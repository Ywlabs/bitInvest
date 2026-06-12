"""종합 점수 기반 추가 매수(ADD_BUY) 분석 엔진.

단순 '고점 대비 5%/10% 하락' 규칙이 아니라
TA + 매크로 + 심리(김프) 요인을 합산해 판단한다.
"""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from core.strategy.budget import MonthlyBudget
from core.strategy.models import ScoreBreakdown, ScoreResult


class CompositeScorer:
    """종합 분석 점수 산출."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.budget = MonthlyBudget(self.settings)

    def score(self, metrics: dict[str, Any]) -> ScoreResult:
        breakdown: list[ScoreBreakdown] = []
        block_reasons: list[str] = []

        ta = metrics.get("technical") or {}
        kimchi = metrics.get("kimchi_premium_pct")
        usd_change = metrics.get("usd_krw_change_pct")

        # --- 기술적 (TA) ---
        rsi = ta.get("rsi_14")
        if rsi is not None:
            if rsi <= 30:
                breakdown.append(ScoreBreakdown("RSI", 2.0, f"RSI {rsi:.1f} (과매도)"))
            elif rsi <= 40:
                breakdown.append(ScoreBreakdown("RSI", 1.0, f"RSI {rsi:.1f} (약과매도)"))
            elif rsi >= 70:
                block_reasons.append(f"RSI과매수({rsi:.0f})")

        macd_hist = ta.get("macd_hist")
        macd_hist_prev = ta.get("macd_hist_prev")
        if macd_hist is not None and macd_hist_prev is not None:
            if macd_hist_prev < 0 <= macd_hist:
                breakdown.append(ScoreBreakdown("MACD", 2.0, "MACD 히스토그램 상향 전환"))
            elif macd_hist < 0 and macd_hist > macd_hist_prev:
                breakdown.append(ScoreBreakdown("MACD", 1.0, "MACD 하락 둔화"))

        dist_ma200 = ta.get("dist_ma200_pct")
        if dist_ma200 is not None:
            if dist_ma200 <= -15:
                breakdown.append(
                    ScoreBreakdown("MA200", 2.0, f"200일선 대비 {dist_ma200:+.1f}%")
                )
            elif dist_ma200 <= -8:
                breakdown.append(
                    ScoreBreakdown("MA200", 1.0, f"200일선 대비 {dist_ma200:+.1f}%")
                )

        ret_7d = ta.get("return_7d_pct")
        if ret_7d is not None and ret_7d <= -8:
            breakdown.append(
                ScoreBreakdown("MOMENTUM", 1.5, f"7일 수익률 {ret_7d:+.1f}% (조정)")
            )

        ret_30d = ta.get("return_30d_pct")
        if ret_30d is not None and ret_30d <= -15:
            breakdown.append(
                ScoreBreakdown("MOMENTUM", 1.0, f"30일 수익률 {ret_30d:+.1f}% (중기 조정)")
            )

        # --- 매크로 / 김프 ---
        if kimchi is not None:
            if kimchi <= self.settings.score_kimchi_favorable_pct:
                breakdown.append(
                    ScoreBreakdown("KIMCHI", 1.5, f"김프 {kimchi:+.2f}% (국내 매수 유리)")
                )
            if kimchi >= self.settings.score_kimchi_block_pct:
                block_reasons.append(f"김프과열({kimchi:.1f}%)")

        if usd_change is not None and usd_change >= self.settings.score_usd_krw_block_pct:
            block_reasons.append(f"환율급등({usd_change:+.1f}%)")

        onchain = metrics.get("onchain") or {}
        inflow = onchain.get("exchange_inflow_btc")
        if (
            self.settings.trigger_onchain_enabled
            and inflow is not None
            and inflow >= self.settings.trigger_onchain_inflow_btc
        ):
            block_reasons.append("거래소유입급증")

        # --- 온체인 가점 (연동 후) ---
        outflow = onchain.get("exchange_outflow_btc")
        if outflow is not None and inflow is not None and outflow > inflow:
            breakdown.append(ScoreBreakdown("ONCHAIN", 1.0, "순유출 우세"))

        total = sum(b.points for b in breakdown)
        max_possible = 12.0
        blocked = len(block_reasons) > 0
        min_score = self.settings.add_buy_min_score

        recommend = (not blocked) and total >= min_score
        recommended_krw = 0.0
        if recommend:
            recommended_krw = self.budget.allocate_for_score(total)

        confidence = min(0.95, total / max_possible) if not blocked else 0.0

        return ScoreResult(
            total_score=total,
            max_possible=max_possible,
            breakdown=breakdown,
            blocked=blocked,
            block_reasons=block_reasons,
            recommend_add_buy=recommend and recommended_krw > 0,
            recommended_krw=recommended_krw,
            confidence=confidence,
        )
