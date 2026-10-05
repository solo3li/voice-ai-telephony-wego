"""API Client for interacting with Cloud Voice Assistant Backend.

Handles owner authentication (strictly username and password, no email),
session persistence for Auto-Login, and call orchestration.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
import requests
import tempfile

try:
    from controllers.app_paths import get_writable_file_path
except ImportError:
    try:
        from app_paths import get_writable_file_path
    except ImportError:
        def get_writable_file_path(name: str) -> str:
            return os.path.join(tempfile.gettempdir(), name)

logger = logging.getLogger(__name__)

SESSION_FILE = get_writable_file_path("session.json")
DEFAULT_SERVER_URL = "https://app.169.58.32.179.nip.io"


class DongleApiClient:
    def __init__(self, server_url: str = DEFAULT_SERVER_URL):
        self.server_url = server_url.rstrip("/")
        self.token: Optional[str] = None
        self.user_data: Optional[Dict[str, Any]] = None
        self.active_profile: Optional[Dict[str, Any]] = None
        self.livekit_url: Optional[str] = None
        self.load_session()

    def set_server_url(self, url: str):
        self.server_url = url.rstrip("/")

    def login(self, username: str, password: str, remember: bool = True) -> Dict[str, Any]:
        """Authenticate business owner using strictly username and password (NO email)."""
        url = f"{self.server_url}/api/v1/dongle/auth/login/"
        payload = {
            "username": username.strip(),
            "password": password.strip()
        }
        try:
            resp = requests.post(url, json=payload, timeout=12, verify=False)
            data = resp.json()
            if resp.status_code == 200 and data.get("status") == "success":
                self.token = data.get("token")
                self.user_data = data.get("user")
                self.active_profile = data.get("active_profile")
                self.livekit_url = data.get("livekit_url")
                if remember:
                    self.save_session()
                return {"success": True, "data": data}
            else:
                msg = data.get("message", "فشل تسجيل الدخول، يرجى مراجعة البيانات")
                return {"success": False, "error": msg}
        except Exception as e:
            logger.error(f"Login request failed: {e}")
            return {"success": False, "error": f"تعذر الاتصال بالسيرفر: {str(e)}"}

    def init_call(self, caller_phone: str, dongle_id: str = "dongle_main") -> Dict[str, Any]:
        """Request LiveKit WebRTC room and tokens for an incoming cellular call."""
        if not self.token:
            return {"success": False, "error": "غير مسجل الدخول"}

        url = f"{self.server_url}/api/v1/dongle/call/"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "caller_phone": caller_phone,
            "dongle_id": dongle_id
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10, verify=False)
            data = resp.json()
            if resp.status_code == 200 and data.get("status") == "success":
                return {"success": True, "data": data}
            return {"success": False, "error": data.get("message", "فشل بدء المكالمة")}
        except Exception as e:
            logger.error(f"Call init request failed: {e}")
            return {"success": False, "error": f"خطأ اتصال بالسيرفر: {str(e)}"}

    def hangup_call(self, room_name: str, duration_seconds: int = 0, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Notify cloud backend that call ended to record duration and session."""
        if not self.token:
            return {"success": False, "error": "غير مسجل الدخول"}

        url = f"{self.server_url}/api/v1/dongle/hangup/"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "room_name": room_name,
            "duration_seconds": duration_seconds,
            "session_id": session_id
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=8, verify=False)
            return {"success": resp.status_code == 200}
        except Exception as e:
            logger.error(f"Hangup request failed: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Verify token and get live cloud status."""
        if not self.token:
            return {"success": False, "error": "غير مسجل الدخول"}

        url = f"{self.server_url}/api/v1/dongle/status/"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=8, verify=False)
            data = resp.json()
            if resp.status_code == 200:
                return {"success": True, "data": data}
            return {"success": False, "error": data.get("message", "غير مصرح")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_session(self):
        """Persist session token for auto-login."""
        try:
            content = {
                "server_url": self.server_url,
                "token": self.token,
                "user_data": self.user_data,
                "active_profile": self.active_profile,
                "livekit_url": self.livekit_url,
            }
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Could not save session: {e}")

    def load_session(self) -> bool:
        """Load saved session token if available."""
        if not os.path.exists(SESSION_FILE):
            return False
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.server_url = data.get("server_url", self.server_url)
            self.token = data.get("token")
            self.user_data = data.get("user_data")
            self.active_profile = data.get("active_profile")
            self.livekit_url = data.get("livekit_url")
            return bool(self.token)
        except Exception as e:
            logger.warning(f"Failed to read session file: {e}")
            return False

    def clear_session(self):
        """Logout and wipe saved session."""
        self.token = None
        self.user_data = None
        self.active_profile = None
        if os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
            except Exception:
                pass
