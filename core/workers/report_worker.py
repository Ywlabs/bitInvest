"""정산 Worker — 일자별 성과 보고서 생성."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config import get_settings
from core.state import PipelineState
from core.strategy.budget import MonthlyBudget
from core.strategy.scoring import CompositeScorer
from services.exchange_rate import collect_market_snapshot
from services.market_store import (
    get_latest_market_snapshot,
    get_latest_trade_decision,
    get_latest_trading_signal,
    save_daily_report,
    write_report_file,
)
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
        """리포트용 종합 분석 (DB score 없으면 실시간 재계산)."""
        score = market.get("score")
        technical = market.get("technical")

        if score and technical:
            return {"score": score, "technical": technical, "live_recomputed": False}

        settings = get_settings()
        try:
            snap = collect_market_snapshot(settings.default_ticker).to_dict()
            onchain = fetch_onchain_metrics().to_dict()
            if not technical:
                technical = fetch_technical_snapshot(settings.default_ticker).to_dict()
            metrics = {
                "captured_at": snap["captured_at"],
                "usd_krw": snap["usd_krw"],
                "btc_krw": snap["btc_krw"],
                "btc_usd_implied": snap["btc_usd_implied"],
                "kimchi_premium_pct": snap.get("kimchi_premium_pct"),
                "onchain": onchain,
                "technical": technical,
            }
            if not score:
                score = CompositeScorer(settings).score(metrics).to_dict()
            return {"score": score, "technical": technical, "live_recomputed": True}
        except Exception as exc:  # noqa: BLE001
            return {
                "score": score or {},
                "technical": technical or {},
                "live_recomputed": False,
                "error": str(exc),
            }

    def _analysis_lines(self, analysis: dict[str, Any]) -> list[str]:
        """종합 분석 섹션 텍스트."""
        settings = get_settings()
        budget = MonthlyBudget(settings)
        score = analysis.get("score") or {}
        technical = analysis.get("technical") or {}

        lines = [
            "[종합 분석 (ADD_BUY)]",
        ]
        if analysis.get("live_recomputed"):
            lines.append("  (리포트 생성 시점 실시간 재계산)")
        if analysis.get("error"):
            lines.append(f"  분석 오류      : {analysis['error']}")

        lines.extend(
            [
                f"  종합 점수       : {score.get('total_score', '-')} / {score.get('max_possible', 12)}",
                f"  최소 기준       : {settings.add_buy_min_score} 점",
                f"  ADD_BUY 권장    : {'예' if score.get('recommend_add_buy') else '아니오'}",
                f"  권장 추가매수   : {score.get('recommended_krw', 0):,.0f} KRW",
                f"  신뢰도          : {score.get('confidence', 0):.2f}",
            ]
        )

        block_reasons = score.get("block_reasons") or []
        if block_reasons:
            lines.append(f"  보류 사유       : {', '.join(block_reasons)}")

        def _fmt_num(val: Any, fmt: str = ".2f") -> str:
            if val is None or val == "-":
                return "-"
            try:
                return format(float(val), fmt)
            except (TypeError, ValueError):
                return str(val)

        lines.extend(
            [
                "",
                "  [기술적 지표]",
                f"    RSI(14)       : {_fmt_num(technical.get('rsi_14'), '.1f')}",
                f"    MACD hist     : {_fmt_num(technical.get('macd_hist'), ',.0f')}",
                f"    7일 수익률    : {_fmt_num(technical.get('return_7d_pct'))}%",
                f"    30일 수익률   : {_fmt_num(technical.get('return_30d_pct'))}%",
                f"    200MA 이격    : {_fmt_num(technical.get('dist_ma200_pct'))}%",
                "",
                "  [점수 요인]",
            ]
        )

        breakdown = score.get("breakdown") or []
        if breakdown:
            for item in breakdown:
                lines.append(
                    f"    +{item.get('points', 0):.1f} {item.get('factor', '')}: {item.get('reason', '')}"
                )
        else:
            lines.append("    (가점 요인 없음)")

        lines.extend(
            [
                "",
                "  [월 추가매수 예산]",
                f"    월 한도        : {budget.monthly_limit:,.0f} KRW",
                f"    이번 달 사용   : {budget.spent_this_month():,.0f} KRW",
                f"    이번 달 잔여   : {budget.remaining():,.0f} KRW",
                "",
            ]
        )
        return lines

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

        lines = [
            "=" * 50,
            f"  일일 성과 보고서  {report_date}",
            "=" * 50,
            "",
            "[시장 스냅샷]",
            f"  수집 시각       : {market.get('captured_at', '-')}",
            f"  USD/KRW         : {market.get('usd_krw', 0):,.2f}",
            f"  BTC/KRW (업비트): {market.get('btc_krw', 0):,.0f}",
            f"  BTC/USD (환산)  : {market.get('btc_usd_implied', 0):,.2f}",
        ]
        kimchi = market.get("kimchi_premium_pct")
        if kimchi is not None:
            lines.append(f"  김치 프리미엄   : {kimchi:+.2f}%")

        lines.append("")
        lines.extend(self._analysis_lines(analysis))

        lines.extend(
            [
                "[계좌 현황]",
                f"  원화 잔고       : {account.get('krw_balance', 0):,.0f} KRW",
                f"  원화 잠금       : {account.get('krw_locked', 0):,.0f} KRW",
                f"  총 평가액       : {account.get('total_eval_amount', 0):,.0f} KRW",
                f"  코인 손익       : {account.get('total_pnl', 0):+,.0f} KRW "
                f"({account.get('total_pnl_rate', 0):+.2f}%)",
            ]
        )

        holdings = account.get("holdings") or []
        if holdings:
            lines.append("  보유 코인:")
            for h in holdings:
                lines.append(
                    f"    - {h.get('currency', '?')}: "
                    f"{h.get('total', 0):.8f} (평단 {h.get('avg_buy_price', 0):,.0f})"
                )

        lines.extend(
            [
                "",
                "[신호 / 매매 실행]",
                f"  신호 ID         : {state.signal_id or '-'}",
                f"  신호 사유       : {state.trigger_reason or decision.get('reason', '-')}",
                f"  결정            : {decision.get('action', '-')}",
                f"  추가매수 금액   : {decision.get('buy_amount_krw', 0):,.0f} KRW",
                f"  판단 사유       : {decision.get('reason', '-')}",
                f"  DRY_RUN         : {decision.get('dry_run', True)}",
                "",
                "=" * 50,
            ]
        )

        if state.errors:
            lines.extend(["", "[오류]", *[f"  - {e}" for e in state.errors]])

        file_path = write_report_file(report_date, lines)
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
        }
        report_id = save_daily_report(report_date, content, str(file_path))
        state.report_id = report_id
        state.report_path = str(file_path)
        state.market_snapshot = {**market, "score": analysis.get("score"), "technical": analysis.get("technical")}
        return state
