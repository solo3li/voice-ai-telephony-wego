"""Dialpad View for Outbound GSM Calls.

Provides an interactive mobile-style keypad (0-9, *, #, +)
to initiate outbound phone calls through the connected GSM Dongle
and automatically bridge them to LiveKit / Voice AI or Human Agents.
"""
import flet as ft
from theme import (
    COLOR_BURGUNDY,
    COLOR_BURGUNDY_LIGHT,
    COLOR_WHITE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_RED_BG,
)


class DialpadView:
    def __init__(self, page: ft.Page, on_dial: callable, on_hangup: callable):
        self.page = page
        self.on_dial = on_dial
        self.on_hangup = on_hangup
        self.number_input = ft.TextField(
            value="",
            hint_text="أدخل رقم الهاتف...",
            text_align=ft.TextAlign.CENTER,
            text_size=22,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            border_radius=14,
            cursor_color=COLOR_BURGUNDY,
            autofocus=False,
            read_only=False,
        )

        self.call_target_dropdown = ft.Dropdown(
            label="وجهة المكالمة الصادرة",
            value="ai_agent",
            options=[
                ft.dropdown.Option("ai_agent", "🤖 المساعد الذكي (AI Agent)"),
                ft.dropdown.Option("human_queue", "🎧 تحويل لموظف خدمة العملاء"),
            ],
            border_radius=10,
            text_size=12,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            dense=True,
        )

        self.status_banner = ft.Container(
            visible=False,
            bgcolor=COLOR_BURGUNDY_LIGHT,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=10,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=COLOR_BURGUNDY),
                    ft.Text("جاري الاتصال عبر الشريحة...", size=12, color=COLOR_BURGUNDY, weight=ft.FontWeight.BOLD),
                ],
            ),
        )

    def _append_digit(self, char: str):
        self.number_input.value = (self.number_input.value or "") + char
        self.page.update()

    def _backspace(self, e):
        val = self.number_input.value or ""
        if val:
            self.number_input.value = val[:-1]
            self.page.update()

    def _clear(self, e):
        self.number_input.value = ""
        self.page.update()

    def _handle_call_press(self, e):
        num = (self.number_input.value or "").strip()
        if not num:
            self.page.snack_bar = ft.SnackBar(ft.Text("يرجى إدخال رقم الهاتف أولاً"), bgcolor=COLOR_RED)
            self.page.snack_bar.open = True
            self.page.update()
            return

        self.status_banner.visible = True
        self.page.update()
        if self.on_dial:
            self.on_dial(num, self.call_target_dropdown.value)

    def set_calling_state(self, is_calling: bool, status_text: str = ""):
        self.status_banner.visible = is_calling
        if status_text and self.status_banner.content:
            row = self.status_banner.content
            if len(row.controls) > 1:
                row.controls[1].value = status_text
        self.page.update()

    def _build_key(self, digit: str, letters: str = "") -> ft.Container:
        return ft.Container(
            content=ft.Column(
                spacing=0,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(digit, size=20, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                    ft.Text(letters, size=8, color=COLOR_TEXT_MUTED) if letters else ft.Container(),
                ],
            ),
            width=68,
            height=54,
            bgcolor=COLOR_WHITE,
            border=ft.Border.all(1, COLOR_BORDER_LIGHT),
            border_radius=12,
            alignment=ft.Alignment(0, 0),
            ink=True,
            on_click=lambda e: self._append_digit(digit),
        )

    def build(self) -> ft.Control:
        keys = [
            [("1", ""), ("2", "ABC"), ("3", "DEF")],
            [("4", "GHI"), ("5", "JKL"), ("6", "MNO")],
            [("7", "PQRS"), ("8", "TUV"), ("9", "WXYZ")],
            [("*", ""), ("0", "+"), ("#", "")],
        ]

        keypad_rows = []
        for r in keys:
            row_controls = [self._build_key(d, l) for d, l in r]
            keypad_rows.append(ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=14, controls=row_controls))

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            content=ft.Column(
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("لوحة الاتصال الصادر (Outbound Dialpad)", size=14, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                    self.call_target_dropdown,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Container(content=self.number_input, expand=True),
                            ft.IconButton(ft.Icons.BACKSPACE_OUTLINED, icon_size=18, icon_color=COLOR_TEXT_MUTED, on_click=self._backspace),
                        ],
                    ),
                    self.status_banner,
                    ft.Container(height=4),
                    # Keypad
                    ft.Column(spacing=8, controls=keypad_rows),
                    ft.Container(height=8),
                    # Call Actions Row
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        controls=[
                            ft.FilledButton(
                                content="بدء الاتصال",
                                icon=ft.Icons.CALL,
                                bgcolor=COLOR_GREEN,
                                color=COLOR_WHITE,
                                height=46,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                                on_click=self._handle_call_press,
                            ),
                            ft.OutlinedButton(
                                content="إنهاء",
                                icon=ft.Icons.CALL_END,
                                height=46,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                    side=ft.BorderSide(1.5, COLOR_RED),
                                    color=COLOR_RED
                                ),
                                on_click=lambda e: self.on_hangup() if self.on_hangup else None,
                            ),
                        ],
                    ),
                ],
            ),
        )
