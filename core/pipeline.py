"""Agent Worker 파이프라인 오케스트레이터."""

from __future__ import annotations

from core.state import PipelineState, WatchResult
from core.workers import AnalysisWorker, ReportWorker, TradingWorker


class AgentPipeline:
    """
    이벤트 기반 Worker 오케스트레이터.

    - run_watch(): Analysis 감시만 (신호 생성)
    - run_trading_consumer(): pending 신호만 처리
    - run_report(): 일일 리포트
    - run_full(): 통합 테스트 (watch + consumer + report)
    """

    def __init__(self, ticker: str = "KRW-BTC") -> None:
        self.analysis = AnalysisWorker(ticker=ticker)
        self.trading = TradingWorker()
        self.report = ReportWorker()

    def run_watch(self) -> WatchResult:
        """AnalysisWorker 감시 1회."""
        return self.analysis.run_watch()

    def run_trading_consumer(self) -> PipelineState:
        """pending trading signal 1건 소비."""
        return self.trading.run_consumer()

    def run_report(self, state: PipelineState | None = None) -> PipelineState:
        """일일 성과 보고서."""
        state = state or PipelineState()
        return self.report.run(state)

    def run_full(self, *, force_trading: bool = False) -> PipelineState:
        """
        통합 실행 (테스트용).

        force_trading=True 이면 신호 없어도 snapshot 기준 Trading 시도.
        """
        state = PipelineState()
        watch = self.analysis.run_watch()
        state.snapshot_id = watch.snapshot_id
        state.signal_id = watch.signal_id
        state.signal_created = watch.signal_created
        state.market_snapshot = watch.metrics
        state.errors.extend(watch.errors)

        if not state.ok:
            return state

        if watch.signal_created or force_trading:
            trade_state = self.trading.run(state)
            state.trading_decision = trade_state.trading_decision
            state.account_summary = trade_state.account_summary
            state.errors.extend(trade_state.errors)
            state.skipped = trade_state.skipped
        else:
            state.skipped = True
            state.skip_reason = "트리거 미충족 - TradingWorker 스킵"

        return self.report.run(state)

    def run(self) -> PipelineState:
        """하위 호환: run_full(force_trading=True)."""
        return self.run_full(force_trading=True)
