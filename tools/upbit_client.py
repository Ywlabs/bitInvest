"""업비트 Open API 클라이언트 래퍼."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pyupbit

from config import Settings, get_settings


class UpbitConnectionError(Exception):
    """업비트 API 연결 또는 인증 실패."""


@dataclass
class AccountBalance:
    """보유 자산 한 종목."""

    currency: str
    balance: float
    locked: float
    avg_buy_price: float
    unit_currency: str

    @property
    def available(self) -> float:
        """주문에 사용 가능한 수량 (잠금 제외)."""
        return self.balance

    @property
    def total(self) -> float:
        """잠금 포함 전체 수량."""
        return self.balance + self.locked


@dataclass
class AccountSummary:
    """계좌 요약 (평가액 포함)."""

    krw_balance: float
    krw_locked: float
    holdings: list[AccountBalance]
    total_krw_value: float
    total_buy_amount: float
    total_eval_amount: float
    total_pnl: float
    total_pnl_rate: float


class UpbitClient:
    """업비트 계좌 조회 및 (향후) 주문 실행 클라이언트."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._upbit: pyupbit.Upbit | None = None

    @property
    def upbit(self) -> pyupbit.Upbit:
        """인증된 pyupbit 인스턴스 (lazy init)."""
        if self._upbit is None:
            self._upbit = pyupbit.Upbit(
                self.settings.upbit_access_key,
                self.settings.upbit_secret_key,
            )
        return self._upbit

    def test_connection(self) -> bool:
        """
        API 키 유효성 및 계좌 조회 권한을 확인한다.

        Returns:
            연결 성공 여부

        Raises:
            UpbitConnectionError: 인증 실패 또는 API 오류
        """
        try:
            balances = self.upbit.get_balances()
            if balances is None:
                raise UpbitConnectionError(
                    "잔고 조회에 실패했습니다. API 키와 '자산 조회' 권한을 확인해 주세요."
                )
            return True
        except UpbitConnectionError:
            raise
        except Exception as exc:
            raise UpbitConnectionError(f"업비트 연결 실패: {exc}") from exc

    def get_raw_balances(self) -> list[dict[str, Any]]:
        """업비트 원본 잔고 목록 반환."""
        balances = self.upbit.get_balances()
        if balances is None:
            raise UpbitConnectionError("잔고 조회 결과가 비어 있습니다.")
        return balances

    def get_balances(self) -> list[AccountBalance]:
        """보유 자산 목록을 구조화하여 반환."""
        result: list[AccountBalance] = []
        for item in self.get_raw_balances():
            result.append(
                AccountBalance(
                    currency=item["currency"],
                    balance=float(item["balance"]),
                    locked=float(item["locked"]),
                    avg_buy_price=float(item.get("avg_buy_price") or 0),
                    unit_currency=item.get("unit_currency", "KRW"),
                )
            )
        return result

    def get_krw_balance(self) -> float:
        """사용 가능 원화 잔고."""
        balance = self.upbit.get_balance("KRW")
        return float(balance or 0)

    def get_coin_balance(self, currency: str) -> float:
        """
        특정 코인 보유 수량.

        Args:
            currency: 'BTC', 'ETH' 등 (KRW-BTC 형식도 허용)
        """
        symbol = currency.replace("KRW-", "").upper()
        balance = self.upbit.get_balance(symbol)
        return float(balance or 0)

    def get_avg_buy_price(self, ticker: str) -> float:
        """특정 마켓 평균 매수가."""
        price = self.upbit.get_avg_buy_price(ticker)
        return float(price or 0)

    def get_account_summary(self) -> AccountSummary:
        """계좌 전체 요약 (현재가 기준 평가액·손익 포함)."""
        balances = self.get_balances()
        krw = next((b for b in balances if b.currency == "KRW"), None)
        krw_balance = krw.balance if krw else 0.0
        krw_locked = krw.locked if krw else 0.0

        holdings = [b for b in balances if b.currency != "KRW" and b.total > 0]
        tickers = [f"KRW-{b.currency}" for b in holdings]

        current_prices: dict[str, float] = {}
        if tickers:
            prices = pyupbit.get_current_price(tickers)
            if isinstance(prices, dict):
                current_prices = {k: float(v) for k, v in prices.items()}
            elif len(tickers) == 1 and prices is not None:
                current_prices = {tickers[0]: float(prices)}

        coin_buy = sum(h.avg_buy_price * h.total for h in holdings)
        coin_eval = sum(
            current_prices.get(f"KRW-{h.currency}", h.avg_buy_price) * h.total
            for h in holdings
        )
        coin_pnl = coin_eval - coin_buy
        coin_pnl_rate = (coin_pnl / coin_buy * 100) if coin_buy > 0 else 0.0
        total_eval = krw_balance + krw_locked + coin_eval

        return AccountSummary(
            krw_balance=krw_balance,
            krw_locked=krw_locked,
            holdings=holdings,
            total_krw_value=total_eval,
            total_buy_amount=coin_buy,
            total_eval_amount=total_eval,
            total_pnl=coin_pnl,
            total_pnl_rate=coin_pnl_rate,
        )
