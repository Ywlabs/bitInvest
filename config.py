"""업비트 API 및 애플리케이션 설정."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 (.env 위치 기준)
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """환경 변수 기반 설정."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    upbit_access_key: str = Field(..., alias="UPBIT_ACCESS_KEY")
    upbit_secret_key: str = Field(..., alias="UPBIT_SECRET_KEY")
    default_ticker: str = Field(default="KRW-BTC", alias="DEFAULT_TICKER")
    dry_run: bool = Field(default=True, alias="DRY_RUN")
    signal_cooldown_hours: float = Field(default=8.0, alias="SIGNAL_COOLDOWN_HOURS")

    # --- 추가 매수(ADD_BUY) 전략 — DCA 와 별도, 매도 없음 ---
    monthly_add_buy_budget_krw: float = Field(
        default=500_000.0,
        alias="MONTHLY_ADD_BUY_BUDGET_KRW",
        description="월간 추가 매수 총 한도 (원)",
    )
    add_buy_min_score: float = Field(
        default=5.0,
        alias="ADD_BUY_MIN_SCORE",
        description="종합 점수 이상일 때만 ADD_BUY 신호",
    )
    add_buy_min_order_krw: float = Field(
        default=30_000.0,
        alias="ADD_BUY_MIN_ORDER_KRW",
        description="1회 추가 매수 최소 금액 (등급 금액 하한)",
    )
    add_buy_max_per_order_krw: float = Field(
        default=50_000.0,
        alias="ADD_BUY_MAX_PER_ORDER_KRW",
        description="1회 추가 매수 절대 상한 (원)",
    )
    add_buy_remaining_pct: float = Field(
        default=0.15,
        alias="ADD_BUY_REMAINING_PCT",
        description="1회 매수 = 월 잔여 예산 × 이 비율 × 등급배율",
    )
    # 등급별 금액 배율 (점수 구간)
    add_buy_tier_low_multiplier: float = Field(
        default=0.8,
        alias="ADD_BUY_TIER_LOW_MULTIPLIER",
        description="저등급 배율",
    )
    add_buy_tier_mid_multiplier: float = Field(
        default=1.0,
        alias="ADD_BUY_TIER_MID_MULTIPLIER",
        description="중등급 배율",
    )
    add_buy_tier_high_multiplier: float = Field(
        default=1.2,
        alias="ADD_BUY_TIER_HIGH_MULTIPLIER",
        description="고등급 배율",
    )
    add_buy_tier_mid_min_score: float = Field(
        default=7.0,
        alias="ADD_BUY_TIER_MID_MIN_SCORE",
        description="중등급 최소 종합 점수",
    )
    add_buy_tier_high_min_score: float = Field(
        default=9.0,
        alias="ADD_BUY_TIER_HIGH_MIN_SCORE",
        description="고등급 최소 종합 점수",
    )
    strategy_sell_enabled: bool = Field(
        default=False,
        alias="STRATEGY_SELL_ENABLED",
        description="10년 보유 전략: 기본 false (매도 비활성)",
    )

    # 종합 점수용 매크로 임계값
    score_kimchi_favorable_pct: float = Field(default=1.0, alias="SCORE_KIMCHI_FAVORABLE_PCT")
    score_kimchi_block_pct: float = Field(default=2.5, alias="SCORE_KIMCHI_BLOCK_PCT")
    score_usd_krw_block_pct: float = Field(default=0.5, alias="SCORE_USD_KRW_BLOCK_PCT")

    trigger_onchain_inflow_btc: float = Field(default=500.0, alias="TRIGGER_ONCHAIN_INFLOW_BTC")
    trigger_onchain_enabled: bool = Field(default=False, alias="TRIGGER_ONCHAIN_ENABLED")

    # Phase 2-A: MTF / ATR / Drawdown / Volume
    score_weekly_bear_block_enabled: bool = Field(
        default=True,
        alias="SCORE_WEEKLY_BEAR_BLOCK_ENABLED",
        description="주봉 약세 시 ADD_BUY 차단",
    )
    atr_high_ratio: float = Field(
        default=1.5,
        alias="ATR_HIGH_RATIO",
        description="ATR 비율(60일 대비) 고변동 임계",
    )
    atr_extreme_ratio: float = Field(
        default=2.0,
        alias="ATR_EXTREME_RATIO",
        description="ATR 비율 극단 변동 임계",
    )
    atr_high_min_score_add: float = Field(
        default=1.0,
        alias="ATR_HIGH_MIN_SCORE_ADD",
        description="고변동 시 최소 점수 가산",
    )
    atr_extreme_min_score_add: float = Field(
        default=2.0,
        alias="ATR_EXTREME_MIN_SCORE_ADD",
        description="극단 변동 시 최소 점수 가산",
    )
    atr_high_size_multiplier: float = Field(
        default=0.5,
        alias="ATR_HIGH_SIZE_MULTIPLIER",
        description="고변동 시 매수 금액 배율",
    )
    atr_extreme_size_multiplier: float = Field(
        default=0.35,
        alias="ATR_EXTREME_SIZE_MULTIPLIER",
        description="극단 변동 시 매수 금액 배율",
    )
    score_volume_confirm_ratio: float = Field(
        default=1.2,
        alias="SCORE_VOLUME_CONFIRM_RATIO",
        description="거래량 동반 조정 판정 배율",
    )

    @field_validator("upbit_access_key", "upbit_secret_key")
    @classmethod
    def validate_api_keys(cls, value: str) -> str:
        """플레이스홀더 키 사용 시 명확한 오류를 발생시킨다."""
        placeholder = {"your_access_key_here", "your_secret_key_here", ""}
        if value.strip() in placeholder:
            raise ValueError(
                ".env 파일에 실제 UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY 를 설정해 주세요."
            )
        return value.strip()


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤."""
    return Settings()
