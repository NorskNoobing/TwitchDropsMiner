from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict

import flet as ft

from translate import _
from constants import PriorityMode

if TYPE_CHECKING:
    from webui.app import WebUIManager
    from settings import Settings
    from inventory import DropsCampaign, TimedDrop


class CampaignDisplay(TypedDict):
    container: ft.Container
    status_text: ft.Text


class InventoryOverview:
    """Inventory overview component displaying campaigns and drops."""

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._settings: Settings | None = None
        self._campaigns: dict[DropsCampaign, CampaignDisplay] = {}
        self._drops: dict[str, ft.Text] = {}

        # Filter checkboxes
        self._filters = {
            "not_linked": ft.Checkbox(label=_("gui", "inventory", "filter", "not_linked"), value=False),
            "upcoming": ft.Checkbox(label=_("gui", "inventory", "filter", "upcoming"), value=True),
            "expired": ft.Checkbox(label=_("gui", "inventory", "filter", "expired"), value=False),
            "excluded": ft.Checkbox(label=_("gui", "inventory", "filter", "excluded"), value=False),
            "finished": ft.Checkbox(label=_("gui", "inventory", "filter", "finished"), value=False),
        }

        self._refresh_button = ft.ElevatedButton(
            content=ft.Text(_("gui", "inventory", "filter", "refresh")),
        )
        self._refresh_button.on_click = lambda e: self.refresh()

        # Filter row
        filter_row = ft.Row(
            controls=[
                ft.Text(_("gui", "inventory", "filter", "show"), size=12),
                *self._filters.values(),
                self._refresh_button,
            ],
            wrap=True,
            spacing=10,
        )

        # Campaign list
        self._campaign_column = ft.Column(
            controls=[],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=filter_row,
                        padding=8,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                    ),
                    ft.Container(
                        content=self._campaign_column,
                        expand=True,
                        padding=8,
                    ),
                ],
                spacing=8,
                expand=True,
            ),
            padding=8,
            expand=True,
        )

    def _get_settings(self) -> Settings | None:
        """Get settings from manager."""
        if self._settings is None and self._manager._twitch:
            self._settings = self._manager._twitch.settings
        return self._settings

    def get_status(self, campaign: DropsCampaign) -> tuple[str, str]:
        """Get status text and color for a campaign."""
        if campaign.active:
            status_text = _("gui", "inventory", "status", "active")
            status_color = "green"
        elif campaign.upcoming:
            status_text = _("gui", "inventory", "status", "upcoming")
            status_color = "goldenrod"
        else:
            status_text = _("gui", "inventory", "status", "expired")
            status_color = "red"
        return (status_text, status_color)

    def _update_visibility(self, campaign: DropsCampaign) -> bool:
        """Check if campaign should be visible based on filters."""
        settings = self._get_settings()
        if settings is None:
            return True

        not_linked = self._filters["not_linked"].value
        expired = self._filters["expired"].value
        excluded = self._filters["excluded"].value
        upcoming = self._filters["upcoming"].value
        finished = self._filters["finished"].value
        priority_only = settings.priority_mode is PriorityMode.PRIORITY_ONLY

        return (
            campaign.required_minutes > 0  # Don't show sub-only campaigns
            and (not_linked or campaign.eligible)
            and (campaign.active or (upcoming and campaign.upcoming) or (expired and campaign.expired))
            and (
                excluded or (
                    campaign.game.name not in settings.exclude
                    and (not priority_only or campaign.game.name in settings.priority)
                )
            )
            and (finished or not campaign.finished)
        )

    async def add_campaign(self, campaign: DropsCampaign) -> None:
        """Add a campaign to the inventory display."""
        status_text, status_color = self.get_status(campaign)

        # Create campaign card
        status_label = ft.Text(status_text, color=status_color, size=12)

        # Ends/Starts time
        ends_at = campaign.ends_at.astimezone().replace(microsecond=0, tzinfo=None)
        starts_at = campaign.starts_at.astimezone().replace(microsecond=0, tzinfo=None)
        time_text = _("gui", "inventory", "ends").format(time=ends_at)
        if campaign.upcoming:
            time_text = _("gui", "inventory", "starts").format(time=starts_at)

        # Linking status
        if campaign.eligible:
            link_text = _("gui", "inventory", "status", "linked")
            link_color = "green"
        else:
            link_text = _("gui", "inventory", "status", "not_linked")
            link_color = "red"

        # ACL channels
        acl = campaign.allowed_channels
        if acl:
            if len(acl) <= 5:
                allowed_text = '\n'.join(ch.name for ch in acl)
            else:
                allowed_text = '\n'.join(ch.name for ch in acl[:4])
                allowed_text += f"\n{_('gui', 'inventory', 'and_more').format(amount=len(acl) - 4)}"
        else:
            allowed_text = _("gui", "inventory", "all_channels")

        # Drops display
        drop_controls = []
        for drop in campaign.drops:
            progress_text, progress_color = self._get_drop_progress_text(drop)
            drop_label = ft.Text(progress_text, color=progress_color if progress_color else None, size=11)
            self._drops[drop.id] = drop_label

            benefits_text = ", ".join(b.name for b in drop.benefits)
            drop_card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(benefits_text, size=11, weight=ft.FontWeight.BOLD),
                        drop_label,
                    ],
                    spacing=2,
                ),
                padding=8,
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=4,
            )
            drop_controls.append(drop_card)

        campaign_card = ft.Container(
            content=ft.Row(
                controls=[
                    # Campaign info
                    ft.Column(
                        controls=[
                            ft.Text(campaign.name, size=12, weight=ft.FontWeight.BOLD),
                            status_label,
                            ft.Text(time_text, size=11),
                            ft.Text(link_text, color=link_color, size=11),
                            ft.Text(f"{_('gui', 'inventory', 'allowed_channels')}\n{allowed_text}", size=10),
                        ],
                        spacing=4,
                        width=250,
                    ),
                    ft.VerticalDivider(width=1),
                    # Drops
                    ft.Row(
                        controls=drop_controls,
                        spacing=8,
                        wrap=True,
                        expand=True,
                    ),
                ],
                spacing=16,
            ),
            padding=12,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )

        self._campaigns[campaign] = {
            "container": campaign_card,
            "status_text": status_label,
        }

        # Add to display if visible
        if self._update_visibility(campaign):
            self._campaign_column.controls.append(campaign_card)

        if self._manager._page:
            self._manager._page.update()

    def _get_drop_progress_text(self, drop: TimedDrop) -> tuple[str, str]:
        """Get progress text and color for a drop."""
        progress_text: str
        progress_color: str = ""

        if drop.is_claimed:
            progress_color = "green"
            progress_text = _("gui", "inventory", "status", "claimed")
        elif drop.can_claim:
            progress_color = "goldenrod"
            progress_text = _("gui", "inventory", "status", "ready_to_claim")
        elif drop.current_minutes or drop.can_earn():
            progress_text = _("gui", "inventory", "percent_progress").format(
                percent=f"{drop.progress:3.1%}",
                minutes=drop.required_minutes,
            )
            if drop.ends_at < drop.campaign.ends_at:
                progress_text += '\n' + _("gui", "inventory", "ends").format(
                    time=drop.ends_at.astimezone().replace(microsecond=0, tzinfo=None)
                )
        else:
            if drop.required_minutes > 0:
                progress_text = _("gui", "inventory", "minutes_progress").format(
                    minutes=drop.required_minutes
                )
            else:
                progress_text = ""
            if datetime.now(timezone.utc) < drop.starts_at > drop.campaign.starts_at:
                progress_text += '\n' + _("gui", "inventory", "starts").format(
                    time=drop.starts_at.astimezone().replace(microsecond=0, tzinfo=None)
                )
            elif drop.ends_at < drop.campaign.ends_at:
                progress_text += '\n' + _("gui", "inventory", "ends").format(
                    time=drop.ends_at.astimezone().replace(microsecond=0, tzinfo=None)
                )

        return (progress_text, progress_color)

    def clear(self) -> None:
        """Clear all campaigns from the display."""
        self._campaign_column.controls.clear()
        self._drops.clear()
        self._campaigns.clear()
        if self._manager._page:
            self._manager._page.update()

    def update_drop(self, drop: TimedDrop) -> None:
        """Update a drop's progress display."""
        label = self._drops.get(drop.id)
        if label is None:
            return
        progress_text, progress_color = self._get_drop_progress_text(drop)
        label.value = progress_text
        label.color = progress_color if progress_color else None
        if self._manager._page:
            self._manager._page.update()

    def refresh(self) -> None:
        """Refresh the inventory display based on filters."""
        self._campaign_column.controls.clear()

        for campaign, display in self._campaigns.items():
            # Update status
            status_text, status_color = self.get_status(campaign)
            display["status_text"].value = status_text
            display["status_text"].color = status_color

            # Update visibility
            if self._update_visibility(campaign):
                self._campaign_column.controls.append(display["container"])

        if self._manager._page:
            self._manager._page.update()

    def configure_theme(self, *, bg: str) -> None:
        """Configure theme background color."""
        self._container.bgcolor = bg

    def build(self) -> ft.Container:
        """Build and return the inventory overview control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the inventory overview."""
        self._container.bgcolor = colors["bg"]

        # Update filter checkboxes
        for checkbox in self._filters.values():
            checkbox.label_style = ft.TextStyle(color=colors["fg"])

        # Update campaign cards
        for display in self._campaigns.values():
            container = display["container"]
            container.border = ft.border.all(1, colors["border"])
            container.bgcolor = colors["surface"]
