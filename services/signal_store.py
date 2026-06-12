"""TradingWorker 이관용 신호 큐 (SQLite, 향후 MQTT 대체 가능)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from services.market_store import _connect, init_db

SIGNAL_PENDING = "pending"
SIGNAL_PROCESSING = "processing"
SIGNAL_DONE = "done"
SIGNAL_REJECTED = "rejected"


def create_signal(
    *,
    trigger_type: str,
    reason: str,
    snapshot_id: int,
    priority: int = 0,
    metrics: dict[str, Any] | None = None,
) -> int:
    """매매 신호 생성 (pending)."""
    init_db()
    created_at = datetime.now(timezone.utc).astimezone().isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trading_signals
            (created_at, trigger_type, reason, snapshot_id, status, priority, metrics_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                trigger_type,
                reason,
                snapshot_id,
                SIGNAL_PENDING,
                priority,
                json.dumps(metrics or {}, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def has_pending_signal(trigger_type: str | None = None) -> bool:
    """동일 유형 pending 신호 존재 여부."""
    init_db()
    with _connect() as conn:
        if trigger_type:
            row = conn.execute(
                """
                SELECT 1 FROM trading_signals
                WHERE status = ? AND trigger_type = ?
                LIMIT 1
                """,
                (SIGNAL_PENDING, trigger_type),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM trading_signals WHERE status = ? LIMIT 1",
                (SIGNAL_PENDING,),
            ).fetchone()
    return row is not None


def has_recent_signal(trigger_type: str, cooldown_hours: float) -> bool:
    """쿨다운 기간 내 동일 유형 신호가 있었는지."""
    init_db()
    since = (
        datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    ).astimezone().isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM trading_signals
            WHERE trigger_type = ?
              AND created_at >= ?
              AND status IN (?, ?, ?)
            LIMIT 1
            """,
            (trigger_type, since, SIGNAL_PENDING, SIGNAL_PROCESSING, SIGNAL_DONE),
        ).fetchone()
    return row is not None


def claim_next_pending_signal() -> dict[str, Any] | None:
    """가장 우선순위 높은 pending 신호를 processing 으로 전환 후 반환."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM trading_signals
            WHERE status = ?
            ORDER BY priority DESC, id ASC
            LIMIT 1
            """,
            (SIGNAL_PENDING,),
        ).fetchone()
        if row is None:
            return None
        signal_id = int(row["id"])
        conn.execute(
            "UPDATE trading_signals SET status = ? WHERE id = ?",
            (SIGNAL_PROCESSING, signal_id),
        )
        return dict(row)


def complete_signal(signal_id: int, status: str, note: str | None = None) -> None:
    """신호 처리 완료."""
    init_db()
    completed_at = datetime.now(timezone.utc).astimezone().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE trading_signals
            SET status = ?, completed_at = ?, result_note = ?
            WHERE id = ?
            """,
            (status, completed_at, note, signal_id),
        )


def get_signal(signal_id: int) -> dict[str, Any]:
    """신호 ID 조회."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM trading_signals WHERE id = ?", (signal_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"signal_id={signal_id} 를 찾을 수 없습니다.")
    return dict(row)
