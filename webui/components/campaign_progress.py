from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from translate import _

if TYPE_CHECKING:
    from webui.app import WebUIManager
    from inventory import TimedDrop


class CampaignProgress:
    """Component displaying campaign and drop progress with timer countdown."""

    BAR_LENGTH = 420
    ALMOST_DONE_SECONDS = 10

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._drop: TimedDrop | None = None
        self._seconds: int = 0
        self._timer_task: asyncio.Task[None] | None = None

        # Campaign variables
        self._campaign_name = ft.Text("...", size=12, text_align=ft.TextAlign.CENTER)
        self._campaign_game = ft.Text("...", size=12, text_align=ft.TextAlign.CENTER)
        self._campaign_percentage = ft.Text("-%", size=12)
        self._campaign_remaining = ft.Text("", size=12)
        self._campaign_progress = ft.ProgressBar(value=0, width=self.BAR_LENGTH, height=10)

        # Drop variables
        self._drop_rewards = ft.Text("...", size=12, text_align=ft.TextAlign.CENTER)
        self._drop_percentage = ft.Text("-%", size=12)
        self._drop_remaining = ft.Text("", size=12)
        self._drop_progress = ft.ProgressBar(value=0, width=self.BAR_LENGTH, height=10)

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "progress", "name"), weight=ft.FontWeight.BOLD, size=12),
                    # Game and Campaign row
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(_("gui", "progress", "game"), size=11, weight=ft.FontWeight.BOLD),
                                    self._campaign_game,
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                expand=True,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(_("gui", "progress", "campaign"), size=11, weight=ft.FontWeight.BOLD),
                                    self._campaign_name,
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                expand=True,
                            ),
                        ],
                    ),
                    # Campaign progress
                    ft.Row(
                        controls=[
                            ft.Text(_("gui", "progress", "campaign_progress"), size=11),
                            ft.Column(
                                controls=[self._campaign_percentage, self._campaign_remaining],
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self._campaign_progress,
                    ft.Divider(height=1),
                    # Drop section
                    ft.Text(_("gui", "progress", "drop"), size=11, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    self._drop_rewards,
                    ft.Row(
                        controls=[
                            ft.Text(_("gui", "progress", "drop_progress"), size=11),
                            ft.Column(
                                controls=[self._drop_percentage, self._drop_remaining],
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self._drop_progress,
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.all(8),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )

    def _divmod(self, minutes: int) -> tuple[int, int]:
        """Calculate hours and minutes, accounting for seconds countdown."""
        if self._seconds < 60 and minutes > 0:
            minutes -= 1
        hours, minutes = divmod(minutes, 60)
        return (hours, minutes)

    def _update_time(self, seconds: int | None = None) -> None:
        """Update the time display."""
        if seconds is not None:
            self._seconds = seconds
        drop = self._drop
        if drop is not None:
            drop_minutes = drop.remaining_minutes
            campaign_minutes = drop.campaign.remaining_minutes
        else:
            drop_minutes = 0
            campaign_minutes = 0

        dseconds = self._seconds % 60
        hours, minutes = self._divmod(drop_minutes)
        self._drop_remaining.value = _("gui", "progress", "remaining").format(
            time=f"{hours:>2}:{minutes:02}:{dseconds:02}"
        )

        hours, minutes = self._divmod(campaign_minutes)
        self._campaign_remaining.value = _("gui", "progress", "remaining").format(
            time=f"{hours:>2}:{minutes:02}:{dseconds:02}"
        )

        if self._manager._page:
            self._manager._page.update()

    async def _timer_loop(self) -> None:
        """Timer loop for countdown display."""
        self._update_time(60)
        while self._seconds > 0:
            await asyncio.sleep(1)
            self._seconds -= 1
            self._update_time()
        self._timer_task = None

    def start_timer(self) -> None:
        """Start the countdown timer."""
        if self._timer_task is None:
            if self._drop is None or self._drop.remaining_minutes <= 0:
                # If starting at 0 drop minutes, just update to 60 seconds
                self._update_time(60)
            else:
                self._timer_task = asyncio.create_task(self._timer_loop())

    def stop_timer(self) -> None:
        """Stop the countdown timer."""
        if self._timer_task is not None:
            self._timer_task.cancel()
            self._timer_task = None

    def minute_almost_done(self) -> bool:
        """Check if the timer is almost done."""
        return self._timer_task is None or self._seconds <= self.ALMOST_DONE_SECONDS

    def display(
        self, drop: TimedDrop | None, *, countdown: bool = True, subone: bool = False
    ) -> None:
        """Display the drop and campaign progress."""
        self._drop = drop
        self.stop_timer()

        if drop is None:
            # Clear the drop display
            self._drop_rewards.value = "..."
            self._drop_progress.value = 0.0
            self._drop_percentage.value = "-%"
            self._campaign_name.value = "..."
            self._campaign_game.value = "..."
            self._campaign_progress.value = 0.0
            self._campaign_percentage.value = "-%"
            self._update_time(0)
            return

        # Update drop info
        self._drop_rewards.value = drop.rewards_text()
        self._drop_progress.value = drop.progress
        self._drop_percentage.value = f"{drop.progress:6.1%}"

        # Update campaign info
        campaign = drop.campaign
        self._campaign_name.value = campaign.name
        self._campaign_game.value = campaign.game.name
        self._campaign_progress.value = campaign.progress
        self._campaign_percentage.value = (
            f"{campaign.progress:6.1%} ({campaign.claimed_drops}/{campaign.total_drops})"
        )

        if countdown:
            # Restart the seconds update timer
            self.start_timer()
        elif subone:
            # Display current remaining time at 0 seconds
            self._update_time(0)
        else:
            # Display full time with no subtracting
            self._update_time(60)

        if self._manager._page:
            self._manager._page.update()

    def build(self) -> ft.Container:
        """Build and return the campaign progress control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the campaign progress."""
        self._container.bgcolor = colors["surface"]
        self._container.border = ft.border.all(1, colors["border"])

        # Update text colors
        for text_control in [
            self._campaign_name,
            self._campaign_game,
            self._campaign_percentage,
            self._campaign_remaining,
            self._drop_rewards,
            self._drop_percentage,
            self._drop_remaining,
        ]:
            text_control.color = colors["fg"]

        # Update progress bar colors
        self._campaign_progress.color = colors["accent"]
        self._campaign_progress.bgcolor = colors["bg"]
        self._drop_progress.color = colors["accent"]
        self._drop_progress.bgcolor = colors["bg"]

        # Update title color
        if self._container.content and isinstance(self._container.content, ft.Column):
            for control in self._container.content.controls:
                if isinstance(control, ft.Text):
                    control.color = colors["fg"]
                elif isinstance(control, ft.Row):
                    for sub in control.controls:
                        if isinstance(sub, ft.Text):
                            sub.color = colors["fg"]
                        elif isinstance(sub, ft.Column):
                            for sub2 in sub.controls:
                                if isinstance(sub2, ft.Text):
                                    sub2.color = colors["fg"]
