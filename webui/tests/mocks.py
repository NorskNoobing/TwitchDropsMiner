"""Mock factories for WebUI tests.

These are in a separate module so test files can import them without
triggering app.py's ``ui.run()`` call.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from yarl import URL

from constants import PriorityMode


class MockSettings:
    dark_mode = False
    tray_notifications = False
    stdlog = False
    language = "English"
    proxy = None
    priority = []
    exclude = set()
    priority_mode = PriorityMode.PRIORITY_ONLY
    autostart_tray = False
    connection_quality = 1
    enable_badges_emotes = False
    available_drops_check = False

    def save(self, *, force=False):
        pass


def make_mock_twitch():
    twitch = MagicMock()
    settings = MockSettings()
    twitch.settings = settings
    twitch.state_change = MagicMock(return_value=MagicMock())
    twitch._session = None
    twitch.close = MagicMock()
    twitch.websocket = MagicMock()
    twitch.websocket.websockets = []
    twitch.inventory = []
    return twitch


def make_mock_channel(name="test_channel", game="TestGame", iid="ch1", **overrides):
    channel = MagicMock()
    channel.name = name
    channel.iid = iid
    channel.game = game
    channel.online = overrides.pop("online", True)
    channel.pending_online = overrides.pop("pending_online", False)
    channel.drops_enabled = overrides.pop("drops_enabled", True)
    channel.viewers = overrides.pop("viewers", 100)
    channel.acl_based = overrides.pop("acl_based", False)
    for k, v in overrides.items():
        setattr(channel, k, v)
    return channel


def make_mock_drop(
    drop_id="drop1",
    progress=0.5,
    remaining_minutes=30,
    rewards_text="Test Reward",
    campaign=None,
    **overrides,
):
    drop = MagicMock()
    drop.id = drop_id
    drop.progress = progress
    drop.remaining_minutes = remaining_minutes
    drop.rewards_text = MagicMock(return_value=rewards_text)
    drop.is_claimed = overrides.pop("is_claimed", False)
    drop.can_claim = overrides.pop("can_claim", False)
    drop.current_minutes = overrides.pop("current_minutes", int(progress * 60))
    drop.required_minutes = overrides.pop("required_minutes", 60)
    drop.starts_at = overrides.pop("starts_at", None)
    drop.ends_at = overrides.pop("ends_at", None)
    drop.benefits = overrides.pop("benefits", [])

    if campaign is None:
        campaign = make_mock_campaign()
    drop.campaign = campaign
    for k, v in overrides.items():
        setattr(drop, k, v)
    return drop


def make_mock_campaign(
    name="Test Campaign",
    game_name="TestGame",
    claimed_drops=1,
    total_drops=3,
    remaining_minutes=90,
    progress=0.33,
    **overrides,
):
    campaign = MagicMock()
    campaign.name = name
    campaign.game = MagicMock()
    campaign.game.name = game_name
    campaign.claimed_drops = claimed_drops
    campaign.total_drops = total_drops
    campaign.remaining_minutes = remaining_minutes
    campaign.progress = progress
    campaign.eligible = overrides.pop("eligible", True)
    campaign.active = overrides.pop("active", True)
    campaign.upcoming = overrides.pop("upcoming", False)
    campaign.expired = overrides.pop("expired", False)
    campaign.finished = overrides.pop("finished", False)
    campaign.required_minutes = overrides.pop("required_minutes", 120)
    campaign.starts_at = overrides.pop("starts_at", None)
    campaign.ends_at = overrides.pop("ends_at", None)
    campaign.image_url = overrides.pop("image_url", URL("https://example.com/img.png"))
    campaign.link_url = overrides.pop("link_url", URL("https://twitch.tv/link"))
    campaign.allowed_channels = overrides.pop("allowed_channels", [])
    campaign.drops = overrides.pop("drops", [])
    for k, v in overrides.items():
        setattr(campaign, k, v)
    return campaign
