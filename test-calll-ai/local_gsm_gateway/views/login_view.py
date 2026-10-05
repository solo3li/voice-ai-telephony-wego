"""Owner Login View for Local GSM USB Dongle Gateway App.

Allows the business owner to login using strictly their Username and Password (NO email).
Features Auto-Login / Remember Session and elegant brand typography.
"""
import flet as ft
from theme import (
    COLOR_BURGUNDY,
    COLOR_BURGUNDY_HOVER,
    COLOR_CREAM,
    COLOR_WHITE,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_RED,
)
from controllers.api_client import DongleApiClient, DEFAULT_SERVER_URL


class LoginView:
    def __init__(self, page: ft.Page, api_client: DongleApiClient, on_login_success):
        self.page = page
        self.api_client = api_client
        self.on_login_success = on_login_success

        # Inputs (Username and Password ONLY - NO email!)
        self.username_input = ft.TextField(
            label="اسم المستخدم (Username)",
            hint_text="أدخل اسم مستخدم المالك",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            text_style=ft.TextStyle(color=COLOR_TEXT_PRIMARY, size=14),
            border_radius=12,
            autofocus=True,
        )

        self.password_input = ft.TextField(
            label="كلمة المرور (Password)",
            hint_text="••••••••",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            text_style=ft.TextStyle(color=COLOR_TEXT_PRIMARY, size=14),
            border_radius=12,
        )

        self.server_url_input = ft.TextField(
            label="رابط السيرفر السحابي (Server URL)",
            value=self.api_client.server_url or DEFAULT_SERVER_URL,
            prefix_icon=ft.Icons.CLOUD_OUTLINED,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_BURGUNDY,
            text_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=12),
            border_radius=12,
        )

        self.remember_checkbox = ft.Checkbox(
            label="تذكر تسجيل الدخول (Auto-login)",
            value=True,
            fill_color={ft.ControlState.SELECTED: COLOR_BURGUNDY},
        )

        self.error_text = ft.Text(
            value="",
            color=COLOR_RED,
            size=12,
            weight=ft.FontWeight.W_600,
            visible=False,
            text_align=ft.TextAlign.CENTER,
        )

        self.loading_indicator = ft.ProgressRing(
            visible=False,
            width=20,
            height=20,
            stroke_width=2.5,
            color=COLOR_WHITE,
        )

        self.login_btn_text = ft.Text("تسجيل الدخول وبدء البوابة", color=COLOR_WHITE, weight=ft.FontWeight.BOLD, size=14)

        self.login_button = ft.FilledButton(
            content=ft.Row(
                controls=[self.loading_indicator, self.login_btn_text],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor=COLOR_BURGUNDY,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                overlay_color={ft.ControlState.HOVERED: COLOR_BURGUNDY_HOVER},
            ),
            height=48,
            on_click=self._handle_login,
        )

    def _handle_login(self, e):
        username = (self.username_input.value or "").strip()
        password = (self.password_input.value or "").strip()
        server_url = (self.server_url_input.value or "").strip() or DEFAULT_SERVER_URL

        if not username or not password:
            self._show_error("يرجى إدخال اسم المستخدم وكلمة المرور")
            return

        self._set_loading(True)
        self.api_client.set_server_url(server_url)

        res = self.api_client.login(username, password, remember=self.remember_checkbox.value)
        self._set_loading(False)

        if res.get("success"):
            self.error_text.visible = False
            self.page.update()
            if self.on_login_success:
                self.on_login_success()
        else:
            self._show_error(res.get("error", "فشل تسجيل الدخول"))

    def _show_error(self, message: str):
        self.error_text.value = message
        self.error_text.visible = True
        self.page.update()

    def _set_loading(self, is_loading: bool):
        self.loading_indicator.visible = is_loading
        self.login_button.disabled = is_loading
        self.login_btn_text.value = "جاري التحقق..." if is_loading else "تسجيل الدخول وبدء البوابة"
        self.page.update()

    def build(self) -> ft.Control:
        return ft.Container(
            expand=True,
            bgcolor=COLOR_CREAM,
            alignment=ft.Alignment.CENTER,
            padding=20,
            content=ft.Card(
                elevation=2,
                bgcolor=COLOR_WHITE,
                shape=ft.RoundedRectangleBorder(radius=20),
                content=ft.Container(
                    padding=28,
                    width=380,
                    content=ft.Column(
                        spacing=16,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                        controls=[
                            # Brand Logo (Modern 3D SIM & Voice AI emblem)
                            ft.Container(
                                width=76,
                                height=76,
                                border_radius=20,
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                shadow=ft.BoxShadow(blur_radius=14, color="#7A152633", offset=ft.Offset(0, 4)),
                                content=ft.Image(
                                    src="logo.png",
                                    width=76,
                                    height=76,
                                    fit="cover",
                                    error_content=ft.Container(
                                        bgcolor=COLOR_BURGUNDY,
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.SIM_CARD_ROUNDED, color=COLOR_WHITE, size=36),
                                    ),
                                ),
                            ),
                            # Titles
                            ft.Text(
                                "بوابة الاتصال الخلوي الذكية",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=COLOR_BURGUNDY,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                "تسجيل دخول المالك (Owner Login)",
                                size=12,
                                color=COLOR_TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Divider(color=COLOR_BORDER, height=1),
                            # Form Fields
                            self.username_input,
                            self.password_input,
                            self.server_url_input,
                            self.remember_checkbox,
                            self.error_text,
                            # Submit Button
                            ft.Container(
                                content=self.login_button,
                                width=340,
                            ),
                            ft.Text(
                                "تحكم مباشر بشريحة المودم والذكاء الاصطناعي",
                                size=11,
                                color=COLOR_TEXT_MUTED,
                            ),
                        ],
                    ),
                ),
            ),
        )
