from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class NotificationEventType(str, Enum):
    DROP_CLAIMED = "drop_claimed"
    CAMPAIGN_COMPLETED = "campaign_completed"
    CAMPAIGN_NOT_LINKED = "campaign_not_linked"
    MINING_STARTED = "mining_started"
    MINING_SWITCHED = "mining_switched"
    NO_CAMPAIGNS = "no_campaigns"
    LOGIN_REQUIRED = "login_required"
    MINER_ERROR = "miner_error"
    APP_STARTED = "app_started"
    UPDATE_AVAILABLE = "update_available"


DEFAULT_EVENT_TYPES = {
    NotificationEventType.DROP_CLAIMED,
    NotificationEventType.CAMPAIGN_NOT_LINKED,
    NotificationEventType.LOGIN_REQUIRED,
    NotificationEventType.MINER_ERROR,
}


@dataclass(frozen=True)
class BenefitInfo:
    name: str
    image_url: str = ""


@dataclass(frozen=True)
class NotificationEvent:
    event_type: NotificationEventType
    title: str
    message: str
    deduplication_key: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    game_name: str = ""
    campaign_name: str = ""
    claimed_drops: int = 0
    total_drops: int = 0
    game_image_url: str = ""
    benefits: tuple[BenefitInfo, ...] = ()
    link_url: str = "https://www.twitch.tv/drops/inventory"

    @classmethod
    def from_claimed_drop(cls, drop) -> "NotificationEvent":
        campaign = drop.campaign
        benefits = tuple(
            BenefitInfo(name=benefit.name, image_url=str(benefit.image_url or ""))
            for benefit in drop.benefits
        ) or (BenefitInfo(name=drop.name),)
        return cls(
            event_type=NotificationEventType.DROP_CLAIMED,
            title=(
                f"Claimed drop: {campaign.game.name} "
                f"({campaign.claimed_drops}/{campaign.total_drops})"
            ),
            message=drop.rewards_text() or drop.name,
            deduplication_key=f"drop_claimed:{drop.id}",
            game_name=campaign.game.name,
            campaign_name=campaign.name,
            claimed_drops=campaign.claimed_drops,
            total_drops=campaign.total_drops,
            game_image_url=str(campaign.image_url or ""),
            benefits=benefits,
        )

    @classmethod
    def campaign_completed(cls, drop) -> "NotificationEvent":
        campaign = drop.campaign
        return cls(
            event_type=NotificationEventType.CAMPAIGN_COMPLETED,
            title=f"Campaign completed: {campaign.game.name}",
            message=f"{campaign.name} ({campaign.claimed_drops}/{campaign.total_drops})",
            deduplication_key=f"campaign_completed:{campaign.id}",
            game_name=campaign.game.name,
            campaign_name=campaign.name,
            claimed_drops=campaign.claimed_drops,
            total_drops=campaign.total_drops,
            game_image_url=str(campaign.image_url or ""),
        )

    @classmethod
    def campaign_not_linked(cls, campaign) -> "NotificationEvent":
        return cls(
            event_type=NotificationEventType.CAMPAIGN_NOT_LINKED,
            title=f"Campaign not linked: {campaign.game.name}",
            message=campaign.name,
            deduplication_key=(
                f"campaign_not_linked_game:{campaign.game.name.casefold()}"
            ),
            game_name=campaign.game.name,
            campaign_name=campaign.name,
            claimed_drops=campaign.claimed_drops,
            total_drops=campaign.total_drops,
            game_image_url=str(campaign.image_url or ""),
            link_url=(
                str(campaign.link_url)
                if campaign.link_url
                else "https://www.twitch.tv/drops/inventory"
            ),
        )

    @classmethod
    def simple(
        cls,
        event_type: NotificationEventType,
        title: str,
        message: str,
        key: str,
    ) -> "NotificationEvent":
        return cls(event_type, title, message, f"{event_type.value}:{key}")


@dataclass(frozen=True)
class DeliveryAttempt:
    created_at: datetime
    event_type: NotificationEventType
    destination_name: str
    success: bool
    detail: str
