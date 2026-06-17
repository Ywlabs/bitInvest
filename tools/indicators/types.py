"""기술적 분석 도메인 모델."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MomentumProfile:
    """모멘텀·추세 강도."""

    rsi_14: float
    rsi_7: float
    macd: float
    macd_signal: float
    macd_hist: float
    macd_hist_prev: float
    adx_14: float
    plus_di: float
    minus_di: float
    ma_60: float
    ma_120: float
    ma_200: float
    return_1d_pct: float
    return_7d_pct: float
    return_30d_pct: float
    dist_ma60_pct: float
    dist_ma120_pct: float
    dist_ma200_pct: float
    ma_alignment: str  # bullish_stack | bearish_stack | mixed


@dataclass(frozen=True)
class VolatilityProfile:
    """변동성·밴드."""

    atr_14: float
    atr_14_pct: float
    atr_ratio: float
    bb_pct_b: float
    bb_bandwidth_pct: float
    realized_vol_20d: float
    vol_percentile_60d: float
    regime: str  # low | normal | high | extreme


@dataclass(frozen=True)
class StructureProfile:
    """시장 구조(스윙·지지/저항)."""

    bias: str  # bullish | bearish | range
    higher_low: bool
    lower_high: bool
    support: float
    resistance: float
    dist_support_pct: float
    dist_resistance_pct: float
    near_support: bool


@dataclass(frozen=True)
class VolumeProfile:
    """거래량·OBV."""

    volume_ratio: float
    obv_slope_10d_pct: float
    capitulation: bool
    accumulation: bool
    vwap_20d: float
    dist_vwap_pct: float


@dataclass(frozen=True)
class MTFProfile:
    """멀티 타임프레임 정렬."""

    weekly_trend: str  # bull | bear | neutral
    weekly_dist_ma200_pct: float
    weekly_ma200_slope_pct: float
    alignment_score: float
    daily_weekly_aligned: bool


@dataclass(frozen=True)
class DrawdownProfile:
    """고점 대비 조정폭."""

    drawdown_52w_pct: float
    drawdown_ath_pct: float
    recovery_from_52w_low_pct: float


@dataclass(frozen=True)
class DivergenceProfile:
    """다이버전스."""

    rsi_bullish: bool
    rsi_bearish: bool
    macd_bullish: bool


@dataclass
class TechnicalSnapshot:
    """종합 기술적 스냅샷 — 분석·스코어링 단일 진실 공급원."""

    ticker: str
    price: float
    bar_count: int
    momentum: MomentumProfile
    volatility: VolatilityProfile
    structure: StructureProfile
    volume: VolumeProfile
    mtf: MTFProfile
    drawdown: DrawdownProfile
    divergence: DivergenceProfile
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """하위 호환 flat dict + 프로필별 nested dict."""
        m = self.momentum
        v = self.volatility
        s = self.structure
        vol = self.volume
        mtf = self.mtf
        dd = self.drawdown
        div = self.divergence

        flat: dict[str, Any] = {
            # --- legacy flat keys (Phase 1/2-A) ---
            "price": self.price,
            "rsi_14": m.rsi_14,
            "macd": m.macd,
            "macd_signal": m.macd_signal,
            "macd_hist": m.macd_hist,
            "macd_hist_prev": m.macd_hist_prev,
            "ma_60": m.ma_60,
            "ma_120": m.ma_120,
            "ma_200": m.ma_200,
            "return_1d_pct": m.return_1d_pct,
            "return_7d_pct": m.return_7d_pct,
            "return_30d_pct": m.return_30d_pct,
            "dist_ma200_pct": m.dist_ma200_pct,
            "atr_14": v.atr_14,
            "atr_14_pct": v.atr_14_pct,
            "atr_ratio": v.atr_ratio,
            "drawdown_52w_pct": dd.drawdown_52w_pct,
            "drawdown_ath_pct": dd.drawdown_ath_pct,
            "volume_ratio": vol.volume_ratio,
            "weekly_trend": mtf.weekly_trend,
            "weekly_dist_ma200_pct": mtf.weekly_dist_ma200_pct,
            "weekly_ma200_slope_pct": mtf.weekly_ma200_slope_pct,
            # --- Phase 2-Pro 확장 ---
            "rsi_7": m.rsi_7,
            "adx_14": m.adx_14,
            "plus_di": m.plus_di,
            "minus_di": m.minus_di,
            "dist_ma60_pct": m.dist_ma60_pct,
            "dist_ma120_pct": m.dist_ma120_pct,
            "ma_alignment": m.ma_alignment,
            "bb_pct_b": v.bb_pct_b,
            "bb_bandwidth_pct": v.bb_bandwidth_pct,
            "realized_vol_20d": v.realized_vol_20d,
            "vol_percentile_60d": v.vol_percentile_60d,
            "volatility_regime": v.regime,
            "structure_bias": s.bias,
            "structure_higher_low": s.higher_low,
            "structure_lower_high": s.lower_high,
            "structure_near_support": s.near_support,
            "dist_support_pct": s.dist_support_pct,
            "dist_resistance_pct": s.dist_resistance_pct,
            "obv_slope_10d_pct": vol.obv_slope_10d_pct,
            "capitulation": vol.capitulation,
            "accumulation": vol.accumulation,
            "vwap_20d": vol.vwap_20d,
            "dist_vwap_pct": vol.dist_vwap_pct,
            "mtf_alignment_score": mtf.alignment_score,
            "daily_weekly_aligned": mtf.daily_weekly_aligned,
            "recovery_from_52w_low_pct": dd.recovery_from_52w_low_pct,
            "rsi_bullish_divergence": div.rsi_bullish,
            "rsi_bearish_divergence": div.rsi_bearish,
            "macd_bullish_divergence": div.macd_bullish,
        }
        flat["profiles"] = {
            "momentum": asdict(m),
            "volatility": asdict(v),
            "structure": asdict(s),
            "volume": asdict(vol),
            "mtf": asdict(mtf),
            "drawdown": asdict(dd),
            "divergence": asdict(div),
            "meta": self.meta,
        }
        return flat
