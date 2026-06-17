"""스코어링 팩터 프로토콜."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from config import Settings
from core.strategy.models import ScoreBreakdown


@dataclass
class FactorResult:
    """단일 팩터 평가 결과."""

    breakdown: list[ScoreBreakdown] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    max_points: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class ScoringFactor(Protocol):
    """종합 점수에 기여하는 전략 팩터."""

    name: str
    max_points: float

    def evaluate(self, metrics: dict[str, Any], settings: Settings) -> FactorResult: ...
