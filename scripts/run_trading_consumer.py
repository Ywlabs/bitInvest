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


def main() -> int:
    print("[TradingWorker] pending 신호 확인...")
    state = AgentPipeline().run_trading_consumer()

    if state.errors:
        for err in state.errors:
            print(f"  오류: {err}")
        return 1

    if state.skipped:
        print(f"  스킵: {state.skip_reason}")
        return 0

    decision = state.trading_decision or {}
    print(f"  신호 ID   : {state.signal_id}")
    print(f"  매매 판단 : {decision.get('action', '-')}")
    print(f"  사유      : {decision.get('reason', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
