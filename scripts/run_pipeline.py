"""
Agent Worker 통합 테스트 실행.

이벤트 모드: watch -> (신호 있으면) trading -> report
강제 모드: --force 시 트리거 없어도 Trading 실행

사용법:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --force
    python scripts/run_pipeline.py --event-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import AgentPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Worker 통합 실행")
    parser.add_argument("--force", action="store_true", help="신호 없어도 Trading 실행")
    parser.add_argument(
        "--event-only",
        action="store_true",
        help="이벤트 모드 (신호 있을 때만 Trading)",
    )
    args = parser.parse_args()
    force = args.force or not args.event_only

    print("Agent Worker 파이프라인 (이벤트 기반)")
    print("  1) AnalysisWorker - 감시/수집/신호생성")
    print("  2) TradingWorker  - pending 신호 시만 매매")
    print("  3) ReportWorker   - 일일 리포트")
    print()

    state = AgentPipeline().run_full(force_trading=force)

    if state.errors:
        print("[오류]")
        for err in state.errors:
            print(f"  - {err}")
        return 1

    print("[완료]")
    print(f"  스냅샷 ID   : {state.snapshot_id}")
    print(f"  신호 생성   : {state.signal_created} (id={state.signal_id})")
    if state.skipped:
        print(f"  Trading     : 스킵 ({state.skip_reason})")
    else:
        decision = state.trading_decision or {}
        print(f"  매매 판단   : {decision.get('action', '-')}")
    print(f"  리포트      : {state.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
