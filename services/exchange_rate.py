"""달러 환율 및 BTC 시세 조회."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import urlopen

import pyupbit

# 키 없이 사용 가능한 환율 API (순서대로 시도)
USD_KRW_URLS = (
    "https://open.er-api.com/v6/latest/USD",
    "https://api.frankfurter.app/latest?from=USD&to=KRW",
)
BINANCE_BTC_USDT_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
DEFAULT_TICKER = "KRW-BTC"


class MarketDataError(Exception):
    """시세·환율 조회 실패."""


@dataclass
class MarketSnapshotData:
    """분석 Worker가 수집하는 시장 스냅샷."""

    captured_at: str
    usd_krw: float
    btc_krw: float
    btc_usd_binance: float
    btc_usd_implied: float
    kimchi_premium_pct: float | None
    source: str

    def to_dict(self) -> dict:
        return {
            "captured_at": self.captured_at,
            "usd_krw": self.usd_krw,
            "btc_krw": self.btc_krw,
            "btc_usd_binance": self.btc_usd_binance,
            "btc_usd_implied": self.btc_usd_implied,
            "kimchi_premium_pct": self.kimchi_premium_pct,
            "source": self.source,
        }


def fetch_usd_krw_rate() -> float:
    """USD/KRW 환율 조회 (무료 API 폴백 체인)."""
    errors: list[str] = []
    for url in USD_KRW_URLS:
        try:
            request = urlopen(url, timeout=10)
            with request as response:
                payload = json.loads(response.read().decode("utf-8"))
            rate = payload.get("rates", {}).get("KRW")
            if rate:
                return float(rate)
            errors.append(f"{url}: KRW 값 없음")
        except Exception as exc:  # noqa: BLE001 — 폴백 체인
            errors.append(f"{url}: {exc}")
    raise MarketDataError("USD/KRW 환율 조회 실패 — " + " | ".join(errors))


def fetch_btc_usdt_binance() -> float:
    """바이낸스 BTC/USDT 현재가 (김프 계산용)."""
    try:
        with urlopen(BINANCE_BTC_USDT_URL, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        price = payload.get("price")
        if not price:
            raise MarketDataError("바이낸스 BTC 응답에 price 없음")
        return float(price)
    except (URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        raise MarketDataError(f"바이낸스 BTC 조회 실패: {exc}") from exc


def calc_kimchi_premium_pct(btc_krw: float, btc_usd: float, usd_krw: float) -> float:
    """김치 프리미엄 % = (업비트 / 해외원화환산 - 1) * 100"""
    global_krw = btc_usd * usd_krw
    if global_krw <= 0:
        return 0.0
    return (btc_krw / global_krw - 1.0) * 100.0


def fetch_btc_krw_price(ticker: str = DEFAULT_TICKER) -> float:
    """업비트 BTC 원화 현재가."""
    price = pyupbit.get_current_price(ticker)
    if price is None:
        raise MarketDataError(f"{ticker} 현재가 조회 실패")
    return float(price)


def collect_market_snapshot(ticker: str = DEFAULT_TICKER) -> MarketSnapshotData:
    """
    달러 환율 + BTC 시세를 수집하고 파생 지표를 계산한다.

    btc_usd_implied = btc_krw / usd_krw
    kimchi_premium_pct = (업비트 vs 바이낸스) * 100
    """
    usd_krw = fetch_usd_krw_rate()
    btc_krw = fetch_btc_krw_price(ticker)
    btc_usd_binance = fetch_btc_usdt_binance()
    btc_usd_implied = btc_krw / usd_krw if usd_krw > 0 else 0.0
    kimchi = calc_kimchi_premium_pct(btc_krw, btc_usd_binance, usd_krw)
    captured_at = datetime.now(timezone.utc).astimezone().isoformat()

    return MarketSnapshotData(
        captured_at=captured_at,
        usd_krw=usd_krw,
        btc_krw=btc_krw,
        btc_usd_binance=btc_usd_binance,
        btc_usd_implied=btc_usd_implied,
        kimchi_premium_pct=kimchi,
        source="er-api+pyupbit+binance",
    )
