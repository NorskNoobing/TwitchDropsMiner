"""Integration tests for the WebUI adapter → section data flows.

Each test drives the public adapter API (the same interface twitch.py calls) and
asserts on the resulting Python state in the underlying section objects.  No live
browser or NiceGUI server is needed: sections store their mutable state as plain
instance attributes that are populated/updated independently of any UI rendering.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Domain-object helpers
# ---------------------------------------------------------------------------

def _make_channel(
    iid="ch1",
    name="TestChannel",
    online=True,
    pending_online=False,
    drops_enabled=True,
    viewers=100,
    acl_based=False,
    game=None,
):
    ch = MagicMock()
    ch.iid = iid
    ch.name = name
    ch.online = online
    ch.pending_online = pending_online
    ch.drops_enabled = drops_enabled
    ch.viewers = viewers
    ch.acl_based = acl_based
    ch.game = game
    return ch


def _make_drop(
    remaining_minutes=30,
    progress=0.75,
    campaign_remaining_minutes=60,
    campaign_progress=0.5,
    campaign_name="Test Campaign",
    game_name="TestGame",
    claimed_drops=1,
    total_drops=2,
    rewards="Test Reward",
):
    campaign = MagicMock()
    campaign.remaining_minutes = campaign_remaining_minutes
    campaign.progress = campaign_progress
    campaign.claimed_drops = claimed_drops
    campaign.total_drops = total_drops
    campaign.game = MagicMock()
    campaign.game.name = game_name
    campaign.name = campaign_name

    drop = MagicMock()
    drop.campaign = campaign
    drop.remaining_minutes = remaining_minutes
    drop.progress = progress
    drop.rewards_text.return_value = rewards
    return drop


# ---------------------------------------------------------------------------
# Manager-level state
# ---------------------------------------------------------------------------

class TestManagerState:
    def test_status_update_flows_to_text(self, webui_manager):
        webui_manager.status.update("Mining drops")
        assert webui_manager._status_text == "Mining drops"

    def test_print_appends_timestamped_line_to_console_log(self, webui_manager):
        section = webui_manager.main_panel._console_section
        webui_manager.print("hello_unique_xZq")
        assert "hello_unique_xZq" in section._console_log[-1]

    def test_print_multiline_adds_one_entry_per_line(self, webui_manager):
        section = webui_manager.main_panel._console_section
        webui_manager.print("multi_a_xZq\nmulti_b_xZq\nmulti_c_xZq")
        tail = section._console_log[-3:]
        assert any("multi_a_xZq" in line for line in tail)
        assert any("multi_b_xZq" in line for line in tail)
        assert any("multi_c_xZq" in line for line in tail)

    def test_close_sets_close_requested(self, webui_manager):
        assert not webui_manager.close_requested
        webui_manager.close()
        assert webui_manager.close_requested

    def test_restart_arms_reload_requested(self, webui_manager):
        assert not webui_manager._reload_requested.is_set()
        webui_manager.restart()
        assert webui_manager._reload_requested.is_set()


# ---------------------------------------------------------------------------
# Channel adapter → ChannelsSection state
# ---------------------------------------------------------------------------

class TestChannelAdapterFlow:
    def test_display_add_inserts_channel_into_map(self, webui_manager):
        ch = _make_channel(iid="ch1")
        webui_manager.channels.display(ch, add=True)
        assert "ch1" in webui_manager.main_panel._channels_section._channel_map

    def test_display_update_ignored_when_channel_not_yet_in_map(self, webui_manager):
        ch = _make_channel(iid="ch2")
        webui_manager.channels.display(ch, add=False)
        assert "ch2" not in webui_manager.main_panel._channels_section._channel_map

    def test_display_update_replaces_existing_entry(self, webui_manager):
        webui_manager.channels.display(_make_channel(iid="ch3", name="OldName"), add=True)
        webui_manager.channels.display(_make_channel(iid="ch3", name="NewName"), add=False)
        assert webui_manager.main_panel._channels_section._channel_map["ch3"].name == "NewName"

    def test_remove_drops_channel_from_map(self, webui_manager):
        ch = _make_channel(iid="ch4")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.remove(ch)
        assert "ch4" not in webui_manager.main_panel._channels_section._channel_map

    def test_clear_empties_channel_map(self, webui_manager):
        for i in range(3):
            webui_manager.channels.display(_make_channel(iid=f"clr{i}"), add=True)
        webui_manager.channels.clear()
        assert len(webui_manager.main_panel._channels_section._channel_map) == 0

    def test_set_watching_prefixes_row_name_with_arrow(self, webui_manager):
        ch = _make_channel(iid="w1", name="WatchMe")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        section = webui_manager.main_panel._channels_section
        assert any(r["channel"].startswith("▶") for r in section._channel_rows)

    def test_clear_watching_removes_arrow_prefix(self, webui_manager):
        ch = _make_channel(iid="w2", name="WatchMe")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        webui_manager.channels.clear_watching()
        section = webui_manager.main_panel._channels_section
        assert section._watching_channel_iid is None
        assert not any(r["channel"].startswith("▶") for r in section._channel_rows)

    def test_remove_clears_watching_state_for_that_channel(self, webui_manager):
        ch = _make_channel(iid="w3")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        webui_manager.channels.remove(ch)
        assert webui_manager.main_panel._channels_section._watching_channel_iid is None

    def test_get_selection_returns_channel_when_selected(self, webui_manager):
        ch = _make_channel(iid="s1")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s1"
        assert webui_manager.channels.get_selection() is ch

    def test_clear_selection_makes_get_selection_return_none(self, webui_manager):
        ch = _make_channel(iid="s2")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s2"
        webui_manager.channels.clear_selection()
        assert webui_manager.channels.get_selection() is None

    def test_remove_clears_selection_for_that_channel(self, webui_manager):
        ch = _make_channel(iid="s3")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s3"
        webui_manager.channels.remove(ch)
        assert webui_manager.main_panel._channels_section._selected_channel_iid is None

    def test_channel_row_reflects_online_status(self, webui_manager):
        from translate import _
        ch = _make_channel(iid="r1", online=True, pending_online=False)
        webui_manager.channels.display(ch, add=True)
        row = next(r for r in webui_manager.main_panel._channels_section._channel_rows if r["iid"] == "r1")
        assert row["status"] == _("gui", "channels", "online")

    def test_channel_row_reflects_offline_status(self, webui_manager):
        from translate import _
        ch = _make_channel(iid="r2", online=False, pending_online=False)
        webui_manager.channels.display(ch, add=True)
        row = next(r for r in webui_manager.main_panel._channels_section._channel_rows if r["iid"] == "r2")
        assert row["status"] == _("gui", "channels", "offline")


# ---------------------------------------------------------------------------
# Campaign-progress adapter → DropSection state
# ---------------------------------------------------------------------------

class TestDropAdapterFlow:
    def test_display_with_countdown_activates_countdown(self, webui_manager):
        drop = _make_drop()
        webui_manager.progress.display(drop, countdown=True)
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is drop
        assert section._countdown_active is True

    def test_display_without_countdown_stores_60_seconds(self, webui_manager):
        drop = _make_drop()
        webui_manager.progress.display(drop, countdown=False)
        section = webui_manager.main_panel._drop_section
        assert section._countdown_active is False
        assert section._progress_seconds == 60

    def test_display_subone_sets_progress_to_zero(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=False, subone=True)
        assert webui_manager.main_panel._drop_section._progress_seconds == 0

    def test_display_none_clears_drop(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.progress.display(None)
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is None
        assert section._countdown_active is False

    def test_display_populates_campaign_and_drop_text(self, webui_manager):
        drop = _make_drop(game_name="MyGame", campaign_name="MyCampaign", rewards="Gold")
        webui_manager.progress.display(drop, countdown=False)
        section = webui_manager.main_panel._drop_section
        assert section._campaign_game_text == "MyGame"
        assert section._campaign_name_text == "MyCampaign"
        assert section._drop_rewards_text == "Gold"

    def test_clear_drop_resets_display_text_and_progress(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.clear_drop()
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is None
        assert section._campaign_game_text == "..."
        assert section._drop_rewards_text == "..."
        assert section._campaign_progress_value == 0.0
        assert section._drop_progress_value == 0.0

    def test_stop_timer_deactivates_countdown(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.progress.stop_timer()
        assert webui_manager.main_panel._drop_section._countdown_active is False

    def test_minute_almost_done_false_while_countdown_active_with_time_remaining(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 59
        assert webui_manager.progress.minute_almost_done() is False

    def test_minute_almost_done_true_after_stop_timer(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 59
        webui_manager.progress.stop_timer()
        assert webui_manager.progress.minute_almost_done() is True

    def test_minute_almost_done_true_at_ten_second_boundary(self, webui_manager):
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 10
        assert webui_manager.progress.minute_almost_done() is True


# ---------------------------------------------------------------------------
# WebSocket adapter → WebsocketSection state
# ---------------------------------------------------------------------------

class TestWebsocketAdapterFlow:
    @pytest.fixture(autouse=True)
    def _stub_refresh(self, nicegui_loop):
        pass  # activates nicegui_loop for every test in this class

    def test_update_creates_entry_for_new_index(self, webui_manager):
        webui_manager.websockets.update(0, status="connected", topics=5)
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["status"] == "connected"
        assert entry["topics"] == 5

    def test_update_status_only_leaves_topics_unchanged(self, webui_manager):
        webui_manager.websockets.update(0, status="connected", topics=5)
        webui_manager.websockets.update(0, status="disconnected")
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["topics"] == 5
        assert entry["status"] == "disconnected"

    def test_update_topics_only_leaves_status_unchanged(self, webui_manager):
        webui_manager.websockets.update(0, status="connected", topics=5)
        webui_manager.websockets.update(0, topics=8)
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["status"] == "connected"
        assert entry["topics"] == 8

    def test_update_with_no_params_raises_type_error(self, webui_manager):
        with pytest.raises(TypeError):
            webui_manager.websockets.update(0)

    def test_remove_drops_entry(self, webui_manager):
        webui_manager.websockets.update(0, status="connected", topics=3)
        webui_manager.websockets.remove(0)
        assert 0 not in webui_manager.main_panel._ws_section._ws_data

    def test_multiple_slots_tracked_independently(self, webui_manager):
        webui_manager.websockets.update(0, status="connected", topics=1)
        webui_manager.websockets.update(1, status="disconnected", topics=0)
        section = webui_manager.main_panel._ws_section
        assert section._ws_data[0]["status"] == "connected"
        assert section._ws_data[1]["status"] == "disconnected"
        webui_manager.websockets.remove(0)
        assert 0 not in section._ws_data
        assert 1 in section._ws_data


# ---------------------------------------------------------------------------
# Login adapter → LoginSection state
# ---------------------------------------------------------------------------

class TestLoginAdapterFlow:
    def test_update_stores_user_id_as_string(self, webui_manager):
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 12345)
        assert webui_manager.main_panel._login_section._user_str == "12345"

    def test_update_none_user_id_shows_dash(self, webui_manager):
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_out"), None)
        assert webui_manager.main_panel._login_section._user_str == "-"

    def test_update_maps_localized_status_to_internal_key(self, webui_manager):
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 1)
        assert webui_manager.main_panel._login_section._login_state == "logged_in"

    def test_login_required_mirrors_to_status_bar(self, webui_manager):
        from translate import _
        status = _("gui", "login", "required")
        webui_manager.login.update(status, None)
        assert webui_manager._status_text == status

    def test_logged_in_does_not_mirror_to_status_bar(self, webui_manager):
        from translate import _
        webui_manager.status.update("Mining")
        webui_manager.login.update(_("gui", "login", "logged_in"), 1)
        assert webui_manager._status_text == "Mining"


# ---------------------------------------------------------------------------
# coro_unless_closed — async interrupt races
# ---------------------------------------------------------------------------

class TestCoroUnlessClosed:
    def test_normal_coroutine_returns_its_result(self, webui_manager):
        async def _run():
            async def produce():
                return 42
            return await webui_manager.coro_unless_closed(produce())

        assert asyncio.run(_run()) == 42

    def test_close_event_pre_set_raises_exit_request(self, webui_manager):
        from exceptions import ExitRequest

        async def _run():
            webui_manager._close_requested.set()
            await webui_manager.coro_unless_closed(asyncio.sleep(9999))

        with pytest.raises(ExitRequest):
            asyncio.run(_run())

    def test_reload_event_pre_set_raises_reload_request(self, webui_manager):
        from exceptions import ReloadRequest

        async def _run():
            webui_manager._reload_requested.set()
            await webui_manager.coro_unless_closed(asyncio.sleep(9999))

        with pytest.raises(ReloadRequest):
            asyncio.run(_run())

    def test_reload_clears_the_event_after_raising(self, webui_manager):
        from exceptions import ReloadRequest

        async def _run():
            webui_manager._reload_requested.set()
            try:
                await webui_manager.coro_unless_closed(asyncio.sleep(9999))
            except ReloadRequest:
                pass
            return webui_manager._reload_requested.is_set()

        assert asyncio.run(_run()) is False

    def test_close_signalled_mid_coro_interrupts_it(self, webui_manager):
        from exceptions import ExitRequest

        async def _run():
            async def set_close_then_hang():
                webui_manager._close_requested.set()
                await asyncio.sleep(9999)

            await webui_manager.coro_unless_closed(set_close_then_hang())

        with pytest.raises(ExitRequest):
            asyncio.run(_run())
