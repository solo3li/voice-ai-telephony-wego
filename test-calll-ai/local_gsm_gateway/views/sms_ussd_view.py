"""SMS & USSD View for Local GSM Dongle Gateway.

Enables business owners to:
1. View and send SMS text messages directly via the SIM card.
2. Execute cellular network USSD codes (e.g., *888#, *100#, *1#)
   to check balance, quota, and expiry dates safely.
"""
import flet as ft
from theme import (
    COLOR_BURGUNDY,
    COLOR_BURGUNDY_LIGHT,
    COLOR_WHITE,
    COLOR_CREAM,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_GREEN,
    COLOR_GREEN_BG,
    COLOR_GREEN_TEXT,
)


class SmsUssdView:
    def __init__(self, page: ft.Page, modem_controller, storage_manager):
        self.page = page
        self.modem = modem_controller
        self.storage = storage_manager

        # SMS Components
        self.sms_phone_input = ft.TextField(
            label="رقم الهاتف المستلم",
            hint_text="مثال: +201000000000",
            border_radius=10,
            text_size=12,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            dense=True,
        )
        self.sms_msg_input = ft.TextField(
            label="نص الرسالة",
            hint_text="اكتب الرسالة هنا...",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=10,
            text_size=12,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            dense=True,
        )
        self.sms_list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

        # USSD Components
        self.ussd_input = ft.TextField(
            label="كود الشبكة (USSD Code)",
            value="",
            hint_text="مثال: *888# أو *100# أو *1#",
            border_radius=10,
            text_size=13,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            dense=True,
        )
        self.ussd_response_card = ft.Container(
            bgcolor=COLOR_WHITE,
            padding=12,
            border=ft.Border.all(1, COLOR_BORDER_LIGHT),
            border_radius=12,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Text("رد الشبكة المباشر:", size=11, color=COLOR_TEXT_MUTED, weight=ft.FontWeight.W_600),
                    ft.Text("اضغط على أحد أكواد الرصيد بالأسفل أو أدخل كود واضغط استعلام.", size=12, color=COLOR_TEXT_PRIMARY),
                ],
            ),
        )

        self._load_sms_messages()

    def _load_sms_messages(self):
        self.sms_list_col.controls.clear()
        messages = self.storage.get_sms_messages(limit=15)
        if not messages and self.modem.is_connected and not ("SIMULATED" in getattr(self.modem, "port", "")):
            # Only poll real hardware SIM when connected
            modem_msgs = self.modem.read_all_sms()
            for m in modem_msgs:
                self.storage.add_sms(m.get("sender", ""), m.get("text", ""), direction="inbound", dongle_port=self.modem.port)
            messages = self.storage.get_sms_messages(limit=15)

        if not messages:
            self.sms_list_col.controls.append(
                ft.Container(
                    padding=16,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("لا توجد رسائل SMS مسجلة حتى الآن", size=12, color=COLOR_TEXT_MUTED),
                )
            )
            return

        for m in messages:
            is_out = m.get("direction") == "outbound"
            self.sms_list_col.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    bgcolor=COLOR_WHITE if not is_out else COLOR_BURGUNDY_LIGHT,
                    border=ft.Border.all(1, COLOR_BORDER_LIGHT),
                    border_radius=10,
                    content=ft.Column(
                        spacing=2,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"{'📤 إلى:' if is_out else '📩 من:'} {m['phone_number']}", size=11, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                                    ft.Text(m.get("created_at", "")[:16], size=9, color=COLOR_TEXT_MUTED),
                                ],
                            ),
                            ft.Text(m["message_text"], size=11, color=COLOR_TEXT_PRIMARY),
                        ],
                    ),
                )
            )

    def _send_sms_click(self, e):
        phone = (self.sms_phone_input.value or "").strip()
        text = (self.sms_msg_input.value or "").strip()
        if not phone or not text:
            self.page.snack_bar = ft.SnackBar(ft.Text("يرجى كتابة رقم الهاتف ونص الرسالة"), bgcolor=COLOR_BURGUNDY)
            self.page.snack_bar.open = True
            self.page.update()
            return

        ok = self.modem.send_sms(phone, text)
        if ok:
            self.storage.add_sms(phone, text, direction="outbound", dongle_port=self.modem.port)
            self.sms_msg_input.value = ""
            self._load_sms_messages()
            self.page.snack_bar = ft.SnackBar(ft.Text("تم إرسال الرسالة بنجاح عبر الشريحة!"), bgcolor=COLOR_GREEN)
            self.page.snack_bar.open = True
            self.page.update()

    def _execute_ussd_click(self, code: str):
        if not code:
            code = (self.ussd_input.value or "").strip()
        self.ussd_input.value = code
        self.page.update()

        resp = self.modem.execute_ussd(code)
        self.storage.add_ussd_record(code, resp, dongle_port=self.modem.port)

        # Update response box
        self.ussd_response_card.content.controls[1].value = resp
        self.page.update()

    def build(self) -> ft.Control:
        quick_ussd = [
            ("*1#", "معرفة رقم الخط"),
            ("*100#", "خدمات الشبكة"),
            ("*888#", "استعلام الرصيد"),
            ("*60#", "باقة الإنترنت"),
        ]

        ussd_buttons = [
            ft.Chip(
                label=f"{code} ({label})",
                on_click=lambda e, c=code: self._execute_ussd_click(c),
            )
            for code, label in quick_ussd
        ]

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Column(
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    # Section 1: USSD & Balance
                    ft.Text("⚡ استعلام الرصيد والباقات (USSD Codes)", size=13, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Container(content=self.ussd_input, expand=True),
                            ft.FilledButton(content="استعلام", bgcolor=COLOR_BURGUNDY, color=COLOR_WHITE, height=40, on_click=lambda e: self._execute_ussd_click(self.ussd_input.value)),
                        ],
                    ),
                    ft.Row(spacing=6, wrap=True, controls=ussd_buttons),
                    self.ussd_response_card,

                    ft.Divider(height=1, color=COLOR_BORDER_LIGHT),

                    # Section 2: SMS Messages
                    ft.Text("💬 رسائل الشريحة القصيرة (SIM SMS Messages)", size=13, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                    self.sms_phone_input,
                    self.sms_msg_input,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            ft.FilledButton(content="إرسال رسالة SMS", icon=ft.Icons.SEND_ROUNDED, bgcolor=COLOR_BURGUNDY, color=COLOR_WHITE, on_click=self._send_sms_click)
                        ]
                    ),
                    ft.Text("الوارد والمرسل مؤخراً:", size=11, color=COLOR_TEXT_MUTED, weight=ft.FontWeight.W_600),
                    ft.Container(height=140, content=self.sms_list_col),
                ],
            ),
        )
