from __future__ import annotations

import asyncio
import json
import os
import stat
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from constants import PriorityMode
from webui.adapters.inventory_overview import InventoryOverviewAdapter
from webui.notifications.config import (
    CONFIG_VERSION,
    DEFAULT_DISCORD_COLOR,
    NotificationConfig,
    NotificationDestination,
)
from webui.notifications.discord import TDM_AVATAR_URL, build_discord_payload
from webui.notifications.models import (
    BenefitInfo,
    NotificationEvent,
    NotificationEventType,
)
from webui.notifications.service import NotificationService


def _claimed_event() -> NotificationEvent:
    return NotificationEvent(
        event_type=NotificationEventType.DROP_CLAIMED,
        title="Claimed drop: THE FINALS (5/5)",
        message="Greenroom Glitch 93R, Bonus Charm",
        deduplication_key="drop_claimed:drop-1",
        created_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        game_name="THE FINALS",
        campaign_name="Seasonal Drops Campaign",
        claimed_drops=5,
        total_drops=5,
        game_image_url="https://example.test/game.jpg",
        benefits=(
            BenefitInfo("Greenroom Glitch 93R", "https://example.test/drop-1.jpg"),
            BenefitInfo("Bonus Charm", "https://example.test/drop-2.jpg"),
        ),
    )


def test_claim_event_uses_claimed_campaign_progress():
    campaign = SimpleNamespace(
        id="campaign-1",
        game=SimpleNamespace(name="THE FINALS"),
        name="Seasonal Drops Campaign",
        claimed_drops=5,
        total_drops=5,
        image_url="https://example.test/game.jpg",
    )
    drop = SimpleNamespace(
        id="drop-1",
        name="Drop 1",
        campaign=campaign,
        benefits=[
            SimpleNamespace(
                name="Greenroom Glitch 93R",
                image_url="https://example.test/drop.jpg",
            )
        ],
        rewards_text=lambda: "Greenroom Glitch 93R",
    )

    event = NotificationEvent.from_claimed_drop(drop)

    assert event.title == "Claimed drop: THE FINALS (5/5)"
    assert event.claimed_drops == 5
    assert event.total_drops == 5


def test_discord_payload_has_one_embed_per_benefit():
    destination = NotificationDestination(
        name="Discord", provider="discord", url="https://discord.com/api/webhooks/1/token"
    )

    payload = build_discord_payload(_claimed_event(), destination)

    assert len(payload["embeds"]) == 2
    assert {embed["description"] for embed in payload["embeds"]} == {
        "Greenroom Glitch 93R",
        "Bonus Charm",
    }
    assert all(embed["title"].endswith("(5/5)") for embed in payload["embeds"])
    assert all(embed["thumbnail"]["url"].endswith("game.jpg") for embed in payload["embeds"])
    assert payload["embeds"][0]["image"]["url"].endswith("drop-1.jpg")
    assert payload["username"] == "Twitch Drops Miner"
    assert payload["avatar_url"] == TDM_AVATAR_URL
    assert all(embed["color"] == DEFAULT_DISCORD_COLOR for embed in payload["embeds"])


@pytest.mark.parametrize(
    "url",
    [
        "http://discord.com/api/webhooks/1/token",
        "https://example.test/api/webhooks/1/token",
        "https://discord.com/channels/1/2",
    ],
)
def test_discord_destination_rejects_non_webhook_urls(url):
    destination = NotificationDestination(name="Discord", provider="discord", url=url)

    with pytest.raises(ValueError, match="Discord webhook"):
        destination.validate()


def test_default_events_include_unlinked_but_not_campaign_completed():
    events = set(NotificationDestination().events)

    assert NotificationEventType.CAMPAIGN_NOT_LINKED.value in events
    assert NotificationEventType.CAMPAIGN_COMPLETED.value not in events


def test_notification_config_round_trip_and_restrictive_mode(tmp_path):
    path = tmp_path / "notifications.json"
    config = NotificationConfig(path)
    config.add(
        NotificationDestination(
            name="Discord",
            provider="discord",
            url="https://discord.com/api/webhooks/1/token",
        )
    )

    loaded = NotificationConfig(path)

    assert loaded.destinations[0].name == "Discord"
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == CONFIG_VERSION
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_notification_config_migrates_the_previous_discord_default(tmp_path):
    path = tmp_path / "notifications.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "destinations": [
                    {
                        "name": "Discord",
                        "provider": "discord",
                        "url": "https://discord.com/api/webhooks/1/token",
                        "color": 0x7D46FF,
                        "events": [
                            "drop_claimed",
                            "campaign_completed",
                            "login_required",
                            "miner_error",
                        ],
                    },
                    {
                        "name": "Custom Discord",
                        "provider": "discord",
                        "url": "https://discord.com/api/webhooks/2/token",
                        "color": 0x123456,
                        "events": ["drop_claimed", "campaign_completed"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    config = NotificationConfig(path)

    assert config.destinations[0].color == DEFAULT_DISCORD_COLOR
    assert config.destinations[1].color == 0x123456
    assert set(config.destinations[0].events) == {
        "drop_claimed",
        "campaign_not_linked",
        "login_required",
        "miner_error",
    }
    assert set(config.destinations[1].events) == {
        "drop_claimed",
        "campaign_completed",
    }
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == CONFIG_VERSION


def _unlinked_campaign(
    *,
    game_name="THE FINALS",
    active=True,
    linked=False,
    eligible=False,
    finished=False,
    has_badge_or_emote=False,
    earnable=True,
):
    return SimpleNamespace(
        id="campaign-1",
        name="Seasonal Drops Campaign",
        game=SimpleNamespace(name=game_name),
        active=active,
        linked=linked,
        eligible=eligible,
        finished=finished,
        has_badge_or_emote=has_badge_or_emote,
        claimed_drops=1,
        total_drops=5,
        image_url="https://example.test/game.jpg",
        link_url="https://example.test/link-account",
        drops=[SimpleNamespace(_can_earn_within=lambda _: earnable)],
    )


def _unlinked_manager(
    queued,
    displayed=None,
    *,
    priority_mode=PriorityMode.PRIORITY_ONLY,
    priority=None,
    exclude=None,
    enable_badges_emotes=False,
):
    settings = SimpleNamespace(
        priority_mode=priority_mode,
        priority=["THE FINALS"] if priority is None else priority,
        exclude=set() if exclude is None else exclude,
        enable_badges_emotes=enable_badges_emotes,
    )
    return SimpleNamespace(
        _twitch=SimpleNamespace(settings=settings),
        inventory_panel=SimpleNamespace(
            add_campaign=(displayed.append if displayed is not None else lambda _: None)
        ),
        notification_service=SimpleNamespace(queue=queued.append),
    )


def test_selected_active_unlinked_campaign_queues_a_notification():
    queued = []
    displayed = []
    manager = _unlinked_manager(queued, displayed)
    campaign = _unlinked_campaign()

    asyncio.run(InventoryOverviewAdapter(manager).add_campaign(campaign))

    assert displayed == [campaign]
    assert len(queued) == 1
    event = queued[0]
    assert event.event_type is NotificationEventType.CAMPAIGN_NOT_LINKED
    assert event.title == "Campaign not linked: THE FINALS"
    assert event.message == "Seasonal Drops Campaign"
    assert event.link_url.endswith("link-account")
    assert event.deduplication_key == "campaign_not_linked_game:the finals"

    payload = build_discord_payload(event, NotificationDestination())
    assert payload["embeds"][0]["url"].endswith("link-account")
    assert payload["embeds"][0]["thumbnail"]["url"].endswith("game.jpg")


@pytest.mark.parametrize(
    "campaign_kwargs,manager_kwargs",
    [
        ({"active": False}, {}),
        ({"linked": True, "eligible": True}, {}),
        ({"eligible": True}, {}),
        ({"finished": True}, {}),
        ({"earnable": False}, {}),
        ({"game_name": "Off-list Game"}, {}),
        ({}, {"exclude": {"THE FINALS"}}),
        ({"has_badge_or_emote": True}, {}),
    ],
)
def test_campaign_without_unlinked_mining_blocker_does_not_queue(
    campaign_kwargs, manager_kwargs
):
    queued = []
    manager = _unlinked_manager(queued, **manager_kwargs)
    campaign = _unlinked_campaign(**campaign_kwargs)

    asyncio.run(InventoryOverviewAdapter(manager).add_campaign(campaign))

    assert queued == []


def test_non_priority_mode_can_notify_for_a_non_priority_game():
    queued = []
    manager = _unlinked_manager(
        queued,
        priority_mode=PriorityMode.ENDING_SOONEST,
        priority=[],
    )

    asyncio.run(
        InventoryOverviewAdapter(manager).add_campaign(
            _unlinked_campaign(game_name="Off-list Game")
        )
    )

    assert len(queued) == 1


def test_unlinked_campaigns_for_the_same_game_share_a_deduplication_key():
    first = _unlinked_campaign()
    second = _unlinked_campaign()
    second.id = "campaign-2"
    second.name = "Another Campaign"

    first_event = NotificationEvent.campaign_not_linked(first)
    second_event = NotificationEvent.campaign_not_linked(second)

    assert first_event.deduplication_key == second_event.deduplication_key


def test_test_delivery_uses_artwork_from_the_loaded_inventory(tmp_path, monkeypatch):
    async def run_test() -> None:
        config = NotificationConfig(tmp_path / "notifications.json")
        destination = NotificationDestination(
            name="Discord",
            provider="discord",
            url="https://discord.com/api/webhooks/1/token",
        )
        config.add(destination)
        campaign = SimpleNamespace(
            id="campaign-1",
            game=SimpleNamespace(name="THE FINALS"),
            name="Seasonal Drops Campaign",
            claimed_drops=4,
            total_drops=5,
            image_url="https://example.test/real-game-cover.jpg",
        )
        drop = SimpleNamespace(
            id="drop-1",
            name="Drop 1",
            campaign=campaign,
            benefits=[
                SimpleNamespace(
                    name="Greenroom Glitch 93R",
                    image_url="https://example.test/real-benefit.jpg",
                )
            ],
            rewards_text=lambda: "Greenroom Glitch 93R",
        )
        campaign.drops = [drop]
        delivered = []
        service = NotificationService(config)

        async def capture(event, selected_destination):
            delivered.append((event, selected_destination))

        monkeypatch.setattr(service, "_send_test", capture)

        assert service.send_test(destination.id, [campaign]) is True
        await asyncio.gather(*service._tasks)

        event, selected_destination = delivered[0]
        assert selected_destination is destination
        assert event.game_image_url.endswith("real-game-cover.jpg")
        assert event.benefits[0].image_url.endswith("real-benefit.jpg")

    asyncio.run(run_test())


def test_invalid_notification_config_does_not_prevent_startup(tmp_path):
    path = tmp_path / "notifications.json"
    path.write_text("{not-json", encoding="utf-8")

    config = NotificationConfig(path)

    assert config.destinations == []
    assert "Unable to load notification settings" in config.load_error


def test_email_destination_builds_apprise_url_without_logging_helpers():
    destination = NotificationDestination(
        name="Email",
        provider="email",
        smtp_host="smtp.example.test",
        smtp_port=587,
        smtp_username="miner@example.test",
        smtp_password="secret",
        smtp_from="miner@example.test",
        smtp_recipients="owner@example.test",
    )

    url = destination.apprise_url()

    assert url.startswith("mailtos://smtp.example.test:587?")
    assert "owner%40example.test" in url
    assert "secret" in url
