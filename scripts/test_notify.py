"""Windows 알림 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.desktop_notify import notify_user  # noqa: E402


def _latest_report() -> Path | None:
    reports = ROOT / "reports"
    if not reports.is_dir():
        return None
    files = sorted(reports.glob("report_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def main() -> int:
    report = _latest_report()
    ok = notify_user(
        "bitInvest 알림 테스트",
        "알림 본문을 누르거나 「리포트 열기」로 최신 리포트를 열 수 있어요.",
        kind="info",
        open_path=report,
    )
    print("알림 전송:", "성공" if ok else "실패")
    if report:
        print("연결 파일:", report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
