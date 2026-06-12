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
        default=1_000_000.0,
        alias="MONTHLY_ADD_BUY_BUDGET_KRW",
        description="월간 추가 매수 총 한도 (원)",
    )
    add_buy_min_score: float = Field(
        default=5.0,
        alias="ADD_BUY_MIN_SCORE",
        description="종합 점수 이상일 때만 ADD_BUY 신호",
    )
    add_buy_min_order_krw: float = Field(
        default=100_000.0,
        alias="ADD_BUY_MIN_ORDER_KRW",
        description="1회 추가 매수 최소 금액",
    )
    add_buy_max_per_order_krw: float = Field(
        default=500_000.0,
        alias="ADD_BUY_MAX_PER_ORDER_KRW",
        description="1회 추가 매수 최대 금액",
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
