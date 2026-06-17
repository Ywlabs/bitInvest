"""배치·Worker 실행 이력 (market.db job_runs 테이블)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from services.market_store import _connect, init_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def begin_job_run(job_name: str) -> int:
    """배치 실행 시작 기록."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO job_runs (job_name, started_at, status, summary, detail_json)
            VALUES (?, ?, 'running', '', '{}')
            """,
            (job_name, _now_iso()),
        )
        return int(cursor.lastrowid)


def complete_job_run(
    run_id: int,
    *,
    exit_code: int,
    status: str,
    summary: str = "",
    detail: dict[str, Any] | None = None,
    error_text: str = "",
    duration_ms: int | None = None,
) -> None:
    """배치 실행 완료 기록."""
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE job_runs
            SET finished_at = ?,
                duration_ms = ?,
                exit_code = ?,
                status = ?,
                summary = ?,
                detail_json = ?,
                error_text = ?
            WHERE id = ?
            """,
            (
                _now_iso(),
                duration_ms,
                exit_code,
                status,
                summary,
                json.dumps(detail or {}, ensure_ascii=False),
                error_text,
                run_id,
            ),
        )


def list_job_runs(
    job_name: str | None = None,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """최근 배치 실행 이력 조회."""
    init_db()
    with _connect() as conn:
        if job_name:
            rows = conn.execute(
                """
                SELECT * FROM job_runs
                WHERE job_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (job_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM job_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]
