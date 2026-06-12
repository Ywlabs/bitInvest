"""매매 신호 트리거 엔진."""

from core.triggers.engine import TriggerEngine, TriggerResult

__all__ = ["TriggerEngine", "TriggerResult"]

# rules.py 는 레거시; 신규 전략은 core.strategy.scoring 사용
