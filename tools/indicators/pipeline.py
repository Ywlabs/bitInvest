"""지표 파이프라인 — 수집 → 계산 → TechnicalSnapshot 조립."""

from __future__ import annotations

from tools.indicators.divergence import detect_divergence
from tools.indicators.errors import IndicatorError
from tools.indicators.mtf import fetch_weekly_mtf
from tools.indicators.provider import fetch_ohlcv
from tools.indicators.structure import analyze_structure
from tools.indicators.ta_math import (
    adx_dmi,
    ma_stack_label,
    macd,
    pct_change_from,
    wilder_rsi,
)
from tools.indicators.types import MomentumProfile, TechnicalSnapshot
from tools.indicators.volatility import build_drawdown_profile, build_volatility_profile
from tools.indicators.volume_profile import build_volume_profile

DEFAULT_BAR_COUNT = 400
MIN_BARS = 60


def fetch_technical_snapshot(
    ticker: str = "KRW-BTC",
    count: int = DEFAULT_BAR_COUNT,
) -> TechnicalSnapshot:
    """
    업비트 일봉 기반 종합 기술 스냅샷.

    Wilder RSI/ATR, ADX, 볼린저, VWAP, OBV, 구조·다이버전스, MTF를 한 번에 산출한다.
    """
    df = fetch_ohlcv(ticker, interval="day", count=count)
    if len(df) < MIN_BARS:
        raise IndicatorError(f"{ticker} 일봉 데이터 부족 (필요 {MIN_BARS}봉+)")

    close = df["close"]
    price = float(close.iloc[-1])

    rsi14 = wilder_rsi(close, 14)
    rsi7 = wilder_rsi(close, 7)
    macd_line, signal_line, hist = macd(close)
    adx, plus_di, minus_di = adx_dmi(df, 14)

    ma_60 = float(close.rolling(60).mean().iloc[-1])
    ma_120 = float(close.rolling(120).mean().iloc[-1])
    ma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else ma_120

    def _ret(days: int) -> float:
        if len(close) <= days:
            return 0.0
        return pct_change_from(price, float(close.iloc[-1 - days]))

    momentum = MomentumProfile(
        rsi_14=float(rsi14.iloc[-1]),
        rsi_7=float(rsi7.iloc[-1]),
        macd=float(macd_line.iloc[-1]),
        macd_signal=float(signal_line.iloc[-1]),
        macd_hist=float(hist.iloc[-1]),
        macd_hist_prev=float(hist.iloc[-2]),
        adx_14=float(adx.iloc[-1]),
        plus_di=float(plus_di.iloc[-1]),
        minus_di=float(minus_di.iloc[-1]),
        ma_60=ma_60,
        ma_120=ma_120,
        ma_200=ma_200,
        return_1d_pct=_ret(1),
        return_7d_pct=_ret(7),
        return_30d_pct=_ret(30),
        dist_ma60_pct=pct_change_from(price, ma_60),
        dist_ma120_pct=pct_change_from(price, ma_120),
        dist_ma200_pct=pct_change_from(price, ma_200),
        ma_alignment=ma_stack_label(price, ma_60, ma_120, ma_200),
    )

    volatility = build_volatility_profile(df, price, close)
    structure = analyze_structure(df, price)
    volume = build_volume_profile(df, price)
    drawdown = build_drawdown_profile(close, price)
    divergence = detect_divergence(close, rsi14, hist)
    mtf = fetch_weekly_mtf(ticker, price, ma_200)

    return TechnicalSnapshot(
        ticker=ticker,
        price=price,
        bar_count=len(df),
        momentum=momentum,
        volatility=volatility,
        structure=structure,
        volume=volume,
        mtf=mtf,
        drawdown=drawdown,
        divergence=divergence,
        meta={"interval": "day", "engine": "bitInvest-ta-v2"},
    )
