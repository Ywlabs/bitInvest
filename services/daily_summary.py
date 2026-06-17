"""일자별 활동·시장 데이터 집계."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from services.market_store import _connect, init_db

_DAY = "substr({col}, 1, 10) = ?"


def build_daily_summary(report_date: str) -> dict[str, Any]:
    """
    report_date(YYYY-MM-DD) 하루치 DB 이력을 집계한다.

    로컬 ISO 타임스탬프(…+09:00)의 앞 10자리 날짜로 필터한다.
    """
    init_db()
    with _connect() as conn:
        market = _aggregate_market(conn, report_date)
        jobs = _aggregate_jobs(conn, report_date)
        signals = _list_signals(conn, report_date)
        trades = _list_trades(conn, report_date)
        ledger = _aggregate_ledger(conn, report_date)

    signal_stats = _signal_stats(signals)
    trade_stats = _trade_stats(trades)

    timeline = _build_timeline(jobs.get("runs") or [], signals, trades)

    return {
        "report_date": report_date,
        "market": market,
        "jobs": jobs,
        "signals": {**signal_stats, "items": signals},
        "trades": {**trade_stats, "items": trades},
        "ledger": ledger,
        "timeline": timeline,
    }


def _aggregate_market(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS cnt,
            MIN(btc_krw) AS low,
            MAX(btc_krw) AS high,
            AVG(kimchi_premium_pct) AS kimchi_avg
        FROM market_snapshots
        WHERE {_DAY.format(col="captured_at")}
        """,
        (day,),
    ).fetchone()

    first = conn.execute(
        f"""
        SELECT captured_at, btc_krw, usd_krw, kimchi_premium_pct
        FROM market_snapshots
        WHERE {_DAY.format(col="captured_at")}
        ORDER BY captured_at ASC LIMIT 1
        """,
        (day,),
    ).fetchone()

    last = conn.execute(
        f"""
        SELECT captured_at, btc_krw, usd_krw, kimchi_premium_pct
        FROM market_snapshots
        WHERE {_DAY.format(col="captured_at")}
        ORDER BY captured_at DESC LIMIT 1
        """,
        (day,),
    ).fetchone()

    cnt = int(row["cnt"] or 0) if row else 0
    open_px = float(first["btc_krw"]) if first else None
    close_px = float(last["btc_krw"]) if last else None
    change_pct = None
    if open_px and close_px and open_px > 0:
        change_pct = (close_px - open_px) / open_px * 100

    return {
        "snapshot_count": cnt,
        "btc_krw_open": open_px,
        "btc_krw_close": close_px,
        "btc_krw_low": float(row["low"]) if row and row["low"] is not None else None,
        "btc_krw_high": float(row["high"]) if row and row["high"] is not None else None,
        "btc_change_pct": change_pct,
        "kimchi_avg_pct": float(row["kimchi_avg"]) if row and row["kimchi_avg"] is not None else None,
        "first_captured_at": first["captured_at"] if first else None,
        "last_captured_at": last["captured_at"] if last else None,
        "usd_krw_close": float(last["usd_krw"]) if last else None,
    }


def _aggregate_jobs(conn, day: str) -> dict[str, Any]:
    rows = conn.execute(
        f"""
        SELECT job_name, status, COUNT(*) AS cnt
        FROM job_runs
        WHERE {_DAY.format(col="started_at")}
        GROUP BY job_name, status
        """,
        (day,),
    ).fetchall()

    by_job: dict[str, dict[str, int]] = {}
    total = 0
    for row in rows:
        name = row["job_name"]
        by_job.setdefault(name, {})
        by_job[name][row["status"]] = int(row["cnt"])
        total += int(row["cnt"])

    run_rows = conn.execute(
        f"""
        SELECT id, job_name, started_at, finished_at, status, summary, duration_ms, error_text
        FROM job_runs
        WHERE {_DAY.format(col="started_at")}
        ORDER BY started_at ASC
        """,
        (day,),
    ).fetchall()

    runs = [
        {
            "id": r["id"],
            "job_name": r["job_name"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "status": r["status"],
            "summary": r["summary"],
            "duration_ms": r["duration_ms"],
            "error_text": r["error_text"],
        }
        for r in run_rows
    ]

    return {"total_runs": total, "by_job": by_job, "runs": runs}


def _list_signals(conn, day: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT id, created_at, trigger_type, reason, status, completed_at, result_note, metrics_json
        FROM trading_signals
        WHERE {_DAY.format(col="created_at")}
        ORDER BY created_at ASC
        """,
        (day,),
    ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        metrics = json.loads(row["metrics_json"] or "{}")
        score = metrics.get("score") or {}
        items.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "trigger_type": row["trigger_type"],
                "reason": row["reason"],
                "status": row["status"],
                "completed_at": row["completed_at"],
                "result_note": row["result_note"],
                "total_score": score.get("total_score"),
                "recommended_krw": score.get("recommended_krw"),
            }
        )
    return items


def _list_trades(conn, day: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT id, decided_at, signal_id, action, reason, dry_run, raw_json
        FROM trade_decisions
        WHERE {_DAY.format(col="decided_at")}
        ORDER BY decided_at ASC
        """,
        (day,),
    ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        raw = json.loads(row["raw_json"] or "{}")
        items.append(
            {
                "id": row["id"],
                "decided_at": row["decided_at"],
                "signal_id": row["signal_id"],
                "action": row["action"],
                "reason": row["reason"],
                "dry_run": bool(row["dry_run"]),
                "buy_amount_krw": float(raw.get("buy_amount_krw") or 0),
                "executed": bool(raw.get("executed")),
                "order_uuid": raw.get("order_uuid"),
            }
        )
    return items


def _aggregate_ledger(conn, day: str) -> dict[str, Any]:
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(amount_krw), 0) AS total, COUNT(*) AS cnt
        FROM monthly_add_buy_ledger
        WHERE {_DAY.format(col="created_at")}
        """,
        (day,),
    ).fetchone()
    return {
        "spent_krw": float(row["total"]) if row else 0.0,
        "entry_count": int(row["cnt"]) if row else 0,
    }


def _signal_stats(signals: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    for s in signals:
        st = s.get("status") or "unknown"
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "total": len(signals),
        "add_buy_count": sum(1 for s in signals if s.get("trigger_type") == "ADD_BUY"),
        "by_status": by_status,
    }


def _trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    add_buys = [t for t in trades if t.get("action") == "ADD_BUY"]
    executed = [t for t in add_buys if t.get("executed")]
    return {
        "total": len(trades),
        "add_buy_count": len(add_buys),
        "hold_count": sum(1 for t in trades if t.get("action") != "ADD_BUY"),
        "add_buy_total_krw": sum(float(t.get("buy_amount_krw") or 0) for t in add_buys),
        "executed_count": len(executed),
        "executed_total_krw": sum(float(t.get("buy_amount_krw") or 0) for t in executed),
    }


def _build_timeline(
    jobs: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """시간순 통합 타임라인."""
    events: list[tuple[str, str, str]] = []

    for j in jobs:
        t = j.get("started_at") or ""
        label = {"analysis": "분석", "trading": "매매", "report": "리포트"}.get(
            j.get("job_name", ""), j.get("job_name", "")
        )
        status = j.get("status", "")
        summary = j.get("summary") or status
        events.append((t, "job", f"[{label}] {summary}"))

    for s in signals:
        t = s.get("created_at") or ""
        score = s.get("total_score")
        score_txt = f" · 점수 {score:.1f}" if isinstance(score, (int, float)) else ""
        events.append(
            (
                t,
                "signal",
                f"신호 #{s.get('id')} {s.get('trigger_type')} ({s.get('status')}){score_txt}",
            )
        )

    for tr in trades:
        t = tr.get("decided_at") or ""
        amt = tr.get("buy_amount_krw") or 0
        events.append(
            (
                t,
                "trade",
                f"판단 #{tr.get('id')} {tr.get('action')} "
                f"{amt:,.0f}원"
                + (" 체결" if tr.get("executed") else ""),
            )
        )

    events.sort(key=lambda x: x[0])
    return [{"time": _short_time(t), "kind": k, "text": txt} for t, k, txt in events]


def _short_time(iso: str) -> str:
    if not iso:
        return "-"
    if "T" in iso:
        return iso.split("T", 1)[1][:8]
    return iso[-8:] if len(iso) >= 8 else iso
