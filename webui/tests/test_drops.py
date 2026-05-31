"""Integration tests for the drop/campaign progress display."""

from __future__ import annotations

import pytest
from nicegui import app
from nicegui.testing import User

from webui.tests.mocks import make_mock_drop, make_mock_campaign


def _manager():
    return app.webui_manager


def _section():
    return _manager().main_panel._drop_section


@pytest.fixture()
def user(user: User) -> User:
    return user


async def test_drop_display_shows_campaign_game(user: User):
    await user.open("/")
    drop = make_mock_drop(campaign=make_mock_campaign(game_name="Fortnite"))
    _manager().display_drop(drop, countdown=False)
    await user.should_see("Fortnite")


async def test_drop_display_shows_campaign_name(user: User):
    await user.open("/")
    drop = make_mock_drop(campaign=make_mock_campaign(name="Winter Royale"))
    _manager().display_drop(drop, countdown=False)
    await user.should_see("Winter Royale")


async def test_drop_display_shows_rewards(user: User):
    await user.open("/")
    drop = make_mock_drop(rewards_text="Golden Umbrella")
    _manager().display_drop(drop, countdown=False)
    await user.should_see("Golden Umbrella")


async def test_drop_display_shows_progress_percentage(user: User):
    await user.open("/")
    drop = make_mock_drop(progress=0.75)
    _manager().display_drop(drop, countdown=False)
    await user.should_see("75.0%")


async def test_drop_display_shows_campaign_percentage(user: User):
    await user.open("/")
    drop = make_mock_drop(
        campaign=make_mock_campaign(claimed_drops=2, total_drops=5, progress=0.4)
    )
    _manager().display_drop(drop, countdown=False)
    await user.should_see("2/5")


async def test_display_drop_with_none_calls_clear(user: User):
    await user.open("/")
    drop = make_mock_drop(campaign=make_mock_campaign(game_name="Apex"))
    _manager().display_drop(drop, countdown=False)
    await user.should_see("Apex")
    _manager().display_drop(None, countdown=False)
    await user.should_not_see("Apex")
    await user.should_see("...")


async def test_subone_subtracts_one_minute_from_remaining(user: User):
    await user.open("/")
    drop = make_mock_drop(remaining_minutes=30)
    _manager().display_drop(drop, countdown=True, subone=False)
    await user.should_see("0:30:00 remaining")
    _manager().display_drop(drop, countdown=False, subone=True)
    await user.should_see("0:29:00 remaining")


class TestMinuteAlmostDone:
    """Boundary tests for the minute_almost_done() contract used by twitch.py
    to decide when to claim a drop. The formula is:
        not _countdown_active or _progress_seconds <= 10
    """

    async def test_returns_true_when_countdown_stopped(self, user: User):
        await user.open("/")
        drop = make_mock_drop(remaining_minutes=30)
        _manager().display_drop(drop, countdown=True)
        _section()._countdown_active = False
        assert _manager().progress.minute_almost_done() is True

    async def test_returns_false_when_11_seconds_remain(self, user: User):
        await user.open("/")
        drop = make_mock_drop(remaining_minutes=30)
        _manager().display_drop(drop, countdown=True)
        _section()._progress_seconds = 11
        assert _manager().progress.minute_almost_done() is False

    async def test_boundary_returns_true_at_10_seconds(self, user: User):
        await user.open("/")
        drop = make_mock_drop(remaining_minutes=30)
        _manager().display_drop(drop, countdown=True)
        _section()._progress_seconds = 10
        assert _manager().progress.minute_almost_done() is True

    async def test_returns_true_at_0_seconds(self, user: User):
        await user.open("/")
        drop = make_mock_drop(remaining_minutes=30)
        _manager().display_drop(drop, countdown=True)
        _section()._progress_seconds = 0
        assert _manager().progress.minute_almost_done() is True

    async def test_returns_false_at_30_seconds(self, user: User):
        await user.open("/")
        drop = make_mock_drop(remaining_minutes=30)
        _manager().display_drop(drop, countdown=True)
        _section()._progress_seconds = 30
        assert _manager().progress.minute_almost_done() is False
