"""ADD_BUY 등급(티어) — 점수 구간별 매수 배율."""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings


@dataclass(frozen=True)
class AddBuyTier:
    """점수 구간별 추가 매수 등급."""

    key: str
    label: str
    min_score: float
    size_multiplier: float


def resolve_add_buy_tier(score: float, settings: Settings) -> AddBuyTier | None:
    """
    종합 점수에 따른 ADD_BUY 등급 반환.

    금액 = 월 잔여 × REMAINING_PCT × 등급배율 × ATR배율 (상한·최소 적용)
    """
    if score < settings.add_buy_min_score:
        return None

    if score >= settings.add_buy_tier_high_min_score:
        return AddBuyTier(
            key="high",
            label="고등급",
            min_score=settings.add_buy_tier_high_min_score,
            size_multiplier=settings.add_buy_tier_high_multiplier,
        )
    if score >= settings.add_buy_tier_mid_min_score:
        return AddBuyTier(
            key="mid",
            label="중등급",
            min_score=settings.add_buy_tier_mid_min_score,
            size_multiplier=settings.add_buy_tier_mid_multiplier,
        )
    return AddBuyTier(
        key="low",
        label="저등급",
        min_score=settings.add_buy_min_score,
        size_multiplier=settings.add_buy_tier_low_multiplier,
    )
