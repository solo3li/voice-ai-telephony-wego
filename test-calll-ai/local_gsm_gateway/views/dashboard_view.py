"""Comprehensive Dashboard View for Local GSM USB Dongle AI Voice Gateway.

Features:
1. Bottom Navigation Bar with 4 Integrated Tabs:
   - [0] الرئيسية والمكالمات (Dashboard & Active Hero Card with Dynamic Audio Visualizer)
   - [1] لوحة الاتصال الصادر (DialpadView)
   - [2] الرسائل والرصيد (SmsUssdView)
   - [3] مجمع الفلاشات والشرائح (PoolView)
2. Live Dynamic Waveform Visualizer (Real-time Audio RMS Levels via AudioBridge).
3. Real RTT Latency Ping Monitor & Live Hardware Telemetry (AT+CSQ, AT+COPS).
4. Local SQLite Persistence for Call Records via StorageManager.
"""
import time
import flet as ft
from theme import (
    COLOR_BURGUNDY,
    COLOR_BURGUNDY_LIGHT,
    COLOR_BURGUNDY_BORDER,
    COLOR_CREAM,
    COLOR_WHITE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_GREEN,
    COLOR_GREEN_BG,
    COLOR_GREEN_TEXT,
    COLOR_RED,
    COLOR_RED_HOVER,
    COLOR_RED_BG,
)
from controllers.api_client import DongleApiClient
from controllers.modem_controller import ModemController, DonglePool, list_available_ports
from controllers.storage_manager import StorageManager
from controllers.audio_bridge import AudioBridge
from views.dialpad_view import DialpadView
from views.sms_ussd_view import SmsUssdView
from views.pool_view import PoolView


class DashboardView:
    def __init__(self, page: ft.Page, api_client: DongleApiClient, on_logout=None, tray_manager=None):
        self.page = page
        self.api_client = api_client
        self.on_logout = on_logout
        self.tray_manager = tray_manager

        # Storage & Audio Managers
        self.storage = StorageManager()
        self.audio_bridge = AudioBridge(
            on_audio_level=self._on_audio_energy,
            on_latency_update=self._on_latency_update
        )

        # State Variables
        self.is_in_call = False
        self.call_direction = "inbound"  # "inbound" or "outbound"
        self.current_caller = ""
        self.current_room = ""
        self.current_session_id = None
        self.call_start_time = 0
        self.is_muted = False
        self.total_calls_today = 0
        self.recent_calls = []
        self.active_tab_index = 0

        # Multi-SIM Dongle Pool
        self.dongle_pool = DonglePool(on_global_incoming=self._on_pool_incoming_call)

        # Primary Modem Controller
        self.modem = self.dongle_pool.get_idle_modem() or ModemController(
            port="SIMULATED_1",
            on_incoming_call=self._on_modem_incoming_call,
            on_call_ended=self._on_modem_call_ended,
            on_signal_update=self._on_signal_update
        )
        self.modem.on_incoming_call = self._on_modem_incoming_call
        self.modem.on_call_ended = self._on_modem_call_ended
        self.modem.on_signal_update = self._on_signal_update

        # Build UI Components
        self._build_components()

        # Connect Primary Modem & Start Monitors
        self.modem.connect()
        self.audio_bridge.start_ping_monitor(self.api_client.server_url)

    def _build_components(self):
        # 1. Header (Brand Burgundy)
        owner_name = (self.api_client.user_data or {}).get("name") or "المالك"
        self.latency_pill_text = ft.Text("24 ms", color=COLOR_WHITE, size=10, weight=ft.FontWeight.BOLD)
        self.signal_header_text = ft.Text(f"{self.modem.signal_strength}%", color=COLOR_WHITE, size=10, weight=ft.FontWeight.BOLD)

        self.header = ft.Container(
            bgcolor=COLOR_BURGUNDY,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    # Title & Owner with Brand Icon
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=10,
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                content=ft.Image(
                                    src="logo.png",
                                    width=34,
                                    height=34,
                                    fit="cover",
                                    error_content=ft.Icon(ft.Icons.SIM_CARD_ROUNDED, color=COLOR_WHITE, size=20),
                                ),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("بوابة الاتصال الخلوي الذكية", color=COLOR_WHITE, size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"المالك: {owner_name} • {self.modem.operator_name or 'نشط'}", color=COLOR_BURGUNDY_LIGHT, size=10),
                                ],
                            ),
                        ],
                    ),
                    # Badges
                    ft.Row(
                        spacing=6,
                        controls=[
                            # Live Latency Badge
                            ft.Container(
                                content=ft.Row(
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.BOLT_ROUNDED, color=COLOR_GREEN, size=10),
                                        self.latency_pill_text,
                                    ],
                                ),
                                bgcolor="#FFFFFF22",
                                padding=ft.Padding.symmetric(horizontal=6, vertical=3),
                                border_radius=10,
                            ),
                            # 4G Signal
                            ft.Container(
                                content=ft.Row(
                                    spacing=3,
                                    controls=[
                                        ft.Icon(ft.Icons.NETWORK_CELL_ROUNDED, color=COLOR_WHITE, size=12),
                                        self.signal_header_text,
                                    ],
                                ),
                                bgcolor="#FFFFFF22",
                                padding=ft.Padding.symmetric(horizontal=6, vertical=3),
                                border_radius=10,
                            ),
                            # Logout button
                            ft.IconButton(
                                icon=ft.Icons.LOGOUT_ROUNDED,
                                icon_color=COLOR_WHITE,
                                icon_size=16,
                                tooltip="تسجيل الخروج",
                                on_click=self._handle_logout,
                            ),
                        ],
                    ),
                ],
            ),
        )

        # 2. Active Call Hero Card with Dynamic Waveform
        self.call_badge_text = ft.Text("📞 مكالمة واردة نشطة", size=11, color=COLOR_BURGUNDY, weight=ft.FontWeight.BOLD)
        self.call_timer_text = ft.Text("00:00", size=13, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)
        self.caller_number_text = ft.Text("—", size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)

        # Dynamic Waveform Bars (Heights animated via AudioBridge RMS callbacks)
        self.waveform_bars = [
            ft.Container(width=4, height=12, bgcolor=COLOR_BURGUNDY, border_radius=2)
            for _ in range(14)
        ]
        self.waveform_row = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
            controls=self.waveform_bars,
        )

        self.mute_btn = ft.FilledButton(
            content="كتم الصوت",
            icon=ft.Icons.MIC_OFF_ROUNDED,
            style=ft.ButtonStyle(
                color=COLOR_TEXT_PRIMARY,
                bgcolor=COLOR_BORDER_LIGHT,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
            on_click=self._toggle_mute,
        )

        self.hangup_btn = ft.FilledButton(
            content="إنهاء المكالمة",
            icon=ft.Icons.CALL_END_ROUNDED,
            style=ft.ButtonStyle(
                color=COLOR_WHITE,
                bgcolor=COLOR_RED,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
            on_click=lambda e: self._end_call(),
        )

        self.active_call_card = ft.Card(
            visible=False,
            elevation=3,
            bgcolor=COLOR_WHITE,
            shape=ft.RoundedRectangleBorder(radius=16),
            content=ft.Container(
                padding=14,
                border=ft.Border.all(1.5, COLOR_BURGUNDY_BORDER),
                border_radius=16,
                content=ft.Column(
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Container(
                                    content=self.call_badge_text,
                                    bgcolor=COLOR_BURGUNDY_LIGHT,
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=8,
                                ),
                                self.call_timer_text,
                            ],
                        ),
                        self.caller_number_text,
                        self.waveform_row,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=14,
                            controls=[self.mute_btn, self.hangup_btn],
                        ),
                    ],
                ),
            ),
        )

        # 3. Telemetry Metric Cards
        op_display = self.modem.operator_name or ("غير متصل" if not self.modem.is_connected else "شريحة نشطة")
        sig_pct = self.modem.signal_strength
        sig_display = f"{sig_pct}%" if sig_pct > 0 else "0% (لا توجد إشارة)"
        self.signal_val_text = ft.Text(sig_display, size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)
        self.signal_sub_text = ft.Text(f"{op_display} ({self.modem.signal_dbm} dBm)" if self.modem.signal_dbm else op_display, size=10, color=COLOR_TEXT_SECONDARY)
        self.signal_card = self._build_telemetry_card(
            icon=ft.Icons.NETWORK_CELL_ROUNDED,
            title="إشارة الشبكة (4G)",
            value_ctrl=self.signal_val_text,
            sub_ctrl=self.signal_sub_text,
        )

        sim_status_label = "جاهزة للاستقبال" if self.modem.is_connected else "غير متصلة"
        imei_sub = f"IMEI: ...{self.modem.imei[-4:]}" if self.modem.imei else "IMEI: —"
        self.sim_status_text = ft.Text(sim_status_label, size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)
        self.sim_sub_text = ft.Text(imei_sub, size=10, color=COLOR_TEXT_SECONDARY)
        self.sim_card = self._build_telemetry_card(
            icon=ft.Icons.SIM_CARD_OUTLINED,
            title="حالة الشريحة",
            value_ctrl=self.sim_status_text,
            sub_ctrl=self.sim_sub_text,
        )

        self.latency_val_text = ft.Text("— ms", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)
        self.latency_card = self._build_telemetry_card(
            icon=ft.Icons.BOLT_ROUNDED,
            title="زمن الاستجابة الحقيقي",
            value_ctrl=self.latency_val_text,
            sub_ctrl=ft.Text("WebRTC سحابي فائق", size=10, color=COLOR_TEXT_SECONDARY),
        )

        total_today = self.storage.get_total_calls_today()
        self.calls_count_text = ft.Text(f"{total_today} مكالمة", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)
        self.calls_card = self._build_telemetry_card(
            icon=ft.Icons.CALL_ROUNDED,
            title="مكالمات اليوم",
            value_ctrl=self.calls_count_text,
            sub_ctrl=ft.Text("سجل محلي SQLite", size=10, color=COLOR_TEXT_SECONDARY),
        )

        # 4. Hardware Port & Simulation Drawer
        ports = list_available_ports()
        self.port_dropdown = ft.Dropdown(
            label="منفذ المودم النشط",
            value=self.modem.port if self.modem.port else "SIMULATED_1",
            options=[ft.dropdown.Option(p["device"], p["description"]) for p in ports],
            border_radius=10,
            text_size=12,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            dense=True,
            on_select=self._on_port_change,
        )

        self.sim_caller_input = ft.TextField(
            hint_text="مثال: +201000000000",
            value="",
            label="رقم اختبار ورود المكالمة",
            border_radius=10,
            text_size=12,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            dense=True,
        )

        self.hardware_card = ft.Card(
            elevation=1,
            bgcolor=COLOR_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            content=ft.Container(
                padding=12,
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text("إعدادات المودم والمحاكاة", size=11, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                        self.port_dropdown,
                        self.sim_caller_input,
                        ft.FilledButton(
                            content="محاكاة ورود مكالمة من الشريحة",
                            icon=ft.Icons.SIM_CARD_ALERT_ROUNDED,
                            bgcolor=COLOR_BURGUNDY_LIGHT,
                            color=COLOR_BURGUNDY,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            on_click=self._trigger_simulated_call,
                        ),
                    ],
                ),
            ),
        )

        # 5. Recent Calls History
        self.recent_calls_column = ft.Column(spacing=6)
        self._render_recent_calls()

        self.calls_history_card = ft.Card(
            elevation=1,
            bgcolor=COLOR_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            content=ft.Container(
                padding=12,
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("سجل المكالمات الأخير (SQLite)", size=11, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                                ft.Icon(ft.Icons.HISTORY_ROUNDED, color=COLOR_BURGUNDY, size=15),
                            ],
                        ),
                        self.recent_calls_column,
                    ],
                ),
            ),
        )

        # 6. Child Tab Views
        self.dialpad_tab = DialpadView(
            self.page,
            on_dial=self._handle_dialpad_call,
            on_hangup=self._end_call
        )
        self.sms_ussd_tab = SmsUssdView(self.page, self.modem, self.storage)
        self.pool_tab = PoolView(
            self.page,
            self.dongle_pool,
            on_select_primary=self._on_pool_select_primary
        )

        # 7. Bottom Navigation Bar
        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            bgcolor=COLOR_WHITE,
            indicator_color=COLOR_BURGUNDY_LIGHT,
            on_change=self._on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD_OUTLINED, selected_icon=ft.Icons.DASHBOARD, label="الرئيسية"),
                ft.NavigationBarDestination(icon=ft.Icons.DIALPAD_OUTLINED, selected_icon=ft.Icons.DIALPAD, label="الاتصال"),
                ft.NavigationBarDestination(icon=ft.Icons.SMS_OUTLINED, selected_icon=ft.Icons.SMS, label="الرسائل والرصيد"),
                ft.NavigationBarDestination(icon=ft.Icons.HUB_OUTLINED, selected_icon=ft.Icons.HUB, label="مجمع الشرائح"),
            ],
        )

        # Tab Content Container
        self.tab_content = ft.Container(expand=True)
        self._switch_tab(0)

    def _build_telemetry_card(self, icon, title: str, value_ctrl: ft.Control, sub_ctrl: ft.Control) -> ft.Card:
        return ft.Card(
            expand=True,
            elevation=1,
            bgcolor=COLOR_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            content=ft.Container(
                padding=10,
                content=ft.Column(
                    spacing=3,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(title, size=10, color=COLOR_TEXT_MUTED, weight=ft.FontWeight.W_600),
                                ft.Icon(icon, color=COLOR_BURGUNDY, size=15),
                            ],
                        ),
                        value_ctrl,
                        sub_ctrl,
                    ],
                ),
            ),
        )

    def _render_recent_calls(self):
        self.recent_calls_column.controls.clear()
        calls = self.storage.get_recent_calls(limit=6)
        if not calls:
            self.recent_calls_column.controls.append(
                ft.Text("لا توجد مكالمات مسجلة بعد اليوم.", size=11, color=COLOR_TEXT_MUTED)
            )
            return

        for c in calls:
            is_out = c.get("direction") == "outbound"
            dir_icon = ft.Icons.PHONE_FORWARDED_ROUNDED if is_out else ft.Icons.PHONE_IN_TALK_ROUNDED
            dir_text = "صادرة" if is_out else "واردة"

            self.recent_calls_column.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    bgcolor=COLOR_BORDER_LIGHT,
                    border_radius=8,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(dir_icon, size=14, color=COLOR_BURGUNDY),
                                    ft.Text(c["caller_phone"], size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                                    ft.Text(f"({dir_text})", size=10, color=COLOR_TEXT_MUTED),
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Text(f"{c['duration']}ث", size=11, color=COLOR_TEXT_MUTED),
                                    ft.Container(
                                        content=ft.Text("ناجحة", size=9, color=COLOR_GREEN_TEXT, weight=ft.FontWeight.BOLD),
                                        bgcolor=COLOR_GREEN_BG,
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=6,
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

    # ------------------ Navigation & Tabs ------------------

    def _on_nav_change(self, e):
        idx = e.control.selected_index
        self._switch_tab(idx)

    def _switch_tab(self, idx: int):
        self.active_tab_index = idx
        if idx == 0:
            # Home Dashboard Tab
            self.tab_content.content = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                content=ft.Column(
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        self.active_call_card,
                        # 2x2 Telemetry
                        ft.Row(spacing=8, controls=[self.signal_card, self.sim_card]),
                        ft.Row(spacing=8, controls=[self.latency_card, self.calls_card]),
                        # Hardware & Simulation Card
                        self.hardware_card,
                        # Recent Calls Card
                        self.calls_history_card,
                    ],
                ),
            )
        elif idx == 1:
            # Outbound Dialpad Tab
            self.tab_content.content = self.dialpad_tab.build()
        elif idx == 2:
            # SMS & USSD Tab
            self.tab_content.content = self.sms_ussd_tab.build()
        elif idx == 3:
            # Multi-SIM Pool Tab
            self.tab_content.content = self.pool_tab.build()

        self.page.update()

    # ------------------ Dynamic Call Handling & Audio ------------------

    def _on_audio_energy(self, caller_level: float, ai_level: float):
        """Update waveform bar heights dynamically according to speech energy."""
        if not self.is_in_call:
            return
        for i, bar in enumerate(self.waveform_bars):
            # Alternate weighting between caller and AI
            lvl = caller_level if i % 2 == 0 else ai_level
            h = int(8 + (lvl * 32 * ((i + 1) % 4 + 1) / 4))
            bar.height = min(40, max(8, h))
        try:
            self.page.update()
        except Exception:
            pass

    def _on_latency_update(self, rtt_ms: int):
        """Update live RTT metric and colors."""
        self.latency_pill_text.value = f"{rtt_ms} ms"
        self.latency_val_text.value = f"{rtt_ms} ms"
        if rtt_ms < 60:
            self.latency_val_text.color = COLOR_GREEN_TEXT
        elif rtt_ms < 150:
            self.latency_val_text.color = COLOR_TEXT_PRIMARY
        else:
            self.latency_val_text.color = COLOR_RED
        try:
            self.page.update()
        except Exception:
            pass

    def _on_signal_update(self, signal_pct: int, operator_name: str):
        """Update live cellular signal and operator telemetry."""
        self.signal_header_text.value = f"{signal_pct}%"
        self.signal_val_text.value = f"{signal_pct}% ممتازة" if signal_pct > 0 else "0% (لا توجد إشارة)"
        self.signal_sub_text.value = f"{operator_name} ({self.modem.signal_dbm} dBm)" if self.modem.signal_dbm else operator_name
        if self.tray_manager:
            self.tray_manager.update_status(
                operator=operator_name,
                signal=signal_pct,
                is_in_call=self.is_in_call,
                caller=self.current_caller
            )
        try:
            self.page.update()
        except Exception:
            pass

    def _on_port_change(self, e):
        new_port = self.port_dropdown.value
        self.modem.connect(new_port)
        self.page.snack_bar = ft.SnackBar(ft.Text(f"تم التحويل إلى المنفذ: {new_port}"), bgcolor=COLOR_BURGUNDY)
        self.page.snack_bar.open = True
        self.page.update()

    def _on_pool_select_primary(self, port: str):
        if port in self.dongle_pool.modems:
            self.modem = self.dongle_pool.modems[port]
            self.port_dropdown.value = port
            self.page.update()

    def _handle_logout(self, e):
        self.audio_bridge.stop_pipeline()
        self.modem.disconnect()
        self.api_client.clear_session()
        if self.on_logout:
            self.on_logout()

    def _trigger_simulated_call(self, e):
        phone = (self.sim_caller_input.value or "").strip()
        if not phone:
            self.page.snack_bar = ft.SnackBar(ft.Text("يرجى إدخال رقم هاتف للمحاكاة أولاً"), bgcolor=COLOR_BURGUNDY)
            self.page.snack_bar.open = True
            self.page.update()
            return
        self.modem.simulate_incoming_call(phone)

    def _on_pool_incoming_call(self, caller_number: str, dongle_port: str):
        logger.info(f"Incoming call via Pool on {dongle_port}: {caller_number}")
        self._on_modem_incoming_call(caller_number)

    def _on_modem_incoming_call(self, caller_number: str):
        """Incoming cellular call ring detected."""
        if self.is_in_call:
            return

        self.is_in_call = True
        self.call_direction = "inbound"
        self.current_caller = caller_number
        self.call_start_time = time.time()

        # 1. Answer modem call via ATA
        self.modem.answer_call()

        # 2. Request LiveKit Room from Cloud API
        res = self.api_client.init_call(caller_phone=caller_number, dongle_id=self.modem.port)
        if res.get("success"):
            data = res.get("data", {})
            self.current_room = data.get("room_name", "")
            self.current_session_id = data.get("session_id")
        else:
            self.current_room = f"gsm_room_{int(time.time())}"

        # 3. Start Live Audio Pipeline & Waveform
        self.audio_bridge.start_pipeline(self.current_room, self.api_client.livekit_url)

        # 4. Update UI & Tray Notification
        self.call_badge_text.value = "📞 مكالمة واردة نشطة عبر الشريحة"
        self.caller_number_text.value = self.current_caller
        self.call_timer_text.value = "00:01"
        self.active_call_card.visible = True
        self._switch_tab(0)  # Return to Home tab to show Hero call card
        self.nav_bar.selected_index = 0

        if self.tray_manager:
            self.tray_manager.update_status(
                operator=self.modem.operator_name,
                signal=self.modem.signal_strength,
                is_in_call=True,
                caller=caller_number
            )
            # Dispatch notification if window is minimized or hidden in tray
            window_ctrl = getattr(self.page, "window", None)
            is_hidden = not getattr(window_ctrl, "visible", True) or getattr(window_ctrl, "minimized", False)
            if is_hidden:
                self.tray_manager.show_notification(
                    "📞 مكالمة هاتفية واردة",
                    f"اتصال من الرقم {caller_number} — جارٍ ربط المكالمة بالذكاء الاصطناعي."
                )

        self.page.update()

    def _handle_dialpad_call(self, destination_number: str, target: str):
        """Outbound call initiated from DialpadView."""
        if self.is_in_call:
            return

        self.is_in_call = True
        self.call_direction = "outbound"
        self.current_caller = destination_number
        self.call_start_time = time.time()

        # 1. Dial modem call via ATD
        self.modem.dial_call(destination_number)

        # 2. Request LiveKit Room from Cloud API
        res = self.api_client.init_call(caller_phone=destination_number, dongle_id=self.modem.port)
        if res.get("success"):
            data = res.get("data", {})
            self.current_room = data.get("room_name", "")
            self.current_session_id = data.get("session_id")
        else:
            self.current_room = f"outbound_gsm_{int(time.time())}"

        # 3. Start Audio Bridge
        self.audio_bridge.start_pipeline(self.current_room, self.api_client.livekit_url)

        # 4. Update UI
        self.call_badge_text.value = "📤 مكالمة صادرة نشطة عبر الشريحة"
        self.caller_number_text.value = destination_number
        self.call_timer_text.value = "00:01"
        self.active_call_card.visible = True
        self.dialpad_tab.set_calling_state(True, "المكالمة متصلة الآن")
        self.page.update()

    def _toggle_mute(self, e):
        self.is_muted = not self.is_muted
        self.audio_bridge.set_mute(self.is_muted)
        self.mute_btn.content = "إلغاء الكتم" if self.is_muted else "كتم الصوت"
        self.mute_btn.icon = ft.Icons.MIC_ROUNDED if self.is_muted else ft.Icons.MIC_OFF_ROUNDED
        self.page.update()

    def _on_modem_call_ended(self):
        self._end_call()

    def _end_call(self):
        """Terminate call, stop audio bridge, and persist to SQLite."""
        if not self.is_in_call:
            return

        self.is_in_call = False
        duration = int(time.time() - self.call_start_time) if self.call_start_time else 0
        self.audio_bridge.stop_pipeline()
        self.modem.hangup_call()

        # Report to Cloud API
        if self.current_room:
            self.api_client.hangup_call(
                room_name=self.current_room,
                duration_seconds=duration,
                session_id=self.current_session_id
            )

        # Persist to local SQLite
        self.storage.add_call_log(
            caller_phone=self.current_caller,
            direction=self.call_direction,
            duration=max(duration, 1),
            status="completed",
            room_name=self.current_room,
            dongle_port=self.modem.port
        )

        # Update stats
        self.total_calls_today += 1
        self.recent_calls.append({"phone": self.current_caller, "duration": max(duration, 1)})
        total_today = self.storage.get_total_calls_today()
        self.calls_count_text.value = f"{total_today} مكالمة"
        self._render_recent_calls()

        # Reset UI & Tray
        self.is_in_call = False
        self.active_call_card.visible = False
        self.dialpad_tab.set_calling_state(False)

        if self.tray_manager:
            self.tray_manager.update_status(
                operator=self.modem.operator_name,
                signal=self.modem.signal_strength,
                is_in_call=False,
                caller=""
            )

        self.page.update()

    def cleanup(self):
        """Clean up audio pipeline and disconnect hardware safely on app exit."""
        try:
            self.audio_bridge.stop_pipeline()
            self.audio_bridge.stop_ping_monitor()
            self.modem.disconnect()
            if hasattr(self, "dongle_pool"):
                for m in self.dongle_pool.modems.values():
                    m.disconnect()
        except Exception:
            pass

    def build(self) -> ft.Control:
        return ft.Container(
            bgcolor=COLOR_CREAM,
            expand=True,
            content=ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    self.header,
                    self.tab_content,
                    self.nav_bar,
                ],
            ),
        )
