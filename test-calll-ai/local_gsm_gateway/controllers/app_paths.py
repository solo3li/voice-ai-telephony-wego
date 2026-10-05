"""App paths resolver for writable storage directory across OS platforms.

Ensures databases and user session files are saved to the user's
writable AppData/Home directory and never inside read-only package bundles
(such as serious_python, PyInstaller, or Program Files).
"""
import os
import sys
import tempfile
import logging

logger = logging.getLogger(__name__)


def get_app_data_dir() -> str:
    """Return an OS-specific, writable directory for application data."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "VoiceAIGateway")
    elif sys.platform == "darwin":
        data_dir = os.path.expanduser("~/Library/Application Support/VoiceAIGateway")
    elif sys.platform == "android":
        base = os.environ.get("HOME") or os.environ.get("TMPDIR") or "/data/data/com.voiceai.employee/files"
        data_dir = os.path.join(base, "VoiceAIGateway")
    else:
        # Linux / Posix
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        data_dir = os.path.join(base, "voice_ai_gateway")

    try:
        os.makedirs(data_dir, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create preferred app data dir '{data_dir}': {e}. Falling back to tempdir.")
        data_dir = os.path.join(tempfile.gettempdir(), "voice_ai_gateway")
        os.makedirs(data_dir, exist_ok=True)

    return data_dir


def get_writable_file_path(filename: str) -> str:
    """Return full path for a file inside the user's writable AppData directory."""
    return os.path.join(get_app_data_dir(), filename)
