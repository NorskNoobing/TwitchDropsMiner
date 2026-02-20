from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from translate import _
from webui.utils import webopen

if TYPE_CHECKING:
    from webui.app import WebUIManager


class HelpTab:
    """Help tab component with about section and useful links."""

    WIDTH = 800

    def __init__(self, manager: WebUIManager):
        self._manager = manager

        # Create buttons with click handlers assigned separately
        btn_devilxd = ft.TextButton(content=ft.Text("DevilXD"))
        btn_devilxd.on_click = lambda e: webopen("https://github.com/DevilXD")

        btn_repo = ft.TextButton(content=ft.Text("https://github.com/DevilXD/TwitchDropsMiner"))
        btn_repo.on_click = lambda e: webopen("https://github.com/DevilXD/TwitchDropsMiner")

        btn_donate = ft.TextButton(
            content=ft.Text(
                "If you like the application and found it useful, "
                "please consider donating a small amount of money to support me. Thank you!"
            )
        )
        btn_donate.on_click = lambda e: webopen("https://www.buymeacoffee.com/DevilXD")

        btn_inventory = ft.TextButton(content=ft.Text(_("gui", "help", "links", "inventory")))
        btn_inventory.on_click = lambda e: webopen("https://www.twitch.tv/drops/inventory")

        btn_campaigns = ft.TextButton(content=ft.Text(_("gui", "help", "links", "campaigns")))
        btn_campaigns.on_click = lambda e: webopen("https://www.twitch.tv/drops/campaigns")

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    # About section
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("About", weight=ft.FontWeight.BOLD, size=14),
                                ft.Row([
                                    ft.Text("Application created by: "),
                                    btn_devilxd,
                                ]),
                                ft.Row([
                                    ft.Text("Repository: "),
                                    btn_repo,
                                ]),
                                ft.Divider(),
                                ft.Row([
                                    ft.Text("Donate: "),
                                    btn_donate,
                                ]),
                            ],
                            spacing=4,
                        ),
                        padding=12,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                    ),
                    # Useful links section
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(_("gui", "help", "links", "name"), weight=ft.FontWeight.BOLD, size=14),
                                btn_inventory,
                                btn_campaigns,
                            ],
                            spacing=4,
                        ),
                        padding=12,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                    ),
                    # How It Works section
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(_("gui", "help", "how_it_works"), weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(
                                    _("gui", "help", "how_it_works_text"),
                                    size=12,
                                    width=self.WIDTH,
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=12,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                    ),
                    # Getting Started section
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(_("gui", "help", "getting_started"), weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(
                                    _("gui", "help", "getting_started_text"),
                                    size=12,
                                    width=self.WIDTH,
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=12,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=16,
            expand=True,
        )

    def build(self) -> ft.Container:
        """Build and return the help tab control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the help tab."""
        self._container.bgcolor = colors["bg"]

        # Update all text colors in the container
        def update_colors(control):
            if isinstance(control, ft.Text):
                control.color = colors["fg"]
            elif isinstance(control, ft.TextButton):
                control.style = ft.ButtonStyle(color=colors["link"])
            elif isinstance(control, ft.Container):
                control.border = ft.border.all(1, colors["border"])
                control.bgcolor = colors["surface"]
                if control.content:
                    update_colors(control.content)
            elif isinstance(control, ft.Column):
                for child in control.controls:
                    update_colors(child)
            elif isinstance(control, ft.Row):
                for child in control.controls:
                    update_colors(child)

        if self._container.content:
            update_colors(self._container.content)
