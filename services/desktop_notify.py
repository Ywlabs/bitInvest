"""Windows 데스크톱 토스트 알림."""

from __future__ import annotations

import base64
import logging
import sys
from pathlib import Path
from typing import Literal

from config import get_settings

logger = logging.getLogger(__name__)

NotifyKind = Literal["batch", "signal", "buy", "error", "info"]

_APP_ID = "YW Labs.bitInvest"
_MAX_MSG_LEN = 240


def notify_user(
    title: str,
    message: str,
    *,
    kind: NotifyKind = "info",
    job_name: str | None = None,
    open_path: str | Path | None = None,
) -> bool:
    """
    Windows 알림 표시.

    open_path: 토스트(또는 버튼) 클릭 시 열 파일 경로 (winotify 전용).

    kind별 .env 스위치:
    - batch: NOTIFY_ON_BATCH_{ANALYSIS|TRADING|REPORT} (job_name 필요)
    - signal: NOTIFY_ON_SIGNAL
    - buy: NOTIFY_ON_BUY
    - error: NOTIFY_ON_ERROR + 해당 job 배치 알림 ON
    """
    settings = get_settings()
    if not settings.notify_enabled:
        return False
    if sys.platform != "win32":
        return False

    if kind == "batch":
        if not job_name or not settings.is_batch_notify_enabled(job_name):
            return False
    if kind == "signal" and not settings.notify_on_signal:
        return False
    if kind == "buy" and not settings.notify_on_buy:
        return False
    if kind == "error":
        if not settings.notify_on_error:
            return False
        if job_name and not settings.is_batch_notify_enabled(job_name):
            return False

    title = _truncate(title, 64)
    message = _truncate(message, _MAX_MSG_LEN)
    file_uri = _to_file_uri(open_path)

    if _notify_winotify(title, message, file_uri=file_uri):
        return True
    if _notify_powershell_balloon(title, message):
        return True

    logger.warning("데스크톱 알림 표시 실패: %s", title)
    return False


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _to_file_uri(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            return ""
        return resolved.as_uri()
    except OSError:
        return ""


def _notify_winotify(title: str, message: str, *, file_uri: str = "") -> bool:
    try:
        from winotify import Notification, audio
    except ImportError:
        return False

    try:
        toast = Notification(
            app_id=_APP_ID,
            title=title,
            msg=message,
            duration="short",
            launch=file_uri,
        )
        toast.set_audio(audio.Default, loop=False)
        if file_uri:
            toast.add_actions("브라우저에서 열기", file_uri)
        toast.show()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("winotify 실패: %s", exc)
        return False


def _notify_powershell_balloon(title: str, message: str) -> bool:
    """winotify 미설치 시 트레이 풍선 알림 폴백."""
    import subprocess

    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(10000, '{_ps_escape(title)}', '{_ps_escape(message)}', [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Milliseconds 800
$n.Visible = $false
$n.Dispose()
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=15,
            check=False,
        )
        return proc.returncode == 0
    except Exception as exc:  # noqa: BLE001
        logger.debug("PowerShell 알림 실패: %s", exc)
        return False


def _ps_escape(text: str) -> str:
    return text.replace("'", "''")
