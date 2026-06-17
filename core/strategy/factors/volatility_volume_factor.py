"""Drawdown·거래량·VWAP 팩터."""

from __future__ import annotations

from typing import Any

from config import Settings
from core.strategy.factors.base import FactorResult
from core.strategy.models import ScoreBreakdown


class VolatilityVolumeFactor:
    name = "VOL_DD"
    max_points = 5.0

    def _drawdown_points(self, dd_52w: float | None, dd_ath: float | None) -> ScoreBreakdown | None:
        dd = dd_52w if dd_52w is not None else 0.0
        if dd_ath is not None and dd_ath < dd:
            dd = dd_ath
        if dd <= -30:
            return ScoreBreakdown("DRAWDOWN", 2.0, f"고점 대비 {dd:+.1f}% (심층 조정)")
        if dd <= -20:
            return ScoreBreakdown("DRAWDOWN", 1.5, f"고점 대비 {dd:+.1f}% (중간 조정)")
        if dd <= -10:
            return ScoreBreakdown("DRAWDOWN", 1.0, f"고점 대비 {dd:+.1f}% (얕은 조정)")
        return None

    def evaluate(self, metrics: dict[str, Any], settings: Settings) -> FactorResult:
        ta = metrics.get("technical") or {}
        result = FactorResult(max_points=self.max_points)

        dd_item = self._drawdown_points(
            ta.get("drawdown_52w_pct"),
            ta.get("drawdown_ath_pct"),
        )
        if dd_item:
            result.breakdown.append(dd_item)

        if ta.get("capitulation"):
            result.breakdown.append(ScoreBreakdown("CAPITULATION", 2.0, "투매형 캔들+거래량"))
        elif ta.get("accumulation"):
            result.breakdown.append(ScoreBreakdown("VOLUME", 1.0, "OBV·거래량 축적 신호"))
        else:
            vol_ratio = ta.get("volume_ratio")
            ret_1d = ta.get("return_1d_pct")
            if (
                vol_ratio is not None
                and ret_1d is not None
                and ret_1d < 0
                and vol_ratio >= settings.score_volume_confirm_ratio
            ):
                result.breakdown.append(
                    ScoreBreakdown(
                        "VOLUME",
                        1.5,
                        f"거래량 {vol_ratio:.2f}x 동반 하락 ({ret_1d:+.1f}%)",
                    )
                )

        dist_vwap = ta.get("dist_vwap_pct")
        if dist_vwap is not None and dist_vwap <= -2.0:
            result.breakdown.append(
                ScoreBreakdown("VWAP", 0.5, f"VWAP(20) 대비 {dist_vwap:+.1f}%")
            )

        return result
