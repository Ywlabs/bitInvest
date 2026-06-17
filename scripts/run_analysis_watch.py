"""
AnalysisWorker 감시 루프 1회 실행.

cron/GitHub Actions 에서 5분~1시간 간격으로 호출.
조건 충족 시 trading_signals 에 pending 신호만 생성한다.

사용법:
    python scripts/run_analysis_watch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import AgentPipeline  # noqa: E402
from services.job_logger import JobLogger  # noqa: E402


def main() -> int:
    with JobLogger("analysis") as log:
        print("[AnalysisWorker] 감시 시작...")
        result = AgentPipeline().run_watch()

        if result.errors:
            for err in result.errors:
                print(f"  오류: {err}")
            log.set_detail(
                {
                    "snapshot_id": result.snapshot_id,
                    "signal_created": result.signal_created,
                    "signal_id": result.signal_id,
                    "errors": result.errors,
                }
            )
            log.set_summary("분석 실패: " + "; ".join(result.errors))
            log.set_exit_code(1)
            return 1

        print(f"  스냅샷 ID : {result.snapshot_id}")
        if result.signal_created:
            print(f"  신호 생성 : ID={result.signal_id} ({result.trigger_type})")
            print(f"  사유      : {result.trigger_reason}")
            summary = f"신호 생성 id={result.signal_id} ({result.trigger_type})"
        else:
            print("  신호 생성 : 없음 (조건 미충족 또는 쿨다운)")
            summary = "신호 없음"

        log.set_detail(
            {
                "snapshot_id": result.snapshot_id,
                "signal_created": result.signal_created,
                "signal_id": result.signal_id,
                "trigger_type": result.trigger_type,
                "trigger_reason": result.trigger_reason,
            }
        )
        log.set_summary(summary)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
