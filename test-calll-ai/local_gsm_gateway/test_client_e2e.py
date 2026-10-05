"""End-to-End Test Suite for Local GSM USB Dongle Gateway App.

Strictly tests:
1. Owner authentication using ONLY username and password (NO email).
2. UI rendering without live transcription speech bubbles (zero lag / ultra lightweight).
3. Modem event handling, incoming call answering (ATA), LiveKit room creation, and hangup (ATH).
4. Session persistence (session.json) and auto-login workflow.
All executed headlessly via scripts (NO browser used).
"""
import os
import sys
import json
import time
import unittest
from unittest.mock import MagicMock
import urllib3

urllib3.disable_warnings()

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import flet as ft
from controllers.api_client import DongleApiClient, SESSION_FILE
from controllers.modem_controller import ModemController
from views.login_view import LoginView
from views.dashboard_view import DashboardView


class TestDongleGatewayClientE2E(unittest.TestCase):
    SERVER_URL = "https://app.169.58.32.179.nip.io"
    OWNER_USERNAME = "dongle_owner_user"
    OWNER_PASSWORD = "OwnerSecretPassword123!"

    def setUp(self):
        # Clean up any existing session file
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        self.api_client = DongleApiClient(self.SERVER_URL)

    def tearDown(self):
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)

    def test_01_login_view_structure_and_no_email(self):
        """Verify LoginView uses ONLY username/password and has NO email input."""
        print("\n[CLIENT TEST 1] Verifying LoginView inputs (NO email allowed)...")
        mock_page = MagicMock(spec=ft.Page)
        login_view = LoginView(mock_page, self.api_client, on_login_success=None)
        
        # Check inputs
        self.assertTrue(hasattr(login_view, "username_input"))
        self.assertTrue(hasattr(login_view, "password_input"))
        self.assertFalse(hasattr(login_view, "email_input"), "Email field MUST NOT exist!")
        
        # Verify text hints and labels
        self.assertIn("اسم المستخدم", login_view.username_input.label)
        self.assertIn("كلمة المرور", login_view.password_input.label)
        
        # Build UI container
        container = login_view.build()
        self.assertIsInstance(container, ft.Container)
        print("  -> LoginView UI built cleanly with strictly username & password!")

    def test_02_negative_auth_empty_and_wrong_credentials(self):
        """Verify negative auth scenarios via DongleApiClient."""
        print("\n[CLIENT TEST 2] Testing Negative Authentication flows...")
        
        # Empty credentials
        res_empty = self.api_client.login("", "")
        self.assertFalse(res_empty["success"])
        print(f"  -> Empty credentials correctly rejected: {res_empty.get('error')}")

        # Wrong password
        res_wrong = self.api_client.login(self.OWNER_USERNAME, "WrongPassXYZ123!")
        self.assertFalse(res_wrong["success"])
        self.assertIn("غير صحيحة", res_wrong.get("error", ""))
        print(f"  -> Invalid password correctly rejected: {res_wrong.get('error')}")

    def test_03_positive_owner_login_and_token(self):
        """Verify successful owner login and profile retrieval."""
        print("\n[CLIENT TEST 3] Testing Positive Owner Login (Username + Password)...")
        res = self.api_client.login(self.OWNER_USERNAME, self.OWNER_PASSWORD, remember=True)
        self.assertTrue(res["success"], f"Login failed: {res}")
        
        data = res["data"]
        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(self.api_client.token)
        self.assertEqual(self.api_client.user_data["username"], self.OWNER_USERNAME)
        self.assertIn("wss://livekit", self.api_client.livekit_url)
        print(f"  -> Owner authenticated: {self.api_client.user_data.get('name')} (ID: {self.api_client.user_data.get('id')})")
        print(f"  -> Active Voice Profile: {self.api_client.active_profile.get('name')}")
        print(f"  -> LiveKit URL: {self.api_client.livekit_url}")

    def test_04_session_persistence_and_auto_login(self):
        """Verify session.json is created and allows auto-login without re-entering password."""
        print("\n[CLIENT TEST 4] Testing Session Persistence & Auto-Login...")
        
        # Perform login with remember=True
        self.api_client.login(self.OWNER_USERNAME, self.OWNER_PASSWORD, remember=True)
        self.assertTrue(os.path.exists(SESSION_FILE), "session.json should be saved on remember=True")
        
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        self.assertIn("token", session_data)
        self.assertEqual(session_data["user_data"]["username"], self.OWNER_USERNAME)
        print("  -> session.json verified with valid JWT token.")

        # Create a new client and test auto-login loading
        new_client = DongleApiClient(self.SERVER_URL)
        self.assertIsNotNone(new_client.token)
        self.assertEqual(new_client.user_data["username"], self.OWNER_USERNAME)
        
        # Verify status endpoint with restored token
        status_res = new_client.get_status()
        self.assertTrue(status_res["success"])
        self.assertTrue(status_res["data"]["has_active_agent"])
        print(f"  -> Auto-login succeeded! Server recognized agent: {status_res['data']['agent_name']}")

    def test_05_dashboard_view_structure_and_no_transcript_bubbles(self):
        """Verify DashboardView adopts Dynamic Cards and has NO live transcript bubbles."""
        print("\n[CLIENT TEST 5] Verifying DashboardView layout (Dynamic Cards & NO Transcript bubbles)...")
        # Ensure client is logged in
        self.api_client.login(self.OWNER_USERNAME, self.OWNER_PASSWORD)
        
        mock_page = MagicMock(spec=ft.Page)
        dashboard = DashboardView(mock_page, self.api_client, on_logout=None)
        
        # Verify component cards exist
        self.assertTrue(hasattr(dashboard, "header"))
        self.assertTrue(hasattr(dashboard, "active_call_card"))
        self.assertTrue(hasattr(dashboard, "signal_card"))
        self.assertTrue(hasattr(dashboard, "sim_card"))
        self.assertTrue(hasattr(dashboard, "latency_card"))
        self.assertTrue(hasattr(dashboard, "calls_card"))
        self.assertTrue(hasattr(dashboard, "hardware_card"))
        self.assertTrue(hasattr(dashboard, "calls_history_card"))
        
        # Verify NO live transcript bubbles (user requested keeping UI lightweight)
        self.assertFalse(hasattr(dashboard, "transcript_list"), "Transcript list MUST NOT exist in UI!")
        self.assertFalse(hasattr(dashboard, "chat_bubbles"), "Chat bubbles MUST NOT exist in UI!")
        
        # Build dashboard control tree
        dashboard_control = dashboard.build()
        self.assertIsInstance(dashboard_control, ft.Container)
        print("  -> Dynamic Cards UI constructed with 0 transcript clutter (maximum performance)!")

    def test_06_simulated_call_e2e_flow(self):
        """Simulate incoming GSM cellular call from +201012345678, WebRTC token, and hangup."""
        print("\n[CLIENT TEST 6] Running Complete Inbound Cellular Call Simulation...")
        self.api_client.login(self.OWNER_USERNAME, self.OWNER_PASSWORD)
        
        mock_page = MagicMock(spec=ft.Page)
        dashboard = DashboardView(mock_page, self.api_client, on_logout=None)
        
        caller_number = "+201012345678"
        self.assertFalse(dashboard.is_in_call)
        self.assertFalse(dashboard.active_call_card.visible)
        
        # Trigger simulated incoming call
        print(f"  -> Simulating cellular RING from: {caller_number}")
        dashboard.modem.simulate_incoming_call(caller_number)
        
        # Wait a moment for modem event and async cloud API call
        time.sleep(1.0)
        
        # Verify active call state
        self.assertTrue(dashboard.is_in_call)
        self.assertTrue(dashboard.active_call_card.visible)
        self.assertEqual(dashboard.current_caller, caller_number)
        self.assertTrue(dashboard.current_room.startswith("dongle_"))
        self.assertIsNotNone(dashboard.current_session_id)
        print(f"  -> Call accepted! LiveKit Room: {dashboard.current_room}, Session ID: {dashboard.current_session_id}")
        
        # Hang up call
        print("  -> Terminating call via ATH and reporting duration...")
        dashboard._end_call()
        
        self.assertFalse(dashboard.is_in_call)
        self.assertFalse(dashboard.active_call_card.visible)
        self.assertEqual(dashboard.total_calls_today, 1)
        self.assertEqual(len(dashboard.recent_calls), 1)
        self.assertEqual(dashboard.recent_calls[0]["phone"], caller_number)
        print(f"  -> Call ended cleanly. Total calls recorded today: {dashboard.total_calls_today}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
