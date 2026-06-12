"""전략 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreBreakdown:
    """개별 요인 점수."""

    factor: str
    points: float
    reason: str


@dataclass
class ScoreResult:
    """종합 분석 점수 결과."""

    total_score: float
    max_possible: float
    breakdown: list[ScoreBreakdown] = field(default_factory=list)
    blocked: bool = False
    block_reasons: list[str] = field(default_factory=list)
    recommend_add_buy: bool = False
    recommended_krw: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "max_possible": self.max_possible,
            "breakdown": [
                {"factor": b.factor, "points": b.points, "reason": b.reason}
                for b in self.breakdown
            ],
            "blocked": self.blocked,
            "block_reasons": self.block_reasons,
            "recommend_add_buy": self.recommend_add_buy,
            "recommended_krw": self.recommended_krw,
            "confidence": self.confidence,
        }

    @property
    def summary_reason(self) -> str:
        """신호 큐에 저장할 요약 사유."""
        parts = [f"종합점수 {self.total_score:.1f}"]
        top = sorted(self.breakdown, key=lambda b: b.points, reverse=True)[:3]
        for b in top:
            if b.points > 0:
                parts.append(f"{b.factor}+{b.points:.0f}")
        if self.block_reasons:
            parts.append("보류:" + ",".join(self.block_reasons))
        return " | ".join(parts)
