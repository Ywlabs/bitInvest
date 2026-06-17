"""분석 Worker — 종합 점수 기반 ADD_BUY 신호 생성."""

from __future__ import annotations

import json
from typing import Any

from config import get_settings
from core.state import PipelineState, WatchResult
from core.triggers import TriggerEngine
from services.exchange_rate import MarketDataError, collect_market_snapshot
from services.market_store import (
    get_previous_market_snapshot,
    save_market_snapshot,
    save_metric,
)
from services.desktop_notify import notify_user
from services.onchain_client import fetch_onchain_metrics
from services.signal_store import create_signal, has_pending_signal, has_recent_signal
from tools.indicators import IndicatorError, fetch_technical_snapshot
from tools.upbit_client import UpbitClient


class AnalysisWorker:
    """
    시장·기술적·매크로 데이터를 수집하고 종합 점수로 ADD_BUY 신호를 생성한다.

    업비트 DCA(4시간 4만원)와 별도. 매도 신호는 생성하지 않는다.
    """

    def __init__(self, ticker: str = "KRW-BTC") -> None:
        self.ticker = ticker
        self.engine = TriggerEngine()

    def run_watch(self) -> WatchResult:
        """감시 1회: 수집 -> 종합점수 -> (조건 시) ADD_BUY 신호."""
        result = WatchResult()
        settings = get_settings()

        try:
            snapshot = collect_market_snapshot(self.ticker)
            data = snapshot.to_dict()
            onchain = fetch_onchain_metrics().to_dict()
            data["onchain"] = onchain

            snapshot_id = save_market_snapshot(data)
            result.snapshot_id = snapshot_id

            metrics = self._build_metrics(snapshot_id, data, onchain)
            metrics.update(self._fetch_account_metrics())
            result.metrics = metrics
            self._persist_metrics(snapshot_id, metrics)

            trigger = self.engine.evaluate(metrics)
            if trigger.score_result:
                metrics["score"] = trigger.score_result
            result.metrics = metrics
            result.trigger_reason = trigger.reason

            if not trigger.fired or trigger.trigger_type != "ADD_BUY":
                return result

            if has_pending_signal("ADD_BUY"):
                return result

            if has_recent_signal("ADD_BUY", settings.signal_cooldown_hours):
                return result

            signal_id = create_signal(
                trigger_type="ADD_BUY",
                reason=trigger.reason,
                snapshot_id=snapshot_id,
                priority=trigger.priority,
                metrics=metrics,
            )
            result.signal_id = signal_id
            result.signal_created = True
            result.trigger_type = "ADD_BUY"
            result.trigger_reason = trigger.reason

            score = (metrics.get("score") or {}).get("total_score")
            score_txt = f" (종합 점수 {score:.1f}점)" if isinstance(score, (int, float)) else ""
            notify_user(
                "추가 매수 신호가 생겼어요",
                f"시장 조건이 맞아 신호를 등록했습니다{score_txt}.\n"
                "매매 배치가 곧 검토할 예정이에요.",
                kind="signal",
            )

        except (MarketDataError, IndicatorError) as exc:
            result.errors.append(f"[AnalysisWorker] {exc}")

        return result

    def run(self, state: PipelineState) -> PipelineState:
        watch = self.run_watch()
        state.snapshot_id = watch.snapshot_id
        state.signal_id = watch.signal_id
        state.signal_created = watch.signal_created
        state.market_snapshot = watch.metrics
        state.errors.extend(watch.errors)
        return state

    def _build_metrics(
        self,
        snapshot_id: int,
        data: dict[str, Any],
        onchain: dict[str, Any],
    ) -> dict[str, Any]:
        """종합 분석용 metrics."""
        prev = get_previous_market_snapshot(snapshot_id)
        btc_change = None
        usd_change = None
        if prev:
            if prev["btc_krw"]:
                btc_change = (data["btc_krw"] - prev["btc_krw"]) / prev["btc_krw"] * 100
            if prev["usd_krw"]:
                usd_change = (data["usd_krw"] - prev["usd_krw"]) / prev["usd_krw"] * 100

        technical = fetch_technical_snapshot(self.ticker).to_dict()

        return {
            "snapshot_id": snapshot_id,
            "captured_at": data["captured_at"],
            "usd_krw": data["usd_krw"],
            "btc_krw": data["btc_krw"],
            "btc_usd_implied": data["btc_usd_implied"],
            "btc_usd_binance": data.get("btc_usd_binance"),
            "kimchi_premium_pct": data.get("kimchi_premium_pct"),
            "btc_krw_change_pct": btc_change,
            "usd_krw_change_pct": usd_change,
            "onchain": onchain,
            "technical": technical,
        }

    def _fetch_account_metrics(self) -> dict[str, Any]:
        try:
            summary = UpbitClient().get_account_summary()
            return {
                "krw_available": summary.krw_balance,
                "total_eval_amount": summary.total_eval_amount,
            }
        except Exception:  # noqa: BLE001
            return {}

    def _persist_metrics(self, snapshot_id: int, metrics: dict[str, Any]) -> None:
        base = {"captured_at": metrics["captured_at"]}
        for key in ("usd_krw", "btc_krw", "btc_usd_implied", "kimchi_premium_pct"):
            val = metrics.get(key)
            if val is not None:
                save_metric(snapshot_id, key, float(val), {**base, "value": val})
        ta = metrics.get("technical") or {}
        if ta.get("rsi_14") is not None:
            save_metric(snapshot_id, "rsi_14", float(ta["rsi_14"]), {**base, **ta})
