"""월간 추가 매수 예산 관리 (DCA 와 별도)."""

from __future__ import annotations

from datetime import datetime, timezone

from config import Settings, get_settings
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

    def allocate_for_score(self, score: float) -> float:
        """
        종합 점수에 따라 이번 추가 매수 금액 산정.

        단순 % 하락이 아니라 점수 구간별 월 예산 비율 사용.
        """
        remaining = self.remaining()
        if remaining <= 0 or score < self.settings.add_buy_min_score:
            return 0.0

        if score >= 9:
            ratio = 1.0
        elif score >= 7:
            ratio = 0.5
        else:
            ratio = 0.25

        amount = min(remaining, self.monthly_limit * ratio)
        amount = min(amount, self.settings.add_buy_max_per_order_krw)
        if amount < self.settings.add_buy_min_order_krw:
            return 0.0
        return amount

    def record(self, amount: float, note: str = "") -> None:
        """집행 금액 기록."""
        record_add_buy_spent(self.month_key, amount, note)
