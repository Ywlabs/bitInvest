"""
종합 분석 점수 확인 (저장/신호 생성 없음).

사용법:
    python scripts/show_score.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings  # noqa: E402
from core.strategy.budget import MonthlyBudget  # noqa: E402
from core.strategy.scoring import CompositeScorer  # noqa: E402
from core.workers.analysis_worker import AnalysisWorker  # noqa: E402
from services.exchange_rate import collect_market_snapshot  # noqa: E402
from services.onchain_client import fetch_onchain_metrics  # noqa: E402
from tools.indicators import fetch_technical_snapshot  # noqa: E402


def main() -> int:
    cfg = get_settings()
    budget = MonthlyBudget(cfg)

    print("=== ADD_BUY 전략 설정 ===")
    print(f"  월 추가매수 한도   : {cfg.monthly_add_buy_budget_krw:,.0f} KRW")
    print(f"  이번 달 사용       : {budget.spent_this_month():,.0f} KRW")
    print(f"  이번 달 잔여       : {budget.remaining():,.0f} KRW")
    print(f"  최소 종합점수      : {cfg.add_buy_min_score}")
    print(f"  페이싱 비율        : 잔여 × {cfg.add_buy_remaining_pct:.0%}")
    print(f"  등급 배율          : 저×{cfg.add_buy_tier_low_multiplier} / "
          f"중×{cfg.add_buy_tier_mid_multiplier} / 고×{cfg.add_buy_tier_high_multiplier}")
    print(f"  1회 절대 상한      : {cfg.add_buy_max_per_order_krw:,.0f} KRW")
    print(f"  등급 기준 점수     : 중≥{cfg.add_buy_tier_mid_min_score} / 고≥{cfg.add_buy_tier_high_min_score}")
    print(f"  매도 전략          : {'ON' if cfg.strategy_sell_enabled else 'OFF (10년 보유)'}")
    print()

    worker = AnalysisWorker(cfg.default_ticker)
    try:
        snap = collect_market_snapshot(cfg.default_ticker).to_dict()
        onchain = fetch_onchain_metrics().to_dict()
        technical = fetch_technical_snapshot(cfg.default_ticker).to_dict()
        metrics = worker._build_metrics(0, snap, onchain)  # noqa: SLF001
        metrics["technical"] = technical
        metrics.update(worker._fetch_account_metrics())  # noqa: SLF001

        result = CompositeScorer(cfg).score(metrics)
        print("=== 종합 분석 점수 ===")
        print(f"  BTC/KRW     : {metrics['btc_krw']:,.0f}")
        print(f"  김프        : {metrics.get('kimchi_premium_pct', 0):+.2f}%")
        print(f"  RSI(14)     : {technical.get('rsi_14', 0):.1f}")
        print(f"  7일 수익률  : {technical.get('return_7d_pct', 0):+.2f}%")
        print(f"  200MA 이격  : {technical.get('dist_ma200_pct', 0):+.2f}%")
        print(f"  52주 Drawdown: {technical.get('drawdown_52w_pct', 0):+.2f}%")
        print(f"  ATR 비율    : {technical.get('atr_ratio', 1):.2f}x")
        print(f"  거래량 비율 : {technical.get('volume_ratio', 1):.2f}x")
        print(f"  주봉 추세   : {technical.get('weekly_trend', '-')}")
        print(f"  MTF 정렬    : {technical.get('mtf_alignment_score', 0):.2f}")
        print(f"  구조 bias   : {technical.get('structure_bias', '-')}")
        print(f"  ADX(14)     : {technical.get('adx_14', 0):.1f}")
        print(f"  볼린저 %B   : {technical.get('bb_pct_b', 0):.2f}")
        print(f"  변동성 레짐 : {technical.get('volatility_regime', '-')}")
        if technical.get("rsi_bullish_divergence"):
            print("  다이버전스  : RSI 강세")
        print()
        print(f"  종합 점수   : {result.total_score:.1f} / {result.max_possible:.0f}")
        print(f"  최소 기준   : {result.effective_min_score:.1f} (ATR 반영)")
        if result.atr_size_multiplier < 1.0:
            print(f"  ATR 금액배율: {result.atr_size_multiplier:.2f}x")
        print(f"  ADD_BUY     : {'예' if result.recommend_add_buy else '아니오'}")
        if result.add_buy_tier:
            print(
                f"  ADD_BUY 등급: {result.add_buy_tier_label} ({result.add_buy_tier}) "
                f"→ 배율 ×{result.add_buy_tier_multiplier:.1f}"
            )
        if result.recommend_add_buy:
            print(f"  권장 금액   : {result.recommended_krw:,.0f} KRW")
        if result.block_reasons:
            print(f"  보류 사유   : {', '.join(result.block_reasons)}")
        print()
        print("  [요인별]")
        for b in result.breakdown:
            print(f"    +{b.points:.1f} {b.factor}: {b.reason}")
        if not result.breakdown:
            print("    (가점 요인 없음)")
    except Exception as exc:  # noqa: BLE001
        print(f"오류: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
