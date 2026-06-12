"""매매 Worker — ADD_BUY(추가 매수)만 실행. 매도 없음."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from config import get_settings
from core.state import PipelineState
from core.strategy.budget import MonthlyBudget
from services.market_store import get_market_snapshot, save_trade_decision
from services.signal_store import (
    SIGNAL_DONE,
    SIGNAL_REJECTED,
    claim_next_pending_signal,
    complete_signal,
)
from tools.upbit_client import UpbitClient, UpbitConnectionError


class TradingWorker:
    """ADD_BUY 신호만 처리. 10년 보유 전략 — SELL 비활성."""

    def run_consumer(self) -> PipelineState:
        state = PipelineState()
        signal = claim_next_pending_signal()
        if signal is None:
            state.skipped = True
            state.skip_reason = "처리할 pending 신호 없음"
            return state

        state.signal_id = int(signal["id"])
        state.snapshot_id = int(signal["snapshot_id"])

        try:
            state = self._process_signal(state, signal)
            action = (state.trading_decision or {}).get("action", "HOLD")
            if action == "ADD_BUY":
                complete_signal(state.signal_id, SIGNAL_DONE, f"추가매수 판단: {action}")
            else:
                complete_signal(state.signal_id, SIGNAL_REJECTED, "관망")
        except (UpbitConnectionError, KeyError) as exc:
            state.errors.append(f"[TradingWorker] {exc}")
            if state.signal_id:
                complete_signal(state.signal_id, SIGNAL_REJECTED, str(exc))

        return state

    def run(self, state: PipelineState) -> PipelineState:
        if state.signal_id:
            from services.signal_store import get_signal

            return self._process_signal(state, get_signal(state.signal_id))

        if state.snapshot_id and not state.signal_created:
            return self._process_signal(
                state,
                {
                    "id": None,
                    "snapshot_id": state.snapshot_id,
                    "trigger_type": "MANUAL",
                    "reason": "수동 테스트",
                    "metrics_json": "{}",
                },
            )

        return self.run_consumer()

    def _process_signal(self, state: PipelineState, signal: dict) -> PipelineState:
        settings = get_settings()
        if settings.strategy_sell_enabled:
            state.errors.append("[TradingWorker] SELL 은 비활성 권장 — STRATEGY_SELL_ENABLED 확인")

        snapshot = get_market_snapshot(int(signal["snapshot_id"]))
        metrics = json.loads(signal.get("metrics_json") or "{}")
        score = metrics.get("score") or {}

        client = UpbitClient(settings)
        client.test_connection()
        summary = client.get_account_summary()
        account_dict = {
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
        state.account_summary = account_dict
        state.market_snapshot = {
            "usd_krw": snapshot["usd_krw"],
            "btc_krw": snapshot["btc_krw"],
            "btc_usd_implied": snapshot["btc_usd_implied"],
            "kimchi_premium_pct": snapshot.get("kimchi_premium_pct"),
            "captured_at": snapshot["captured_at"],
            "score": score,
        }

        action, reason, confidence, buy_krw = self._decide_add_buy(
            account_dict, score, signal.get("trigger_type", "")
        )

        decision = {
            "decided_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "snapshot_id": state.snapshot_id,
            "signal_id": state.signal_id,
            "trigger_type": signal.get("trigger_type"),
            "action": action,
            "buy_amount_krw": buy_krw,
            "reason": reason,
            "confidence": confidence,
            "dry_run": settings.dry_run,
            "score": score,
            "market": state.market_snapshot,
            "account_summary": account_dict,
        }

        if action == "ADD_BUY" and not settings.dry_run:
            decision["executed"] = False
            decision["execution_note"] = "실주문 API 미구현 — DRY_RUN 권장"

        if action == "ADD_BUY" and buy_krw > 0 and not settings.dry_run:
            MonthlyBudget(settings).record(buy_krw, note=f"signal={state.signal_id}")

        save_trade_decision(decision)
        state.trading_decision = decision
        return state

    def _decide_add_buy(
        self,
        account: dict,
        score: dict,
        trigger_type: str,
    ) -> tuple[str, str, float, float]:
        """종합 점수 + 월 예산 기반 추가 매수 판단."""
        settings = get_settings()
        budget = MonthlyBudget(settings)
        krw = account["krw_balance"]

        recommended = float(score.get("recommended_krw") or 0)
        total_score = float(score.get("total_score") or 0)

        if trigger_type != "ADD_BUY" and trigger_type != "MANUAL":
            return ("HOLD", f"ADD_BUY 외 신호 무시 ({trigger_type})", 0.0, 0.0)

        if score.get("blocked"):
            reasons = ", ".join(score.get("block_reasons") or [])
            return ("HOLD", f"종합분석 보류: {reasons}", 0.0, 0.0)

        if total_score < settings.add_buy_min_score:
            return (
                "HOLD",
                f"종합점수 부족 ({total_score:.1f} < {settings.add_buy_min_score})",
                0.0,
                0.0,
            )

        buy_krw = recommended if recommended > 0 else budget.allocate_for_score(total_score)
        if buy_krw <= 0:
            return ("HOLD", "월 추가매수 예산 소진 또는 금액 산정 불가", 0.0, 0.0)

        if krw < buy_krw:
            buy_krw = min(krw, buy_krw)
            if buy_krw < settings.add_buy_min_order_krw:
                return ("HOLD", f"가용 원화 부족 ({krw:,.0f}원)", 0.0, 0.0)

        if not budget.can_spend(buy_krw):
            return ("HOLD", f"월 한도 초과 (잔여 {budget.remaining():,.0f}원)", 0.0, 0.0)

        return (
            "ADD_BUY",
            f"종합점수 {total_score:.1f} | 추가매수 {buy_krw:,.0f}원 "
            f"(월 잔여 {budget.remaining():,.0f}원)",
            float(score.get("confidence") or 0.6),
            buy_krw,
        )
