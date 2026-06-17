"""배치·Worker 실행 이력 컨텍스트 로거."""

from __future__ import annotations

import time
from types import TracebackType
from typing import Any

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
        return False
