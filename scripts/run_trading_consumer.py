"""
TradingWorker 소비자 1회 실행.

pending 신호가 있을 때만 매매 판단을 수행한다.

사용법:
    python scripts/run_trading_consumer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import AgentPipeline  # noqa: E402
from services.job_logger import JobLogger  # noqa: E402


def main() -> int:
    with JobLogger("trading") as log:
        print("[TradingWorker] pending 신호 확인...")
        state = AgentPipeline().run_trading_consumer()

        if state.errors:
            for err in state.errors:
                print(f"  오류: {err}")
            log.set_detail(
                {
                    "signal_id": state.signal_id,
                    "skipped": state.skipped,
                    "errors": state.errors,
                }
            )
            log.set_summary("매매 실패: " + "; ".join(state.errors))
            log.set_exit_code(1)
            return 1

        if state.skipped:
            print(f"  스킵: {state.skip_reason}")
            log.set_detail({"skipped": True, "skip_reason": state.skip_reason})
            log.set_summary(f"스킵: {state.skip_reason}")
            return 0

        decision = state.trading_decision or {}
        action = decision.get("action", "-")
        reason = decision.get("reason", "-")
        print(f"  신호 ID   : {state.signal_id}")
        print(f"  매매 판단 : {action}")
        print(f"  사유      : {reason}")

        log.set_detail(
            {
                "signal_id": state.signal_id,
                "snapshot_id": state.snapshot_id,
                "action": action,
                "buy_amount_krw": decision.get("buy_amount_krw"),
                "executed": decision.get("executed"),
                "order_uuid": decision.get("order_uuid"),
                "dry_run": decision.get("dry_run"),
            }
        )
        log.set_summary(f"신호 {state.signal_id} → {action}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
