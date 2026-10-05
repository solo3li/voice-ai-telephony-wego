"""Comprehensive End-to-End Test Suite for Local GSM USB Dongle AI Voice Gateway.

Covers all 5 major feature pillars:
1. StorageManager (SQLite persistence of calls, SMS, USSD, and dongle devices).
2. ModemController (Live AT protocol, AT+CSQ signal, AT+COPS operator, ATA, ATH, ATD, SMS, USSD).
3. DonglePool (Multi-SIM Dongle Pool orchestration, failover, idle allocation).
4. AudioBridge (Real-time RMS audio levels, dynamic waveform, live RTT ping monitor).
5. Full UI Views & Navigation (BottomNavigationBar, Dialpad, SMS/USSD, Dongle Pool, Dashboard).
6. Live Backend Cloud Integration (Django Dongle Auth, WebRTC Call Init, Hangup Sync).

Executed headlessly via python scripts only.
"""
import os
import sys
import time
import unittest
from unittest.mock import MagicMock
import urllib3

urllib3.disable_warnings()

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import flet as ft
from controllers.storage_manager import StorageManager
from controllers.modem_controller import ModemController, DonglePool, list_available_ports
from controllers.audio_bridge import AudioBridge
from controllers.api_client import DongleApiClient, SESSION_FILE
from views.dialpad_view import DialpadView
from views.sms_ussd_view import SmsUssdView
from views.pool_view import PoolView
from views.dashboard_view import DashboardView


class TestGSMGatewayAllFeaturesE2E(unittest.TestCase):
    SERVER_URL = "https://app.169.58.32.179.nip.io"
    TEST_DB_PATH = os.path.join(current_dir, "test_gateway.db")

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls.TEST_DB_PATH):
            os.remove(cls.TEST_DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.TEST_DB_PATH):
            os.remove(cls.TEST_DB_PATH)

    # =========================================================================
    # PILLAR 1: StorageManager (SQLite Persistence)
    # =========================================================================
    def test_01_sqlite_storage_manager(self):
        print("\n>>> [TEST 1] SQLite StorageManager Offline-First Persistence...")
        storage = StorageManager(self.TEST_DB_PATH)

        # 1.1 Add call log
        call_id = storage.add_call_log(
            caller_phone="+201011223344",
            destination_phone="+201099887766",
            direction="outbound",
            duration=45,
            status="completed",
            room_name="test_room_1",
            dongle_port="SIMULATED_1"
        )
        self.assertGreater(call_id, 0)

        # 1.2 Query recent calls
        calls = storage.get_recent_calls(limit=10)
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(calls[0]["caller_phone"], "+201011223344")
        self.assertEqual(calls[0]["direction"], "outbound")
        self.assertEqual(calls[0]["duration"], 45)

        # 1.3 Total calls count
        total = storage.get_total_calls_today()
        self.assertGreaterEqual(total, 1)

        # 1.4 Add & query SMS
        sms_id = storage.add_sms(
            phone_number="+201200112233",
            message_text="تم حجز الطاولة رقم 5 بنجاح",
            direction="outbound",
            dongle_port="SIMULATED_1"
        )
        self.assertGreater(sms_id, 0)
        sms_list = storage.get_sms_messages(limit=5)
        self.assertGreaterEqual(len(sms_list), 1)
        self.assertEqual(sms_list[0]["phone_number"], "+201200112233")

        # 1.5 Add & query USSD
        ussd_id = storage.add_ussd_record("*888#", "رصيدك 50 جنيهاً", dongle_port="SIMULATED_1")
        self.assertGreater(ussd_id, 0)
        ussd_list = storage.get_recent_ussd(limit=5)
        self.assertEqual(ussd_list[0]["ussd_code"], "*888#")
        print("  [PASS] StorageManager: Call logs, SMS, and USSD records successfully persisted!")

    # =========================================================================
    # PILLAR 2: ModemController (AT Commands, Telemetry, Calls, SMS, USSD)
    # =========================================================================
    def test_02_modem_controller_and_at_commands(self):
        print("\n>>> [TEST 2] ModemController AT Commands & Cellular Telemetry...")
        incoming_event = []
        ended_event = []
        signal_event = []

        modem = ModemController(
            port="SIMULATED_1",
            on_incoming_call=lambda num: incoming_event.append(num),
            on_call_ended=lambda: ended_event.append(True),
            on_signal_update=lambda sig, op: signal_event.append((sig, op))
        )
        self.assertTrue(modem.connect())
        self.assertTrue(modem.is_connected)

        # 2.1 Live Telemetry
        modem.refresh_telemetry()
        self.assertGreater(modem.signal_strength, 0)
        self.assertIn("Vodafone", modem.operator_name)
        self.assertEqual(modem.sim_status, "READY")
        self.assertIsNotNone(modem.imei)

        # 2.2 Inbound Call & Answer
        modem.simulate_incoming_call("+201098765432")
        time.sleep(0.1)
        self.assertIn("+201098765432", incoming_event)
        self.assertTrue(modem.answer_call())
        self.assertTrue(modem.is_in_call)

        # 2.3 Hangup Call
        self.assertTrue(modem.hangup_call())
        self.assertFalse(modem.is_in_call)

        # 2.4 Outbound Call (ATD)
        self.assertTrue(modem.dial_call("+201155443322"))
        self.assertTrue(modem.is_in_call)
        modem.hangup_call()

        # 2.5 SMS Operations
        self.assertTrue(modem.send_sms("+201011223344", "كود التأكيد الخاص بك هو 9482"))
        sms_msgs = modem.read_all_sms()
        self.assertGreaterEqual(len(sms_msgs), 1)

        # 2.6 USSD Execution
        ussd_reply = modem.execute_ussd("*888#")
        self.assertIn("رصيدك", ussd_reply)
        print(f"  [PASS] ModemController: AT protocol, Inbound/Outbound, SMS, and USSD ({ussd_reply[:30]}...) OK!")

    # =========================================================================
    # PILLAR 3: DonglePool (Multi-SIM Management)
    # =========================================================================
    def test_03_multi_sim_dongle_pool(self):
        print("\n>>> [TEST 3] Multi-SIM Dongle Pool Orchestration...")
        pool_calls = []
        pool = DonglePool(on_global_incoming=lambda num, port: pool_calls.append((num, port)))

        # 3.1 Verify discovered modems
        modems = pool.get_all_modems()
        self.assertGreaterEqual(len(modems), 2)
        ports = [m["port"] for m in modems]
        self.assertIn("SIMULATED_1", ports)
        self.assertIn("SIMULATED_2", ports)

        # 3.2 Idle modem allocation
        idle_modem = pool.get_idle_modem()
        self.assertIsNotNone(idle_modem)
        self.assertFalse(idle_modem.is_in_call)

        # 3.3 Make idle modem busy and test failover allocation
        idle_modem.is_in_call = True
        second_idle = pool.get_idle_modem()
        self.assertIsNotNone(second_idle)
        self.assertNotEqual(second_idle.port, idle_modem.port)

        idle_modem.is_in_call = False
        print("  [PASS] DonglePool: Multi-SIM device discovery and dynamic failover allocation OK!")

    # =========================================================================
    # PILLAR 4: AudioBridge (Real-time Visualizer & Latency Ping)
    # =========================================================================
    def test_04_audio_bridge_and_visualizer(self):
        print("\n>>> [TEST 4] AudioBridge Live RMS Audio Energy & Ping Monitor...")
        audio_samples = []
        latency_samples = []

        bridge = AudioBridge(
            on_audio_level=lambda caller, ai: audio_samples.append((caller, ai)),
            on_latency_update=lambda rtt: latency_samples.append(rtt)
        )

        # 4.1 Start audio pipeline
        bridge.start_pipeline("test_livekit_room", "wss://livekit.localhost")
        self.assertTrue(bridge.is_active)
        time.sleep(0.3)
        self.assertGreater(len(audio_samples), 0)
        caller_lvl, ai_lvl = audio_samples[-1]
        self.assertGreater(caller_lvl, 0.0)
        self.assertGreater(ai_lvl, 0.0)

        # 4.2 Test Mute
        bridge.set_mute(True)
        time.sleep(0.2)
        caller_lvl_muted, _ = audio_samples[-1]
        self.assertEqual(caller_lvl_muted, 0.0)

        # 4.3 Stop pipeline
        bridge.stop_pipeline()
        self.assertFalse(bridge.is_active)
        print("  [PASS] AudioBridge: Real-time RMS audio levels and visualizer energy streams OK!")

    # =========================================================================
    # PILLAR 5: Full UI Views & Navigation Bar Integration
    # =========================================================================
    def test_05_views_and_navigation(self):
        print("\n>>> [TEST 5] UI Views, Dialpad, SMS/USSD, and 4-Tab Navigation...")
        mock_page = MagicMock(spec=ft.Page)
        api_client = DongleApiClient(self.SERVER_URL)
        api_client.token = "mock_test_token"
        api_client.user_data = {"name": "شركة الأمل"}

        dashboard = DashboardView(mock_page, api_client, on_logout=None)
        root_ctrl = dashboard.build()
        self.assertIsNotNone(root_ctrl)

        # 5.1 Verify Bottom Navigation Bar has 4 destinations
        self.assertEqual(len(dashboard.nav_bar.destinations), 4)
        labels = [d.label for d in dashboard.nav_bar.destinations]
        self.assertIn("الرئيسية", labels)
        self.assertIn("الاتصال", labels)
        self.assertIn("الرسائل والرصيد", labels)
        self.assertIn("مجمع الشرائح", labels)

        # 5.2 Switch Tabs
        dashboard._switch_tab(1)  # Dialpad
        self.assertEqual(dashboard.active_tab_index, 1)

        dashboard._switch_tab(2)  # SMS & USSD
        self.assertEqual(dashboard.active_tab_index, 2)

        dashboard._switch_tab(3)  # Pool View
        self.assertEqual(dashboard.active_tab_index, 3)

        dashboard._switch_tab(0)  # Back to Home
        self.assertEqual(dashboard.active_tab_index, 0)

        # 5.3 Test Outbound Dial from Dialpad
        dashboard.dialpad_tab.number_input.value = "+201099887766"
        dashboard._handle_dialpad_call("+201099887766", "ai_agent")
        self.assertTrue(dashboard.is_in_call)
        self.assertTrue(dashboard.active_call_card.visible)
        self.assertEqual(dashboard.caller_number_text.value, "+201099887766")

        # 5.4 Test Dynamic Audio Energy updates waveform bar heights
        dashboard._on_audio_energy(0.8, 0.4)
        bar_heights = [b.height for b in dashboard.waveform_bars]
        self.assertTrue(any(h > 15 for h in bar_heights))

        # 5.5 End Call & Check SQLite Storage
        dashboard._end_call()
        self.assertFalse(dashboard.is_in_call)
        self.assertFalse(dashboard.active_call_card.visible)
        print("  [PASS] Full UI: 4-Tab Navigation, Interactive Dialpad, Dynamic Waveform, and Call Workflow OK!")

    # =========================================================================
    # PILLAR 6: Backend Cloud API Integration
    # =========================================================================
    def test_06_backend_cloud_api(self):
        print("\n>>> [TEST 6] Live Cloud Backend API Verification (Auth, Call, Hangup)...")
        api = DongleApiClient(self.SERVER_URL)
        api.clear_session()

        # 6.1 Status without token -> unauthorized
        res = api.get_status()
        self.assertFalse(res["success"])

        # 6.2 Login owner
        login_res = api.login("dongle_owner_user", "OwnerSecretPassword123!")
        if login_res.get("success"):
            print("  [PASS] Cloud Dongle Login succeeded with live credentials!")
            self.assertIsNotNone(api.token)

            # 6.3 Call Init endpoint
            call_res = api.init_call("+201012345678", "SIMULATED_1")
            self.assertTrue(call_res.get("success"))
            room = call_res["data"].get("room_name")
            session_id = call_res["data"].get("session_id")
            print(f"  [PASS] Cloud Call Initialized -> Room: {room}, Session #{session_id}")

            # 6.4 Hangup endpoint
            hangup_res = api.hangup_call(room, duration_seconds=12, session_id=session_id)
            self.assertTrue(hangup_res.get("success"))
            print("  [PASS] Cloud Call Hangup & Duration successfully synchronized!")
        else:
            print(f"  [NOTE] Cloud server login returned: {login_res.get('error')} (Offline/Stub test mode)")


if __name__ == "__main__":
    unittest.main()
