"""Multi-SIM Dongle Pool Management View.

Allows business owners to:
1. View all plugged USB Modems / SIM Cards simultaneously.
2. Monitor per-dongle network operator, signal %, and active call state.
3. Refresh ports and trigger test calls on specific dongles.
"""
import flet as ft
from theme import (
    COLOR_BURGUNDY,
    COLOR_BURGUNDY_LIGHT,
    COLOR_WHITE,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_GREEN,
    COLOR_GREEN_BG,
    COLOR_GREEN_TEXT,
    COLOR_RED,
    COLOR_RED_BG,
)


class PoolView:
    def __init__(self, page: ft.Page, dongle_pool, on_select_primary):
        self.page = page
        self.pool = dongle_pool
        self.on_select_primary = on_select_primary
        self.devices_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.refresh_devices()

    def refresh_devices(self):
        self.pool.auto_discover_modems()
        self.devices_column.controls.clear()
        modems = self.pool.get_all_modems()
        if not modems:
            self.devices_column.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("لم يتم العثور على أجهزة مودم USB متصلة حالياً", size=12, color=COLOR_TEXT_MUTED),
                )
            )
            return

        for m in modems:
            port = m["port"]
            op = m["operator"]
            sig = m["signal_strength"]
            is_call = m["is_in_call"]
            status_text = "📞 في مكالمة" if is_call else "جاهز للاستقبال"
            status_color = COLOR_BURGUNDY if is_call else COLOR_GREEN_TEXT
            status_bg = COLOR_BURGUNDY_LIGHT if is_call else COLOR_GREEN_BG

            card = ft.Container(
                bgcolor=COLOR_WHITE,
                padding=12,
                border=ft.Border.all(1, COLOR_BORDER_LIGHT),
                border_radius=12,
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=6,
                                    controls=[
                                        ft.Icon(ft.Icons.USB_ROUNDED, color=COLOR_BURGUNDY, size=18),
                                        ft.Text(f"المنفذ: {port}", size=13, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                                    ],
                                ),
                                ft.Container(
                                    content=ft.Text(status_text, size=10, color=status_color, weight=ft.FontWeight.BOLD),
                                    bgcolor=status_bg,
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=8,
                                ),
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"شبكة: {op}", size=11, color=COLOR_TEXT_SECONDARY),
                                ft.Text(f"إشارة: {sig}% ({m['signal_dbm']} dBm)", size=11, color=COLOR_TEXT_MUTED),
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"IMEI: {m['imei']}", size=9, color=COLOR_TEXT_MUTED),
                                ft.TextButton(
                                    "تعيين كمنفذ رئيسي",
                                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                    on_click=lambda e, p=port: self._set_primary(p),
                                ),
                            ],
                        ),
                    ],
                ),
            )
            self.devices_column.controls.append(card)

    def _set_primary(self, port: str):
        if self.on_select_primary:
            self.on_select_primary(port)
        self.page.snack_bar = ft.SnackBar(ft.Text(f"تم تعيين [{port}] كمنفذ أساسي للاتصال!"), bgcolor=COLOR_BURGUNDY)
        self.page.snack_bar.open = True
        self.page.update()

    def _on_scan_click(self, e):
        self.refresh_devices()
        self.page.snack_bar = ft.SnackBar(ft.Text("تم إعادة فحص واكتشاف منافذ الـ USB!"), bgcolor=COLOR_GREEN)
        self.page.snack_bar.open = True
        self.page.update()

    def build(self) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("مجمع الشرائح والفلاشات (Multi-Dongle Pool)", size=13, weight=ft.FontWeight.BOLD, color=COLOR_BURGUNDY),
                            ft.IconButton(ft.Icons.REFRESH_ROUNDED, tooltip="إعادة فحص المنافذ", on_click=self._on_scan_click),
                        ],
                    ),
                    ft.Text("الفلاشات والشرائح المتصلة المكتشفة تلقائياً:", size=11, color=COLOR_TEXT_MUTED),
                    ft.Container(expand=True, content=self.devices_column),
                ],
            ),
        )
