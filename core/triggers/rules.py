"""매매 신호 트리거 규칙 (.env 임계값 사용)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import Settings, get_settings

# 신호 유형 분류
BUY_TRIGGERS = frozenset({"BTC_DIP", "KIMCHI_LOW"})
SELL_TRIGGERS = frozenset({"BTC_SURGE", "PROFIT_TARGET"})
BLOCK_TRIGGERS = frozenset({"KIMCHI_HIGH", "USD_KRW_SPIKE", "ONCHAIN_INFLOW"})


@dataclass
class RuleHit:
    """단일 규칙 충족 결과."""

    trigger_type: str
    reason: str
    priority: int
    category: str  # buy | sell | block


def evaluate_rules(metrics: dict[str, Any], settings: Settings | None = None) -> list[RuleHit]:
    """모든 규칙을 평가해 충족된 목록을 반환."""
    cfg = settings or get_settings()
    hits: list[RuleHit] = []

    btc_change = metrics.get("btc_krw_change_pct")
    if (
        cfg.trigger_btc_dip_enabled
        and btc_change is not None
        and btc_change <= cfg.trigger_btc_dip_pct
    ):
        hits.append(
            RuleHit(
                trigger_type="BTC_DIP",
                reason=(
                    f"BTC 직전 대비 {btc_change:+.2f}% 하락 "
                    f"(임계 {cfg.trigger_btc_dip_pct}%)"
                ),
                priority=10,
                category="buy",
            )
        )

    if (
        cfg.trigger_btc_surge_enabled
        and btc_change is not None
        and btc_change >= cfg.trigger_btc_surge_pct
    ):
        hits.append(
            RuleHit(
                trigger_type="BTC_SURGE",
                reason=(
                    f"BTC 직전 대비 {btc_change:+.2f}% 상승 "
                    f"(임계 +{cfg.trigger_btc_surge_pct}%)"
                ),
                priority=12,
                category="sell",
            )
        )

    kimchi = metrics.get("kimchi_premium_pct")
    if kimchi is not None:
        if cfg.trigger_kimchi_low_enabled and kimchi <= cfg.trigger_kimchi_low_pct:
            hits.append(
                RuleHit(
                    trigger_type="KIMCHI_LOW",
                    reason=(
                        f"김치 프리미엄 {kimchi:.2f}% "
                        f"(매수 유리, 임계 {cfg.trigger_kimchi_low_pct}% 이하)"
                    ),
                    priority=15,
                    category="buy",
                )
            )
        if cfg.trigger_kimchi_high_enabled and kimchi >= cfg.trigger_kimchi_high_pct:
            hits.append(
                RuleHit(
                    trigger_type="KIMCHI_HIGH",
                    reason=(
                        f"김치 프리미엄 {kimchi:.2f}% "
                        f"(매수 보류, 임계 {cfg.trigger_kimchi_high_pct}% 이상)"
                    ),
                    priority=30,
                    category="block",
                )
            )

    usd_change = metrics.get("usd_krw_change_pct")
    if (
        cfg.trigger_usd_krw_spike_enabled
        and usd_change is not None
        and usd_change >= cfg.trigger_usd_krw_spike_pct
    ):
        hits.append(
            RuleHit(
                trigger_type="USD_KRW_SPIKE",
                reason=(
                    f"USD/KRW 직전 대비 {usd_change:+.2f}% 급등 "
                    f"(임계 +{cfg.trigger_usd_krw_spike_pct}%)"
                ),
                priority=25,
                category="block",
            )
        )

    if cfg.trigger_onchain_enabled:
        onchain = metrics.get("onchain") or {}
        inflow = onchain.get("exchange_inflow_btc")
        if inflow is not None and inflow >= cfg.trigger_onchain_inflow_btc:
            hits.append(
                RuleHit(
                    trigger_type="ONCHAIN_INFLOW",
                    reason=(
                        f"거래소 BTC 유입 {inflow:,.2f} "
                        f"(임계 {cfg.trigger_onchain_inflow_btc})"
                    ),
                    priority=28,
                    category="block",
                )
            )

    account_pnl = metrics.get("account_pnl_rate_pct")
    if (
        cfg.trigger_profit_sell_enabled
        and account_pnl is not None
        and account_pnl >= cfg.trigger_profit_sell_pct
    ):
        hits.append(
            RuleHit(
                trigger_type="PROFIT_TARGET",
                reason=(
                    f"BTC 수익률 {account_pnl:+.2f}% "
                    f"(익절 검토, 임계 +{cfg.trigger_profit_sell_pct}%)"
                ),
                priority=18,
                category="sell",
            )
        )

    return hits
