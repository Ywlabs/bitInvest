"""종합 점수 기반 트리거 엔진."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.strategy.scoring import CompositeScorer


@dataclass
class TriggerResult:
    """트리거 평가 결과."""

    fired: bool
    trigger_type: str | None
    reason: str
    priority: int
    score_result: dict[str, Any] | None = None

    @classmethod
    def none(cls) -> TriggerResult:
        return cls(fired=False, trigger_type=None, reason="", priority=0, score_result=None)


class TriggerEngine:
    """종합 분석 점수로 ADD_BUY 신호 발생 여부를 판단한다."""

    def __init__(self) -> None:
        self.scorer = CompositeScorer()

    def evaluate(self, metrics: dict[str, Any]) -> TriggerResult:
        result = self.scorer.score(metrics)
        score_dict = result.to_dict()

        if not result.recommend_add_buy:
            reason = result.summary_reason
            if result.blocked:
                reason = "보류: " + "; ".join(result.block_reasons)
            elif result.total_score > 0:
                reason = f"점수 부족 ({result.total_score:.1f}) — " + reason
            return TriggerResult(
                fired=False,
                trigger_type=None,
                reason=reason,
                priority=0,
                score_result=score_dict,
            )

        priority = int(min(30, result.total_score * 3))
        return TriggerResult(
            fired=True,
            trigger_type="ADD_BUY",
            reason=result.summary_reason + f" | 예산 {result.recommended_krw:,.0f}원",
            priority=priority,
            score_result=score_dict,
        )
