"""정산 Worker — 일자별 성과 보고서 생성."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config import get_settings
from core.state import PipelineState
from core.strategy.scoring import CompositeScorer
from services.exchange_rate import collect_market_snapshot
from services.market_store import (
    get_latest_market_snapshot,
    get_latest_trade_decision,
    get_latest_trading_signal,
    save_daily_report,
    write_report_html,
)
from services.daily_summary import build_daily_summary
from services.report_html import render_daily_report
from services.onchain_client import fetch_onchain_metrics
from tools.indicators import fetch_technical_snapshot
from tools.upbit_client import UpbitClient, UpbitConnectionError


class ReportWorker:
    """당일 파이프라인 결과 + 종합 분석을 일일 성과 보고서로 정리한다."""

    def build_state_from_db(self, *, refresh_account: bool = True) -> PipelineState:
        """SQLite 최신 데이터 + 신호 metrics 로 state 구성."""
        state = PipelineState()
        snapshot = get_latest_market_snapshot()
        if snapshot:
            state.snapshot_id = int(snapshot["id"])
            raw = json.loads(snapshot.get("raw_json") or "{}")
            state.market_snapshot = {
                "captured_at": snapshot["captured_at"],
                "usd_krw": snapshot["usd_krw"],
                "btc_krw": snapshot["btc_krw"],
                "btc_usd_implied": snapshot["btc_usd_implied"],
                "kimchi_premium_pct": snapshot.get("kimchi_premium_pct"),
                "btc_usd_binance": raw.get("btc_usd_binance"),
            }

        trade = get_latest_trade_decision()
        if trade:
            state.trading_decision = json.loads(trade["raw_json"])
            state.account_summary = json.loads(trade["account_json"])
            if trade.get("signal_id"):
                state.signal_id = int(trade["signal_id"])
            score = (state.trading_decision or {}).get("score")
            if score and state.market_snapshot is not None:
                state.market_snapshot["score"] = score

        signal = get_latest_trading_signal()
        if signal:
            state.signal_created = signal["status"] in ("pending", "processing", "done")
            if state.signal_id is None:
                state.signal_id = int(signal["id"])
            metrics = json.loads(signal.get("metrics_json") or "{}")
            if state.market_snapshot is None:
                state.market_snapshot = {}
            if metrics.get("score"):
                state.market_snapshot["score"] = metrics["score"]
            if metrics.get("technical"):
                state.market_snapshot["technical"] = metrics["technical"]
            state.trigger_reason = signal.get("reason", "")

        if refresh_account or not state.account_summary:
            state.account_summary = self._fetch_live_account(state.account_summary)

        return state

    def _fetch_live_account(self, existing: dict | None) -> dict:
        try:
            summary = UpbitClient().get_account_summary()
            return {
                "krw_balance": summary.krw_balance,
                "krw_locked": summary.krw_locked,
                "total_eval_amount": summary.total_eval_amount,
                "total_pnl": summary.total_pnl,
                "total_pnl_rate": summary.total_pnl_rate,
                "holdings": [
                    {
                        "currency": h.currency,
                        "total": h.total,
                        "avg_buy_price": h.avg_buy_price,
                    }
                    for h in summary.holdings
                ],
            }
        except UpbitConnectionError:
            return existing or {}

    def _resolve_analysis(self, market: dict) -> dict[str, Any]:
        """리포트용 종합 분석 (technical 있으면 점수 재계산)."""
        score = market.get("score")
        technical = market.get("technical")

        settings = get_settings()
        try:
            if not technical:
                technical = fetch_technical_snapshot(settings.default_ticker).to_dict()
            snap = market if market.get("btc_krw") else collect_market_snapshot(settings.default_ticker).to_dict()
            onchain = fetch_onchain_metrics().to_dict()
            metrics = {
                "captured_at": snap.get("captured_at") or market.get("captured_at"),
                "usd_krw": snap.get("usd_krw") or market.get("usd_krw"),
                "btc_krw": snap.get("btc_krw") or market.get("btc_krw"),
                "btc_usd_implied": snap.get("btc_usd_implied") or market.get("btc_usd_implied"),
                "kimchi_premium_pct": snap.get("kimchi_premium_pct") or market.get("kimchi_premium_pct"),
                "onchain": onchain,
                "technical": technical,
            }
            score = CompositeScorer(settings).score(metrics).to_dict()
            return {"score": score, "technical": technical, "live_recomputed": True}
        except Exception as exc:  # noqa: BLE001
            return {
                "score": score or {},
                "technical": technical or {},
                "live_recomputed": False,
                "error": str(exc),
            }

    def run(self, state: PipelineState) -> PipelineState:
        if not state.market_snapshot and not state.account_summary:
            loaded = self.build_state_from_db()
            state.snapshot_id = loaded.snapshot_id
            state.signal_id = loaded.signal_id
            state.signal_created = loaded.signal_created
            state.market_snapshot = loaded.market_snapshot
            state.trading_decision = loaded.trading_decision or state.trading_decision
            state.account_summary = loaded.account_summary

        now = datetime.now(timezone.utc).astimezone()
        report_date = now.strftime("%Y-%m-%d")

        market = state.market_snapshot or {}
        decision = state.trading_decision or {}
        account = state.account_summary or {}
        analysis = self._resolve_analysis(market)
        settings = get_settings()
        daily_summary = build_daily_summary(report_date)

        html_content = render_daily_report(
            report_date=report_date,
            created_at=now.isoformat(),
            market=market,
            analysis=analysis,
            decision=decision,
            account=account,
            signal_id=state.signal_id,
            signal_created=state.signal_created,
            trigger_reason=state.trigger_reason or "",
            errors=state.errors,
            daily_summary=daily_summary,
            settings=settings,
        )

        file_path = write_report_html(report_date, html_content)
        content = {
            "created_at": now.isoformat(),
            "report_date": report_date,
            "signal_id": state.signal_id,
            "signal_created": state.signal_created,
            "analysis": analysis,
            "market_snapshot": market,
            "trading_decision": decision,
            "account_summary": account,
            "errors": state.errors,
            "daily_summary": daily_summary,
        }
        report_id = save_daily_report(report_date, content, str(file_path))
        state.report_id = report_id
        state.report_path = str(file_path)
        state.market_snapshot = {**market, "score": analysis.get("score"), "technical": analysis.get("technical")}
        return state
