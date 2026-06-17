"""배치·Worker 실행 이력 컨텍스트 로거."""

from __future__ import annotations

import time
from types import TracebackType
from typing import Any

from services.desktop_notify import notify_user
from services.job_log_store import begin_job_run, complete_job_run


class JobLogger:
    """배치 1회 실행을 market.db job_runs 에 기록한다."""

    def __init__(self, job_name: str) -> None:
        self.job_name = job_name
        self.run_id: int | None = None
        self.summary = ""
        self.detail: dict[str, Any] = {}
        self.error_text = ""
        self._exit_code = 0
        self._started = 0.0

    def set_summary(self, text: str) -> None:
        self.summary = text

    def set_detail(self, data: dict[str, Any]) -> None:
        self.detail = data

    def set_exit_code(self, code: int) -> None:
        self._exit_code = code

    def __enter__(self) -> JobLogger:
        self.run_id = begin_job_run(self.job_name)
        self._started = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        duration_ms = int((time.perf_counter() - self._started) * 1000)
        if exc_type is not None:
            self._exit_code = 1
            self.error_text = str(exc_val)
            status = "failed"
        elif self._exit_code != 0:
            status = "failed"
        else:
            status = "success"

        if self.run_id is not None:
            complete_job_run(
                self.run_id,
                exit_code=self._exit_code,
                status=status,
                summary=self.summary,
                detail=self.detail,
                error_text=self.error_text,
                duration_ms=duration_ms,
            )

        self._maybe_notify(status, duration_ms)
        return False

    def _maybe_notify(self, status: str, duration_ms: int) -> None:
        if status == "success" and self._skip_success_notify():
            return

        title, body = self._friendly_message(status)
        if not body:
            return

        kind = "error" if status == "failed" else "batch"
        open_path = None
        if self.job_name == "report" and status == "success":
            open_path = self.detail.get("report_path")

        notify_user(
            title,
            body,
            kind=kind,
            job_name=self.job_name,
            open_path=open_path,
        )

    def _skip_success_notify(self) -> bool:
        """의미 없는 완료(대기 신호 없음 등)는 알림 생략."""
        if self.job_name != "trading":
            return False
        return bool(self.detail.get("skipped"))

    def _friendly_message(self, status: str) -> tuple[str, str]:
        if status == "failed":
            return self._friendly_failure()

        builders = {
            "analysis": self._friendly_analysis_success,
            "trading": self._friendly_trading_success,
            "report": self._friendly_report_success,
        }
        builder = builders.get(self.job_name)
        if builder:
            return builder()
        return ("bitInvest 알림", self.summary or "작업이 끝났습니다.")

    def _friendly_failure(self) -> tuple[str, str]:
        labels = {
            "analysis": "시장 분석",
            "trading": "매매 처리",
            "report": "리포트 작성",
        }
        label = labels.get(self.job_name, "작업")
        err = self.error_text or self.summary or "알 수 없는 오류"
        return (
            f"bitInvest — {label} 중 문제 발생",
            f"잠시 후 다시 실행해 보시거나 로그를 확인해 주세요.\n{err}",
        )

    def _friendly_analysis_success(self) -> tuple[str, str]:
        if self.detail.get("signal_created"):
            reason = self.detail.get("trigger_reason") or ""
            extra = f"\n{reason}" if reason else ""
            return (
                "추가 매수 신호가 생겼어요",
                "종합 점수 조건을 만족했습니다. 곧 매매 배치가 검토할 예정이에요."
                + extra,
            )
        return (
            "시장 분석을 마쳤어요",
            "지금은 추가 매수 조건에 해당하지 않습니다. 평소처럼 DCA는 그대로 진행됩니다.",
        )

    def _friendly_trading_success(self) -> tuple[str, str]:
        action = self.detail.get("action", "")
        amount = float(self.detail.get("buy_amount_krw") or 0)
        dry_run = self.detail.get("dry_run", True)
        executed = self.detail.get("executed", False)
        reason = self.summary or ""

        if action == "ADD_BUY" and amount > 0:
            if dry_run:
                return (
                    "추가 매수 조건 충족 (모의 실행)",
                    f"약 {amount:,.0f}원 규모로 매수할 만한 상황입니다.\n"
                    "DRY_RUN 모드라 실제 주문은 넣지 않았어요.",
                )
            if executed:
                return (
                    "비트코인 추가 매수 주문을 넣었어요",
                    f"약 {amount:,.0f}원 시장가 매수를 접수했습니다.\n업비트 앱에서 체결 여부를 확인해 주세요.",
                )
            return (
                "추가 매수를 검토했어요",
                f"약 {amount:,.0f}원 규모 매수 판단입니다.\n{reason}",
            )

        return (
            "이번에는 추가 매수하지 않아요",
            "신호는 있었지만 예산·점수·잔고 등을 보고 관망하기로 했습니다.",
        )

    def _friendly_report_success(self) -> tuple[str, str]:
        return (
            "오늘 투자 리포트가 준비됐어요",
            "알림을 누르거나 「리포트 열기」를 눌러 브라우저에서 대시보드를 확인하세요.",
        )
