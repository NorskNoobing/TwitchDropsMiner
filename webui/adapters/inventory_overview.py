from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from constants import PriorityMode
from webui.notifications import NotificationEvent

if TYPE_CHECKING:
    from webui.manager import WebUIManager


class InventoryOverviewAdapter:
    """
    Mirrors InventoryOverview - triggers inventory panel refreshes
    when the backend calls clear/add_campaign/update_drop.
    Campaign data is read directly from twitch.inventory.
    """

    def __init__(self, manager: "WebUIManager"):
        self._manager = manager

    def clear(self):
        self._manager.inventory_panel.clear()

    async def add_campaign(self, campaign) -> None:
        self._manager.inventory_panel.add_campaign(campaign)
        if self._is_unlinked_mining_candidate(campaign):
            self._manager.notification_service.queue(
                NotificationEvent.campaign_not_linked(campaign)
            )

    def _is_unlinked_mining_candidate(self, campaign) -> bool:
        settings = self._manager._twitch.settings
        game_name = campaign.game.name
        if (
            not campaign.active
            or campaign.linked
            or campaign.eligible
            or campaign.finished
            or game_name in settings.exclude
            or (
                settings.priority_mode is PriorityMode.PRIORITY_ONLY
                and game_name not in settings.priority
            )
            or (
                campaign.has_badge_or_emote
                and not settings.enable_badges_emotes
            )
        ):
            return False

        next_hour = datetime.now(timezone.utc) + timedelta(hours=1)
        return any(drop._can_earn_within(next_hour) for drop in campaign.drops)

    def update_drop(self, drop) -> None:
        self._manager.inventory_panel.update_drop(drop)

    def configure_theme(self, *, bg: str):
        pass
