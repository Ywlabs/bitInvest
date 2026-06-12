"""온체인 지표 조회 (스텁 — CryptoQuant/Glassnode 연동 예정)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OnchainMetrics:
    """온체인 지표 묶음."""

    exchange_inflow_btc: float | None
    exchange_outflow_btc: float | None
    whale_transfer_usd: float | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "exchange_inflow_btc": self.exchange_inflow_btc,
            "exchange_outflow_btc": self.exchange_outflow_btc,
            "whale_transfer_usd": self.whale_transfer_usd,
            "source": self.source,
        }


def fetch_onchain_metrics() -> OnchainMetrics:
    """
    온체인 데이터 수집.

    TODO: 유료 API 연동 후 실제 값 반환.
    현재는 None 으로 구조만 유지한다.
    """
    return OnchainMetrics(
        exchange_inflow_btc=None,
        exchange_outflow_btc=None,
        whale_transfer_usd=None,
        source="stub",
    )
