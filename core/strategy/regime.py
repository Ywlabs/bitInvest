"""변동성 레짐 → 최소 점수·포지션 배율."""

from __future__ import annotations

from config import Settings


def resolve_atr_regime(atr_ratio: float | None, settings: Settings) -> tuple[float, float]:
    """
    ATR 60일 대비 비율로 레짐 판정.

    Returns:
        (최소점수 가산, 매수금액 배율)
    """
    if atr_ratio is None:
        return 0.0, 1.0
    if atr_ratio >= settings.atr_extreme_ratio:
        return settings.atr_extreme_min_score_add, settings.atr_extreme_size_multiplier
    if atr_ratio >= settings.atr_high_ratio:
        return settings.atr_high_min_score_add, settings.atr_high_size_multiplier
    return 0.0, 1.0
