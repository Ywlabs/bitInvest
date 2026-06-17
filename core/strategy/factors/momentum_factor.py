"""모멘텀·추세 강도 팩터 (RSI, MACD, MA, ADX)."""

from __future__ import annotations

from typing import Any

from config import Settings
from core.strategy.factors.base import FactorResult
from core.strategy.models import ScoreBreakdown


class MomentumFactor:
    name = "MOMENTUM"
    max_points = 9.5

    def evaluate(self, metrics: dict[str, Any], settings: Settings) -> FactorResult:
        ta = metrics.get("technical") or {}
        result = FactorResult(max_points=self.max_points)

        rsi = ta.get("rsi_14")
        if rsi is not None:
            if rsi <= 30:
                result.breakdown.append(ScoreBreakdown("RSI", 2.0, f"RSI {rsi:.1f} (과매도)"))
            elif rsi <= 40:
                result.breakdown.append(ScoreBreakdown("RSI", 1.0, f"RSI {rsi:.1f} (약과매도)"))
            elif rsi >= 70:
                result.block_reasons.append(f"RSI과매수({rsi:.0f})")

        hist = ta.get("macd_hist")
        hist_prev = ta.get("macd_hist_prev")
        if hist is not None and hist_prev is not None:
            if hist_prev < 0 <= hist:
                result.breakdown.append(ScoreBreakdown("MACD", 2.0, "MACD 히스토그램 상향 전환"))
            elif hist < 0 and hist > hist_prev:
                result.breakdown.append(ScoreBreakdown("MACD", 1.0, "MACD 하락 둔화"))

        dist_ma200 = ta.get("dist_ma200_pct")
        if dist_ma200 is not None:
            if dist_ma200 <= -15:
                result.breakdown.append(
                    ScoreBreakdown("MA200", 2.0, f"200일선 대비 {dist_ma200:+.1f}%")
                )
            elif dist_ma200 <= -8:
                result.breakdown.append(
                    ScoreBreakdown("MA200", 1.0, f"200일선 대비 {dist_ma200:+.1f}%")
                )

        ret_7d = ta.get("return_7d_pct")
        if ret_7d is not None and ret_7d <= -8:
            result.breakdown.append(
                ScoreBreakdown("MOMENTUM", 1.5, f"7일 수익률 {ret_7d:+.1f}% (조정)")
            )

        ret_30d = ta.get("return_30d_pct")
        if ret_30d is not None and ret_30d <= -15:
            result.breakdown.append(
                ScoreBreakdown("MOMENTUM", 1.0, f"30일 수익률 {ret_30d:+.1f}% (중기 조정)")
            )

        adx = ta.get("adx_14")
        plus_di = ta.get("plus_di")
        minus_di = ta.get("minus_di")
        if adx is not None and adx >= 25 and plus_di is not None and minus_di is not None:
            if plus_di > minus_di and ta.get("dist_ma200_pct", 0) < 0:
                result.breakdown.append(
                    ScoreBreakdown("ADX", 1.0, f"추세 강도 {adx:.0f} (+DI 우세 조정 매수)")
                )

        if ta.get("ma_alignment") == "bullish_stack":
            result.breakdown.append(ScoreBreakdown("MA_STACK", 0.5, "이동평균 정배열"))

        return result
