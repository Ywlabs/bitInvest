"""시장 구조·다이버전스·볼린저 팩터."""

from __future__ import annotations

from typing import Any

from config import Settings
from core.strategy.factors.base import FactorResult
from core.strategy.models import ScoreBreakdown


class StructureFactor:
    name = "STRUCTURE"
    max_points = 5.0

    def evaluate(self, metrics: dict[str, Any], settings: Settings) -> FactorResult:
        ta = metrics.get("technical") or {}
        result = FactorResult(max_points=self.max_points)

        bias = ta.get("structure_bias")
        if bias == "bearish" and ta.get("structure_lower_high") and ta.get("return_7d_pct", 0) < -5:
            result.block_reasons.append("구조적 약세(저점 갱신·LH 패턴)")

        if ta.get("structure_near_support") and bias in ("bullish", "range"):
            result.breakdown.append(
                ScoreBreakdown(
                    "SUPPORT",
                    1.5,
                    f"지지 근접 ({ta.get('dist_support_pct', 0):+.1f}%)",
                )
            )

        if ta.get("structure_higher_low") and bias == "bullish":
            result.breakdown.append(ScoreBreakdown("STRUCTURE", 1.0, "Higher Low 구조"))

        if ta.get("rsi_bullish_divergence"):
            result.breakdown.append(ScoreBreakdown("DIVERGENCE", 2.0, "RSI 강세 다이버전스"))
        elif ta.get("macd_bullish_divergence"):
            result.breakdown.append(ScoreBreakdown("DIVERGENCE", 1.5, "MACD 강세 다이버전스"))

        if ta.get("rsi_bearish_divergence"):
            result.block_reasons.append("RSI 약세 다이버전스")

        bb_b = ta.get("bb_pct_b")
        if bb_b is not None and bb_b <= 0.1:
            result.breakdown.append(
                ScoreBreakdown("BOLLINGER", 1.0, f"볼린저 하단 (%B {bb_b:.2f})")
            )

        return result
