"""
배치·Worker 실행 이력 조회 (market.db job_runs).

사용법:
    python scripts/show_job_log.py
    python scripts/show_job_log.py --job analysis
    python scripts/show_job_log.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.job_log_store import list_job_runs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="배치 실행 이력 조회")
    parser.add_argument("--job", help="analysis | trading | report | pipeline")
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    rows = list_job_runs(args.job, limit=args.limit)
    if not rows:
        print("실행 이력이 없습니다.")
        return 0

    print("=" * 60)
    print("  배치 실행 이력 (data/market.db → job_runs)")
    print("=" * 60)
    for row in rows:
        status = row["status"]
        ms = row.get("duration_ms")
        dur = f"{ms}ms" if ms is not None else "-"
        print(
            f"[{row['id']}] {row['job_name']:8} {status:7} "
            f"exit={row.get('exit_code', '-')} {dur}"
        )
        print(f"    시작: {row['started_at']}")
        if row.get("finished_at"):
            print(f"    종료: {row['finished_at']}")
        if row.get("summary"):
            print(f"    요약: {row['summary']}")
        if row.get("error_text"):
            print(f"    오류: {row['error_text']}")
        detail = row.get("detail_json")
        if detail and detail != "{}":
            try:
                parsed = json.loads(detail)
                if parsed:
                    print(f"    상세: {json.dumps(parsed, ensure_ascii=False)}")
            except json.JSONDecodeError:
                pass
        print("-" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
