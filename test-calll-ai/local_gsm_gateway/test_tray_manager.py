"""Test suite for System Tray Integration and Background Lifecycle."""
import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure package path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controllers.tray_manager import TrayManager
from controllers.api_client import DongleApiClient
from views.dashboard_view import DashboardView


class TestTrayManager(unittest.TestCase):
    def test_01_tray_manager_initialization_and_status(self):
        """Verify TrayManager initializes correctly and formats telemetry status."""
        opened = []
        exited = []
        muted_states = []

        tray = TrayManager(
            on_open=lambda: opened.append(True),
            on_exit=lambda: exited.append(True),
            on_toggle_mute=lambda m: muted_states.append(m)
        )

        self.assertIsNotNone(tray.icon_path)
        self.assertIn("⚪ غير متصل", tray.status_text)

        # 1. Update status to connected
        tray.update_status(operator="Vodafone", signal=92, is_in_call=False)
        self.assertIn("Vodafone", tray.status_text)
        self.assertIn("92%", tray.status_text)
        self.assertIn("🟢", tray.status_text)

        # 2. Update status to in-call
        tray.update_status(operator="Vodafone", signal=92, is_in_call=True, caller="+201099887766")
        self.assertIn("📞", tray.status_text)
        self.assertIn("+201099887766", tray.status_text)

        # 3. Test Mute Toggle
        tray._handle_toggle_mute()
        self.assertTrue(tray.is_muted)
        self.assertEqual(muted_states, [True])

        tray._handle_toggle_mute()
        self.assertFalse(tray.is_muted)
        self.assertEqual(muted_states, [True, False])

        # 4. Test Open callback
        tray._handle_open()
        self.assertEqual(opened, [True])

        # 5. Test Exit callback
        tray._handle_exit()
        self.assertEqual(exited, [True])
        self.assertFalse(tray.is_running)
        print("  [PASS] TrayManager: Initialization, Status formatting, and Callbacks OK!")

    def test_02_tray_notifications_safe_dispatch(self):
        """Verify show_notification executes safely without throwing exceptions."""
        tray = TrayManager()
        # Should not throw in any environment (headless or GUI)
        try:
            tray.show_notification("📞 مكالمة واردة", "اتصال جديد من +201012345678")
            tray.show_notification("📩 رسالة SMS", "رسالة جديدة واردة")
            notification_ok = True
        except Exception as e:
            notification_ok = False

        self.assertTrue(notification_ok)
        print("  [PASS] TrayManager: Notification dispatch resilience OK!")

    def test_03_dashboard_view_tray_integration(self):
        """Verify DashboardView syncs state and notifies TrayManager on incoming call."""
        mock_page = MagicMock()
        mock_page.window.visible = False
        mock_page.window.minimized = True

        notifications = []
        statuses = []

        tray = TrayManager()
        tray.show_notification = lambda title, msg: notifications.append((title, msg))
        tray.update_status = lambda operator, signal, is_in_call, caller="": statuses.append((operator, signal, is_in_call, caller))

        api_client = DongleApiClient()
        dashboard = DashboardView(mock_page, api_client, on_logout=None, tray_manager=tray)

        # Simulate incoming call
        dashboard._on_modem_incoming_call("+201055554444")
        self.assertTrue(dashboard.is_in_call)

        # Verify tray was notified of incoming call
        self.assertTrue(any(s[2] is True for s in statuses), "Tray should record in_call=True")
        self.assertTrue(any("+201055554444" in n[1] for n in notifications), "Tray should dispatch desktop notification for hidden window")

        # Simulate call hangup
        dashboard._end_call()
        self.assertFalse(dashboard.is_in_call)
        self.assertTrue(any(s[2] is False for s in statuses), "Tray should record in_call=False after hangup")

        # Clean up dashboard
        dashboard.cleanup()
        print("  [PASS] DashboardView: Tray status syncing and incoming call notification OK!")


if __name__ == "__main__":
    unittest.main()
