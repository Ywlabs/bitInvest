"""
실매수 전 환경·연동 사전 점검.

사용법:
    python scripts/preflight_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings  # noqa: E402
from core.strategy.budget import MonthlyBudget  # noqa: E402
from tools.upbit_client import UpbitClient, UpbitConnectionError  # noqa: E402


def main() -> int:
    cfg = get_settings()
    budget = MonthlyBudget(cfg)

    print("=" * 50)
    print("  bitInvest 실매수 사전 점검")
    print("=" * 50)
    print(f"  DRY_RUN              : {cfg.dry_run}")
    print(f"  티커                 : {cfg.default_ticker}")
    print(f"  월 추가매수 한도     : {cfg.monthly_add_buy_budget_krw:,.0f} KRW")
    print(f"  이번 달 잔여         : {budget.remaining():,.0f} KRW")
    print(f"  페이싱 (잔여×비율)  : {cfg.add_buy_remaining_pct:.0%}")
    print(f"  등급 배율            : ×{cfg.add_buy_tier_low_multiplier} / "
          f"×{cfg.add_buy_tier_mid_multiplier} / ×{cfg.add_buy_tier_high_multiplier}")
    print(f"  1회 절대 상한        : {cfg.add_buy_max_per_order_krw:,.0f} KRW")
    print(f"  신호 쿨다운          : {cfg.signal_cooldown_hours}시간")
    print("-" * 50)

    try:
        client = UpbitClient(cfg)
        client.test_connection()
        summary = client.get_account_summary()
        print("  [업비트 연동] OK")
        print(f"  원화 가용            : {summary.krw_balance:,.0f} KRW")
        print(f"  총 평가액            : {summary.total_eval_amount:,.0f} KRW")
    except UpbitConnectionError as exc:
        print(f"  [업비트 연동] 실패 - {exc}")
        return 1

    print("-" * 50)
    if cfg.dry_run:
        print("  상태: DRY_RUN - 실주문 없음 (백테스트/모의 적합)")
        print("  실매수 전환: .env 에 DRY_RUN=false 설정")
    else:
        print("  상태: LIVE - ADD_BUY 시 실제 시장가 매수 실행")
        print("  확인: API 키에 '주문' 권한, IP 허용, 출금 권한 OFF")

    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
