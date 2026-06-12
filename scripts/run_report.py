"""
ReportWorker 일일 성과 보고서 생성.

사용법:
    python scripts/run_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.workers.report_worker import ReportWorker  # noqa: E402


def main() -> int:
    print("[ReportWorker] 일일 리포트 생성...")
    worker = ReportWorker()
    state = worker.run(worker.build_state_from_db())

    if state.errors:
        for err in state.errors:
            print(f"  오류: {err}")
        return 1

    print(f"  리포트: {state.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
