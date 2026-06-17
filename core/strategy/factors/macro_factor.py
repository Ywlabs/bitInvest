"""매크로·온체인 팩터."""

from __future__ import annotations

from typing import Any

from config import Settings
from core.strategy.factors.base import FactorResult
from core.strategy.models import ScoreBreakdown


class MacroFactor:
    name = "MACRO"
    max_points = 2.5

    def evaluate(self, metrics: dict[str, Any], settings: Settings) -> FactorResult:
        result = FactorResult(max_points=self.max_points)

        kimchi = metrics.get("kimchi_premium_pct")
        if kimchi is not None:
            if kimchi <= settings.score_kimchi_favorable_pct:
                result.breakdown.append(
                    ScoreBreakdown("KIMCHI", 1.5, f"김프 {kimchi:+.2f}% (국내 매수 유리)")
                )
            if kimchi >= settings.score_kimchi_block_pct:
                result.block_reasons.append(f"김프과열({kimchi:.1f}%)")

        usd_change = metrics.get("usd_krw_change_pct")
        if usd_change is not None and usd_change >= settings.score_usd_krw_block_pct:
            result.block_reasons.append(f"환율급등({usd_change:+.1f}%)")

        onchain = metrics.get("onchain") or {}
        inflow = onchain.get("exchange_inflow_btc")
        if (
            settings.trigger_onchain_enabled
            and inflow is not None
            and inflow >= settings.trigger_onchain_inflow_btc
        ):
            result.block_reasons.append("거래소유입급증")

        outflow = onchain.get("exchange_outflow_btc")
        if outflow is not None and inflow is not None and outflow > inflow:
            result.breakdown.append(ScoreBreakdown("ONCHAIN", 1.0, "순유출 우세"))

        return result
