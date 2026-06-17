"""MTF·추세 정렬 팩터."""

from __future__ import annotations

from typing import Any

from config import Settings
from core.strategy.factors.base import FactorResult
from core.strategy.models import ScoreBreakdown


class MTFFactor:
    name = "MTF"
    max_points = 1.5

    def evaluate(self, metrics: dict[str, Any], settings: Settings) -> FactorResult:
        ta = metrics.get("technical") or {}
        result = FactorResult(max_points=self.max_points)

        trend = ta.get("weekly_trend")
        if settings.score_weekly_bear_block_enabled and trend == "bear":
            result.block_reasons.append(
                f"주봉약세(200주선 {ta.get('weekly_dist_ma200_pct', 0):+.1f}%)"
            )
            return result

        align = float(ta.get("mtf_alignment_score") or 0)
        if trend == "bull":
            pts = 0.5 + min(0.5, align * 0.5)
            result.breakdown.append(
                ScoreBreakdown(
                    "WEEKLY",
                    pts,
                    f"주봉 강세·정렬 {align:.2f} (200주선 {ta.get('weekly_dist_ma200_pct', 0):+.1f}%)",
                )
            )
        elif ta.get("daily_weekly_aligned"):
            result.breakdown.append(
                ScoreBreakdown("WEEKLY", 0.3, f"일·주 타임프레임 정렬 ({align:.2f})")
            )

        return result
