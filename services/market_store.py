"""시장 스냅샷·매매 판단·일일 리포트 SQLite 저장소."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config import BASE_DIR

DB_PATH = BASE_DIR / "data" / "market.db"
REPORTS_DIR = BASE_DIR / "reports"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """테이블 초기화."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                usd_krw REAL NOT NULL,
                btc_krw REAL NOT NULL,
                btc_usd_implied REAL NOT NULL,
                kimchi_premium_pct REAL,
                source TEXT NOT NULL,
                raw_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trade_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decided_at TEXT NOT NULL,
                snapshot_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                confidence REAL NOT NULL,
                dry_run INTEGER NOT NULL,
                account_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(id)
            );

            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                content_json TEXT NOT NULL,
                file_path TEXT
            );

            CREATE TABLE IF NOT EXISTS metric_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL,
                snapshot_id INTEGER,
                raw_json TEXT NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(id)
            );

            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                snapshot_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                metrics_json TEXT NOT NULL,
                completed_at TEXT,
                result_note TEXT,
                FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(id)
            );

            CREATE INDEX IF NOT EXISTS idx_signals_status
                ON trading_signals(status, priority DESC);
            CREATE INDEX IF NOT EXISTS idx_metrics_type_time
                ON metric_snapshots(metric_type, captured_at);

            CREATE TABLE IF NOT EXISTS monthly_add_buy_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month_key TEXT NOT NULL,
                amount_krw REAL NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB 스키마 마이그레이션."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_decisions)").fetchall()]
    if "signal_id" not in cols:
        conn.execute("ALTER TABLE trade_decisions ADD COLUMN signal_id INTEGER")


def save_market_snapshot(data: dict[str, Any]) -> int:
    """시장 스냅샷 저장 후 ID 반환."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO market_snapshots
            (captured_at, usd_krw, btc_krw, btc_usd_implied, kimchi_premium_pct, source, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["captured_at"],
                data["usd_krw"],
                data["btc_krw"],
                data["btc_usd_implied"],
                data.get("kimchi_premium_pct"),
                data["source"],
                json.dumps(data, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def get_market_snapshot(snapshot_id: int) -> dict[str, Any]:
    """스냅샷 ID로 조회."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM market_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"snapshot_id={snapshot_id} 를 찾을 수 없습니다.")
    return dict(row)


def get_previous_market_snapshot(before_id: int) -> dict[str, Any] | None:
    """직전 시장 스냅샷 조회."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM market_snapshots
            WHERE id < ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (before_id,),
        ).fetchone()
    return dict(row) if row else None


def save_metric(snapshot_id: int, metric_type: str, value: float | None, raw: dict) -> None:
    """개별 지표 시계열 저장."""
    init_db()
    captured_at = raw.get("captured_at", "")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO metric_snapshots
            (captured_at, metric_type, value, snapshot_id, raw_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                captured_at,
                metric_type,
                value,
                snapshot_id,
                json.dumps(raw, ensure_ascii=False),
            ),
        )


def save_trade_decision(decision: dict[str, Any]) -> int:
    """매매 판단 저장."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trade_decisions
            (decided_at, snapshot_id, signal_id, action, reason, confidence, dry_run, account_json, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision["decided_at"],
                decision["snapshot_id"],
                decision.get("signal_id"),
                decision["action"],
                decision["reason"],
                decision["confidence"],
                1 if decision["dry_run"] else 0,
                json.dumps(decision["account_summary"], ensure_ascii=False),
                json.dumps(decision, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def save_daily_report(report_date: str, content: dict[str, Any], file_path: str | None) -> int:
    """일일 리포트 저장 (같은 날짜면 갱신)."""
    init_db()
    created_at = content.get("created_at", "")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_reports (report_date, created_at, content_json, file_path)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(report_date) DO UPDATE SET
                created_at = excluded.created_at,
                content_json = excluded.content_json,
                file_path = excluded.file_path
            """,
            (
                report_date,
                created_at,
                json.dumps(content, ensure_ascii=False),
                file_path,
            ),
        )
        row = conn.execute(
            "SELECT id FROM daily_reports WHERE report_date = ?", (report_date,)
        ).fetchone()
        return int(row["id"])


def get_latest_market_snapshot() -> dict[str, Any] | None:
    """가장 최근 시장 스냅샷."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM market_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_latest_trade_decision() -> dict[str, Any] | None:
    """가장 최근 매매 판단 레코드."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM trade_decisions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_monthly_add_buy_spent(month_key: str) -> float:
    """해당 월 ADD_BUY 집행 합계."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_krw), 0) AS total FROM monthly_add_buy_ledger WHERE month_key = ?",
            (month_key,),
        ).fetchone()
    return float(row["total"]) if row else 0.0


def record_add_buy_spent(month_key: str, amount_krw: float, note: str = "") -> None:
    """ADD_BUY 집행 기록."""
    init_db()
    from datetime import datetime, timezone

    created_at = datetime.now(timezone.utc).astimezone().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO monthly_add_buy_ledger (month_key, amount_krw, note, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (month_key, amount_krw, note, created_at),
        )


def get_latest_trading_signal() -> dict[str, Any] | None:
    """가장 최근 트레이딩 신호."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM trading_signals ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def write_report_file(report_date: str, lines: list[str]) -> Path:
    """리포트 텍스트 파일 저장."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"report_{report_date}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
