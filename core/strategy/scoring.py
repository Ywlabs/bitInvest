"""종합 점수 엔진 — 팩터 합성 + 변동성 레짐."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from core.strategy.budget import MonthlyBudget
from core.strategy.factors import DEFAULT_FACTORS
from core.strategy.factors.base import ScoringFactor
from core.strategy.models import ScoreBreakdown, ScoreResult
from core.strategy.regime import resolve_atr_regime


class CompositeScorer:
    """팩터 기반 종합 분석 점수 산출."""

    def __init__(
        self,
        settings: Settings | None = None,
        factors: tuple[ScoringFactor, ...] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.budget = MonthlyBudget(self.settings)
        self.factors = factors or DEFAULT_FACTORS
        self.max_possible = sum(f.max_points for f in self.factors)

    def score(self, metrics: dict[str, Any]) -> ScoreResult:
        breakdown: list[ScoreBreakdown] = []
        block_reasons: list[str] = []

        for factor in self.factors:
            outcome = factor.evaluate(metrics, self.settings)
            breakdown.extend(outcome.breakdown)
            block_reasons.extend(outcome.block_reasons)

        total = sum(b.points for b in breakdown)
        blocked = len(block_reasons) > 0

        ta = metrics.get("technical") or {}
        min_score_add, size_multiplier = resolve_atr_regime(
            ta.get("atr_ratio"),
            self.settings,
        )
        effective_min_score = self.settings.add_buy_min_score + min_score_add

        recommend = (not blocked) and total >= effective_min_score
        recommended_krw = 0.0
        tier = self.budget.resolve_tier(total)
        if recommend:
            recommended_krw = self.budget.allocate_for_score(total, size_multiplier)

        confidence = min(0.95, total / self.max_possible) if not blocked else 0.0

        return ScoreResult(
            total_score=total,
            max_possible=self.max_possible,
            breakdown=breakdown,
            blocked=blocked,
            block_reasons=block_reasons,
            recommend_add_buy=recommend and recommended_krw > 0,
            recommended_krw=recommended_krw,
            confidence=confidence,
            effective_min_score=effective_min_score,
            atr_size_multiplier=size_multiplier,
            add_buy_tier=tier.key if tier else "",
            add_buy_tier_label=tier.label if tier else "",
            add_buy_tier_multiplier=tier.size_multiplier if tier else 0.0,
        )
