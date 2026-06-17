"""월간 추가 매수 예산 관리 (DCA 와 별도)."""

from __future__ import annotations

from datetime import datetime, timezone

from config import Settings, get_settings
from core.strategy.tiers import AddBuyTier, resolve_add_buy_tier
from services.market_store import get_monthly_add_buy_spent, record_add_buy_spent


class MonthlyBudget:
    """월간 ADD_BUY 예산 한도 및 집행 기록."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def month_key(self) -> str:
        return datetime.now(timezone.utc).astimezone().strftime("%Y-%m")

    @property
    def monthly_limit(self) -> float:
        return self.settings.monthly_add_buy_budget_krw

    def spent_this_month(self) -> float:
        return get_monthly_add_buy_spent(self.month_key)

    def remaining(self) -> float:
        return max(0.0, self.monthly_limit - self.spent_this_month())

    def can_spend(self, amount: float) -> bool:
        return amount > 0 and amount <= self.remaining()

    def resolve_tier(self, score: float) -> AddBuyTier | None:
        """점수 → ADD_BUY 등급."""
        return resolve_add_buy_tier(score, self.settings)

    def allocate_for_score(self, score: float, size_multiplier: float = 1.0) -> float:
        """
        종합 점수·월 잔여 기반 1회 추가 매수 금액.

        산식: int(잔여 × REMAINING_PCT × 등급배율 × ATR배율), 절대상한·최소주문 적용.
        """
        remaining = self.remaining()
        tier = self.resolve_tier(score)
        if tier is None or remaining <= 0:
            return 0.0

        paced = (
            remaining
            * self.settings.add_buy_remaining_pct
            * tier.size_multiplier
            * max(0.0, size_multiplier)
        )
        amount = float(int(paced))
        amount = min(amount, remaining)
        amount = min(amount, self.settings.add_buy_max_per_order_krw)

        if amount < self.settings.add_buy_min_order_krw:
            return 0.0
        return amount

    def record(self, amount: float, note: str = "") -> None:
        """집행 금액 기록."""
        record_add_buy_spent(self.month_key, amount, note)
