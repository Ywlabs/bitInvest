"""Worker 파이프라인 공유 상태."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineState:
    """Worker 간 이관용 상태."""

    snapshot_id: int | None = None
    signal_id: int | None = None
    signal_created: bool = False
    market_snapshot: dict[str, Any] | None = None
    trading_decision: dict[str, Any] | None = None
    account_summary: dict[str, Any] | None = None
    report_id: int | None = None
    report_path: str | None = None
    skipped: bool = False
    skip_reason: str = ""
    trigger_reason: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """치명적 오류 없이 진행 가능한지."""
        return len(self.errors) == 0


@dataclass
class WatchResult:
    """AnalysisWorker 감시 1회 실행 결과."""

    snapshot_id: int | None = None
    signal_id: int | None = None
    signal_created: bool = False
    trigger_type: str | None = None
    trigger_reason: str = ""
    metrics: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0
