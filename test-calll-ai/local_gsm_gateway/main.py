"""Local GSM USB Dongle AI Voice Gateway Flet Application Entrypoint.

Starts the Flet application in a modern mobile form factor (400x800).
Loads saved session for automatic login, or shows the Owner Login screen.
"""
import sys
import os

# Ensure package path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import flet as ft
from theme import COLOR_CREAM, COLOR_BURGUNDY, FONT_FAMILY
from controllers.api_client import DongleApiClient
from controllers.tray_manager import TrayManager
from views.login_view import LoginView
from views.dashboard_view import DashboardView


def main(page: ft.Page):
    page.title = "بوابة الاتصال الخلوي الذكية"
    page.width = 410
    page.height = 820
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COLOR_CREAM
    page.padding = 0

    # Ensure Windows taskbar groups and shows the custom app icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("voiceai.dongle.gateway.v1")
        except Exception:
            pass

    # Set Window & Taskbar Icon
    try:
        window = getattr(page, "window", None)
        if window:
            icon_ico = os.path.join(current_dir, "assets", "icon.ico")
            icon_png = os.path.join(current_dir, "assets", "icon.png")
            if os.path.exists(icon_ico):
                window.icon = icon_ico
            elif os.path.exists(icon_png):
                window.icon = icon_png
            else:
                window.icon = "assets/icon.ico"
    except Exception:
        pass

    # Active dashboard tracker
    active_dashboard = None

    # Tray Manager Integration
    def on_tray_open():
        try:
            window = getattr(page, "window", None)
            if window:
                window.skip_task_bar = False
                window.visible = True
                window.minimized = False
            page.update()
            if window and hasattr(window, "to_front"):
                window.to_front()
        except Exception:
            pass

    def on_tray_exit():
        try:
            if active_dashboard:
                active_dashboard.cleanup()
            tray_manager.stop()
            window = getattr(page, "window", None)
            if window and hasattr(window, "destroy"):
                window.destroy()
            else:
                sys.exit(0)
        except Exception:
            sys.exit(0)

    def on_tray_toggle_mute(is_muted: bool):
        if active_dashboard:
            active_dashboard.is_muted = is_muted
            if hasattr(active_dashboard, "mute_btn"):
                active_dashboard.mute_btn.content = "إلغاء الكتم" if is_muted else "كتم الصوت"
                active_dashboard.mute_btn.icon = ft.Icons.MIC_ROUNDED if is_muted else ft.Icons.MIC_OFF_ROUNDED
                page.update()

    tray_manager = TrayManager(
        on_open=on_tray_open,
        on_exit=on_tray_exit,
        on_toggle_mute=on_tray_toggle_mute,
    )
    tray_manager.start()

    # Desktop Window: Close button interception -> minimize to tray
    try:
        window = getattr(page, "window", None)
        if window:
            window.prevent_close = True

            def on_window_event(e):
                event_type = str(getattr(e, "type", "") or getattr(e, "data", "")).lower()
                if "close" in event_type:
                    window.visible = False
                    window.skip_task_bar = True
                    page.update()
                    tray_manager.show_notification(
                        "بوابة الاتصال الخلوي الذكية",
                        "تعمل البوابة الآن في صينية النظام بالخلفية لضمان عدم تفويت أي مكالمات."
                    )

            window.on_event = on_window_event
    except Exception:
        pass

    # API Client instance
    api_client = DongleApiClient()

    def show_dashboard():
        nonlocal active_dashboard
        page.clean()
        active_dashboard = DashboardView(page, api_client, on_logout=show_login, tray_manager=tray_manager)
        page.add(active_dashboard.build())
        page.update()

    def show_login():
        nonlocal active_dashboard
        page.clean()
        active_dashboard = None
        login = LoginView(page, api_client, on_login_success=show_dashboard)
        page.add(login.build())
        page.update()

    # Check for Auto-Login (Remember Me session)
    if api_client.token and api_client.user_data:
        # Validate token with cloud backend
        status = api_client.get_status()
        if status.get("success"):
            show_dashboard()
            return

    # If no session or expired token, show login screen
    show_login()


if __name__ == "__main__":
    assets_dir = os.path.join(current_dir, "assets")
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=assets_dir)
    elif hasattr(ft, "app"):
        ft.app(target=main, assets_dir=assets_dir)
    else:
        raise RuntimeError("No app runner found in flet module")
