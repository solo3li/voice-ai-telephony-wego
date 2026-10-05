"""System Tray Manager for Local GSM Voice AI Gateway.

Provides desktop background system tray integration:
1. Minimizes to system tray when the window close (X) button is pressed.
2. Native tray icon using the brand emblem (assets/icon.png).
3. Dynamic Right-Click Context Menu:
   - Live Status item (e.g., "🟢 متصل | Vodafone 92%" or "📞 مكالمة نشطة")
   - Open / Restore Window ("🖥️ فتح لوحة التحكم")
   - Mute / Pause Gateway ("🔇 كتم الصوت / تعليق البوابة")
   - Exit / Quit completely ("🚪 إغلاق التطبيق نهائياً")
4. Desktop Notifications (Toast/Balloon) for incoming cellular calls & SMS.
5. Headless and multi-platform resilience with safe fallback.
"""
import os
import sys
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Safe import for pystray and Pillow
PYSTRAY_AVAILABLE = False
pystray = None
Image = None

try:
    from PIL import Image as PILImage
    Image = PILImage
    import pystray as _pystray
    # Verify backend doesn't crash on import
    if hasattr(_pystray, "Icon"):
        pystray = _pystray
        PYSTRAY_AVAILABLE = True
except Exception as e:
    logger.info(f"System tray GUI backend not available in current environment: {e}")
    PYSTRAY_AVAILABLE = False


class TrayManager:
    def __init__(
        self,
        icon_path: Optional[str] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        on_toggle_mute: Optional[Callable[[bool], None]] = None,
    ):
        self.icon_path = icon_path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.png")
        self.on_open = on_open
        self.on_exit = on_exit
        self.on_toggle_mute = on_toggle_mute

        self.tray_icon = None
        self._thread: Optional[threading.Thread] = None
        self.is_running = False
        self.is_muted = False
        self.status_text = "⚪ غير متصل"
        self.tooltip_text = "بوابة الاتصال الخلوي الذكية"

        self.is_supported = PYSTRAY_AVAILABLE and Image is not None

    def _create_image(self):
        """Load icon image from disk or generate a crisp default PIL image."""
        if Image is None:
            return None

        candidate_paths = [
            self.icon_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.png"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.png"),
            os.path.join(os.getcwd(), "assets", "icon.png"),
            os.path.join(os.getcwd(), "assets", "logo.png"),
            os.path.join(os.getcwd(), "local_gsm_gateway", "assets", "icon.png"),
        ]

        if hasattr(sys, "_MEIPASS"):
            candidate_paths.insert(0, os.path.join(sys._MEIPASS, "assets", "icon.png"))

        for path in candidate_paths:
            if path and os.path.exists(path):
                try:
                    img = Image.open(path)
                    return img.convert("RGBA").resize((64, 64))
                except Exception as e:
                    logger.debug(f"Could not load icon from '{path}': {e}")

        # Fallback generated icon (Burgundy circle with gold inner dot)
        img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.ellipse([4, 4, 60, 60], fill=(122, 21, 38, 255))
            draw.ellipse([22, 22, 42, 42], fill=(212, 175, 55, 255))
        except Exception:
            pass
        return img

    def _build_menu(self):
        """Construct the context menu for system tray right click."""
        if not pystray:
            return None

        return pystray.Menu(
            pystray.MenuItem(
                text=lambda item: f"الحالة: {self.status_text}",
                action=None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                text="🖥️ فتح لوحة التحكم",
                action=self._handle_open,
                default=True
            ),
            pystray.MenuItem(
                text=lambda item: "🔊 تشغيل الصوت" if self.is_muted else "🔇 كتم الصوت",
                action=self._handle_toggle_mute
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                text="🚪 إغلاق التطبيق نهائياً",
                action=self._handle_exit
            )
        )

    def start(self) -> bool:
        """Initialize and run system tray icon in a dedicated daemon thread."""
        if not self.is_supported:
            logger.warning("TrayManager: System tray not supported or pystray/Pillow not available in runtime.")
            return False

        if self.is_running:
            return True

        try:
            image = self._create_image()
            if not image:
                logger.warning("TrayManager: Could not create image for system tray.")
                return False

            menu = self._build_menu()
            self.tray_icon = pystray.Icon(
                name="VoiceAIGateway",
                icon=image,
                title=self.tooltip_text,
                menu=menu
            )

            self.is_running = True
            self._thread = threading.Thread(target=self._run_icon_loop, daemon=True)
            self._thread.start()
            logger.info("TrayManager: System tray service started successfully.")
            return True
        except Exception as e:
            logger.error(f"TrayManager failed to start: {e}", exc_info=True)
            self.is_running = False
            return False

    def _run_icon_loop(self):
        """Main loop for pystray icon."""
        try:
            if self.tray_icon:
                logger.info("TrayManager: Running pystray message loop...")
                self.tray_icon.run()
        except Exception as e:
            logger.error(f"TrayManager message loop error: {e}", exc_info=True)
        finally:
            self.is_running = False

    def stop(self):
        """Stop and remove tray icon."""
        self.is_running = False
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None

    def update_status(
        self,
        operator: str = "",
        signal: int = 0,
        is_in_call: bool = False,
        caller: str = ""
    ):
        """Update live telemetry status shown in the tray tooltip and menu."""
        if is_in_call:
            num = caller if caller else "مكالمة جارية"
            self.status_text = f"📞 في مكالمة ({num})"
            self.tooltip_text = f"بوابة الاتصال الخلوي • مكالمة نشطة مع {num}"
        elif operator:
            sig_str = f"{signal}%" if signal > 0 else ""
            self.status_text = f"🟢 متصل | {operator} {sig_str}".strip()
            self.tooltip_text = f"بوابة الاتصال الخلوي • {operator} ({sig_str})"
        else:
            self.status_text = "⚪ غير متصل"
            self.tooltip_text = "بوابة الاتصال الخلوي الذكية"

        if self.tray_icon and self.is_running:
            try:
                self.tray_icon.title = self.tooltip_text
                self.tray_icon.update_menu()
            except Exception:
                pass

    def show_notification(self, title: str, message: str):
        """Trigger a desktop system tray balloon/toast notification."""
        logger.info(f"Tray Notification -> [{title}]: {message}")
        if self.tray_icon and self.is_running:
            try:
                if hasattr(self.tray_icon, "notify"):
                    self.tray_icon.notify(message, title)
            except Exception as e:
                logger.warning(f"Could not dispatch tray notification: {e}")

    def _handle_open(self, icon=None, item=None):
        logger.info("Tray menu: Open dashboard requested")
        if self.on_open:
            self.on_open()

    def _handle_toggle_mute(self, icon=None, item=None):
        self.is_muted = not self.is_muted
        logger.info(f"Tray menu: Toggle mute -> {self.is_muted}")
        if self.on_toggle_mute:
            self.on_toggle_mute(self.is_muted)
        if self.tray_icon and self.is_running:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    def _handle_exit(self, icon=None, item=None):
        logger.info("Tray menu: Complete application exit requested")
        self.stop()
        if self.on_exit:
            self.on_exit()
