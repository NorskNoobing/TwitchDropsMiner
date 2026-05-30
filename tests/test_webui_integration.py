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
# Console output
# ---------------------------------------------------------------------------

class TestConsoleOutput:
    def test_print_appends_timestamped_line(self, webui_manager):
        # manager.print() must prepend a HH:MM:SS: stamp — not just store the
        # raw string — so the console log has readable timestamps per line.
        section = webui_manager.main_panel._console_section
        webui_manager.print("hello_unique_xZq")
        last = section._console_log[-1]
        assert "hello_unique_xZq" in last
        # Verify the timestamp prefix is present (format: HH:MM:SS:)
        assert last.index(":") < last.index("hello_unique_xZq")

    def test_print_multiline_splits_into_one_entry_per_line(self, webui_manager):
        # twitch.py sometimes passes multi-line strings; each logical line must
        # become a separate log entry so every line gets its own timestamp.
        section = webui_manager.main_panel._console_section
        webui_manager.print("part_a_xZq\npart_b_xZq\npart_c_xZq")
        tail = section._console_log[-3:]
        assert any("part_a_xZq" in line for line in tail)
        assert any("part_b_xZq" in line for line in tail)
        assert any("part_c_xZq" in line for line in tail)


# ---------------------------------------------------------------------------
# Channel adapter → ChannelsSection
# ---------------------------------------------------------------------------

class TestChannelAdapterFlow:
    def test_display_update_ignored_when_channel_not_in_map(self, webui_manager):
        # add=False is an in-place refresh for a known channel; if the channel
        # was never added with add=True first, a phantom row must not appear.
        ch = _make_channel(iid="ch1")
        webui_manager.channels.display(ch, add=False)
        assert "ch1" not in webui_manager.main_panel._channels_section._channel_map

    def test_set_watching_prefixes_row_name_with_arrow(self, webui_manager):
        # _build_rows() prepends "▶ " to the channel name for the watched channel;
        # the prefix must appear in the rendered rows after set_watching().
        ch = _make_channel(iid="w1", name="WatchMe")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        rows = webui_manager.main_panel._channels_section._channel_rows
        assert any(r["channel"].startswith("▶") for r in rows)

    def test_clear_watching_removes_arrow_prefix(self, webui_manager):
        # Both the iid marker and the "▶ " row prefix must be cleared together;
        # clearing only the iid would leave a stale arrow in the table.
        ch = _make_channel(iid="w2", name="WatchMe")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        webui_manager.channels.clear_watching()
        section = webui_manager.main_panel._channels_section
        assert section._watching_channel_iid is None
        assert not any(r["channel"].startswith("▶") for r in section._channel_rows)

    def test_remove_clears_watching_state_for_that_channel(self, webui_manager):
        # Removing the currently-watched channel must also clear the watching iid;
        # otherwise the stale iid points to a row that no longer exists.
        ch = _make_channel(iid="w3")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        webui_manager.channels.remove(ch)
        assert webui_manager.main_panel._channels_section._watching_channel_iid is None

    def test_get_selection_returns_channel_object_not_iid(self, webui_manager):
        # twitch.py reads get_selection() during CHANNEL_SWITCH to find which channel
        # to switch to; it must return the Channel object, not just the string iid.
        ch = _make_channel(iid="s1")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s1"
        assert webui_manager.channels.get_selection() is ch

    def test_remove_clears_selection_to_prevent_dead_reference(self, webui_manager):
        # If the selected channel is removed (e.g. goes offline), get_selection()
        # must return None rather than a Channel object no longer in the map.
        ch = _make_channel(iid="s2")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s2"
        webui_manager.channels.remove(ch)
        assert webui_manager.channels.get_selection() is None

    def test_channel_row_status_text_matches_online_flag(self, webui_manager):
        # _build_rows() maps channel.online/pending_online to a localised string;
        # the correct branch must fire so the table cell says "online" or "offline".
        from translate import _
        online_ch = _make_channel(iid="r1", online=True, pending_online=False)
        offline_ch = _make_channel(iid="r2", online=False, pending_online=False)
        webui_manager.channels.display(online_ch, add=True)
        webui_manager.channels.display(offline_ch, add=True)
        rows = {r["iid"]: r for r in webui_manager.main_panel._channels_section._channel_rows}
        assert rows["r1"]["status"] == _("gui", "channels", "online")
        assert rows["r2"]["status"] == _("gui", "channels", "offline")


# ---------------------------------------------------------------------------
# Drop / campaign-progress adapter → DropSection
# ---------------------------------------------------------------------------

class TestDropAdapterFlow:
    def test_display_subone_starts_progress_at_zero(self, webui_manager):
        # subone=True means the drop needs < 1 min; starting at 0 causes
        # minute_almost_done() to return True immediately so the heartbeat fires
        # without waiting a full countdown — unlike countdown=False which sets 60.
        webui_manager.progress.display(_make_drop(), countdown=False, subone=True)
        assert webui_manager.main_panel._drop_section._progress_seconds == 0

    def test_display_none_clears_current_drop(self, webui_manager):
        # twitch.py passes None when there is no active drop; the section must
        # clear state rather than leaving the last campaign's data on screen.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.progress.display(None)
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is None
        assert section._countdown_active is False

    def test_display_extracts_text_from_nested_drop_objects(self, webui_manager):
        # game name, campaign name, and reward text come from nested attributes
        # on Drop and Campaign; the section must read the right fields.
        drop = _make_drop(game_name="MyGame", campaign_name="MyCampaign", rewards="Gold")
        webui_manager.progress.display(drop, countdown=False)
        section = webui_manager.main_panel._drop_section
        assert section._campaign_game_text == "MyGame"
        assert section._campaign_name_text == "MyCampaign"
        assert section._drop_rewards_text == "Gold"

    def test_clear_drop_resets_to_placeholder_values(self, webui_manager):
        # After clear_drop(), the display must show "..." and 0.0, not the last
        # drop's values — otherwise stale campaign info lingers on screen.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.clear_drop()
        section = webui_manager.main_panel._drop_section
        assert section._campaign_game_text == "..."
        assert section._drop_rewards_text == "..."
        assert section._campaign_progress_value == 0.0
        assert section._drop_progress_value == 0.0

    def test_minute_almost_done_false_while_countdown_running(self, webui_manager):
        # twitch.py polls minute_almost_done() to know when to send a heartbeat;
        # returning False prematurely would cause it to fire too early.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 59
        assert webui_manager.progress.minute_almost_done() is False

    def test_minute_almost_done_true_when_countdown_stopped(self, webui_manager):
        # When stop_timer() is called (no eligible stream), minute_almost_done()
        # must flip to True so the heartbeat fires and progress is committed.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 59
        webui_manager.progress.stop_timer()
        assert webui_manager.progress.minute_almost_done() is True

    def test_minute_almost_done_true_at_ten_second_boundary(self, webui_manager):
        # The threshold is <= 10 s (not < 10); at exactly 10 seconds the window
        # opens so the heartbeat reaches Twitch before the minute rolls over.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 10
        assert webui_manager.progress.minute_almost_done() is True


# ---------------------------------------------------------------------------
# WebSocket adapter → WebsocketSection
# ---------------------------------------------------------------------------

class TestWebsocketAdapterFlow:
    @pytest.fixture(autouse=True)
    def _stub_refresh(self, nicegui_loop):
        pass  # nicegui_loop stubs background_tasks.create for @ui.refreshable

    def test_status_only_update_preserves_topic_count(self, webui_manager):
        # twitch.py updates status and topic count on separate code paths;
        # a status-only call must not wipe out the topic count already stored.
        webui_manager.websockets.update(0, status="connected", topics=5)
        webui_manager.websockets.update(0, status="disconnected")
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["topics"] == 5
        assert entry["status"] == "disconnected"

    def test_topics_only_update_preserves_status(self, webui_manager):
        # Same independence in the other direction: changing the topic count must
        # not reset a "connected" status back to the disconnected default.
        webui_manager.websockets.update(0, status="connected", topics=5)
        webui_manager.websockets.update(0, topics=8)
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["status"] == "connected"
        assert entry["topics"] == 8

    def test_update_with_no_params_raises_type_error(self, webui_manager):
        # Calling update() without either keyword arg is a programmer error;
        # the adapter must raise TypeError rather than silently storing nothing.
        with pytest.raises(TypeError):
            webui_manager.websockets.update(0)

    def test_multiple_slots_are_tracked_independently(self, webui_manager):
        # The app runs up to MAX_WEBSOCKETS connections; removing one slot must
        # not affect adjacent slots' entries.
        webui_manager.websockets.update(0, status="connected", topics=1)
        webui_manager.websockets.update(1, status="disconnected", topics=0)
        section = webui_manager.main_panel._ws_section
        assert section._ws_data[0]["status"] == "connected"
        assert section._ws_data[1]["status"] == "disconnected"
        webui_manager.websockets.remove(0)
        assert 0 not in section._ws_data
        assert 1 in section._ws_data


# ---------------------------------------------------------------------------
# Login adapter → LoginSection
# ---------------------------------------------------------------------------

class TestLoginAdapterFlow:
    def test_integer_user_id_stored_as_string(self, webui_manager):
        # The Twitch API returns an integer user ID but the label expects a string;
        # the adapter must convert it so the card doesn't show raw repr output.
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 12345)
        assert webui_manager.main_panel._login_section._user_str == "12345"

    def test_none_user_id_shown_as_dash(self, webui_manager):
        # Before login the user ID is None; "–" is the correct placeholder and
        # must not appear as the Python string "None".
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_out"), None)
        assert webui_manager.main_panel._login_section._user_str == "-"

    def test_localized_status_string_mapped_to_internal_key(self, webui_manager):
        # twitch.py passes the full localised string (e.g. "Logged in"); LoginSection
        # must reverse-map it to a stable key ("logged_in") that drives button state.
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 1)
        assert webui_manager.main_panel._login_section._login_state == "logged_in"

    def test_login_required_status_mirrored_to_status_bar(self, webui_manager):
        # When device-code login is needed the main loop hasn't set a status yet;
        # the adapter must push the login prompt to the bar so the user sees it.
        from translate import _
        status = _("gui", "login", "required")
        webui_manager.login.update(status, None)
        assert webui_manager._status_text == status

    def test_logged_in_status_not_mirrored_to_status_bar(self, webui_manager):
        # Once running, twitch.py owns the status bar; "logged_in" must NOT be
        # mirrored or it would overwrite the current mining status on every heartbeat.
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 1)
        assert webui_manager._status_text != _("gui", "login", "logged_in")


# ---------------------------------------------------------------------------
# coro_unless_closed — async interrupt races
# ---------------------------------------------------------------------------

class TestCoroUnlessClosed:
    def test_normal_coroutine_returns_its_result(self, webui_manager):
        # When neither close nor reload is signalled the wrapped coroutine must
        # run to completion and its return value forwarded to the caller.
        async def _run():
            async def produce():
                return 42
            return await webui_manager.coro_unless_closed(produce())

        assert asyncio.run(_run()) == 42

    def test_close_event_raises_exit_request(self, webui_manager):
        # If close was signalled before the coroutine starts (e.g. the user closed
        # the tab), coro_unless_closed must raise ExitRequest immediately.
        from exceptions import ExitRequest

        async def _run():
            webui_manager._close_requested.set()
            await webui_manager.coro_unless_closed(asyncio.sleep(9999))

        with pytest.raises(ExitRequest):
            asyncio.run(_run())

    def test_reload_event_raises_reload_request(self, webui_manager):
        # logout() arms _reload_requested; the next HTTP call wrapped in
        # coro_unless_closed must raise ReloadRequest to trigger shutdown → re-login.
        from exceptions import ReloadRequest

        async def _run():
            webui_manager._reload_requested.set()
            await webui_manager.coro_unless_closed(asyncio.sleep(9999))

        with pytest.raises(ReloadRequest):
            asyncio.run(_run())

    def test_reload_event_cleared_before_raising(self, webui_manager):
        # _reload_requested must be cleared before the exception propagates so the
        # fresh _run() loop that follows doesn't immediately raise ReloadRequest again.
        from exceptions import ReloadRequest

        async def _run():
            webui_manager._reload_requested.set()
            try:
                await webui_manager.coro_unless_closed(asyncio.sleep(9999))
            except ReloadRequest:
                pass
            return webui_manager._reload_requested.is_set()

        assert asyncio.run(_run()) is False

    def test_close_signalled_mid_coro_still_interrupts(self, webui_manager):
        # close() can be called from inside an already-running coroutine (e.g. an
        # error handler sets the flag); the race must still fire and cancel the coro.
        from exceptions import ExitRequest

        async def _run():
            async def set_close_then_hang():
                webui_manager._close_requested.set()
                await asyncio.sleep(9999)

            await webui_manager.coro_unless_closed(set_close_then_hang())

        with pytest.raises(ExitRequest):
            asyncio.run(_run())
