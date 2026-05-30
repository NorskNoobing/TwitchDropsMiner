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
        # StatusBarAdapter.update() → manager.update_status() → _status_text, which
        # NiceGUI bind_text_from reads to render the status label on every client.
        webui_manager.status.update("Mining drops")
        assert webui_manager._status_text == "Mining drops"

    def test_print_appends_timestamped_line_to_console_log(self, webui_manager):
        # manager.print() must prepend a HH:MM:SS stamp and land the line in the
        # persistent console log that late-joining clients load on page open.
        section = webui_manager.main_panel._console_section
        webui_manager.print("hello_unique_xZq")
        assert "hello_unique_xZq" in section._console_log[-1]

    def test_print_multiline_adds_one_entry_per_line(self, webui_manager):
        # twitch.py sometimes prints multi-line strings; each logical line must get
        # its own timestamp so the console log stays readable.
        section = webui_manager.main_panel._console_section
        webui_manager.print("multi_a_xZq\nmulti_b_xZq\nmulti_c_xZq")
        tail = section._console_log[-3:]
        assert any("multi_a_xZq" in line for line in tail)
        assert any("multi_b_xZq" in line for line in tail)
        assert any("multi_c_xZq" in line for line in tail)

    def test_close_sets_close_requested(self, webui_manager):
        # close_requested is polled by coro_unless_closed() to decide whether to
        # raise ExitRequest; manager.close() must arm it.
        assert not webui_manager.close_requested
        webui_manager.close()
        assert webui_manager.close_requested

    def test_restart_arms_reload_requested(self, webui_manager):
        # restart() races _reload_requested against the next HTTP call in
        # coro_unless_closed(), triggering a full shutdown → re-login cycle.
        assert not webui_manager._reload_requested.is_set()
        webui_manager.restart()
        assert webui_manager._reload_requested.is_set()


# ---------------------------------------------------------------------------
# Channel adapter → ChannelsSection state
# ---------------------------------------------------------------------------

class TestChannelAdapterFlow:
    def test_display_add_inserts_channel_into_map(self, webui_manager):
        # add=True is the first call for a new channel; it must create the map entry
        # that subsequent display(add=False) updates rely on.
        ch = _make_channel(iid="ch1")
        webui_manager.channels.display(ch, add=True)
        assert "ch1" in webui_manager.main_panel._channels_section._channel_map

    def test_display_update_ignored_when_channel_not_yet_in_map(self, webui_manager):
        # add=False is an in-place refresh for an existing channel; silently dropping
        # it when the channel isn't in the map prevents phantom rows.
        ch = _make_channel(iid="ch2")
        webui_manager.channels.display(ch, add=False)
        assert "ch2" not in webui_manager.main_panel._channels_section._channel_map

    def test_display_update_replaces_existing_entry(self, webui_manager):
        # Viewer count, online status, etc. change frequently; add=False must
        # overwrite the stored Channel object so the table shows current data.
        webui_manager.channels.display(_make_channel(iid="ch3", name="OldName"), add=True)
        webui_manager.channels.display(_make_channel(iid="ch3", name="NewName"), add=False)
        assert webui_manager.main_panel._channels_section._channel_map["ch3"].name == "NewName"

    def test_remove_drops_channel_from_map(self, webui_manager):
        # When twitch.py drops a channel it calls remove(); the row must disappear
        # from the map so it is no longer rendered in any client's table.
        ch = _make_channel(iid="ch4")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.remove(ch)
        assert "ch4" not in webui_manager.main_panel._channels_section._channel_map

    def test_clear_empties_channel_map(self, webui_manager):
        # clear() is called on logout / session restart; all rows must be gone so
        # the next session starts with a blank channel list.
        for i in range(3):
            webui_manager.channels.display(_make_channel(iid=f"clr{i}"), add=True)
        webui_manager.channels.clear()
        assert len(webui_manager.main_panel._channels_section._channel_map) == 0

    def test_set_watching_prefixes_row_name_with_arrow(self, webui_manager):
        # The currently-watched channel is indicated visually by a ▶ prefix in the
        # channel name cell; set_watching() must trigger that rebuild.
        ch = _make_channel(iid="w1", name="WatchMe")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        section = webui_manager.main_panel._channels_section
        assert any(r["channel"].startswith("▶") for r in section._channel_rows)

    def test_clear_watching_removes_arrow_prefix(self, webui_manager):
        # When the miner stops watching (e.g. channel goes offline), the ▶ prefix
        # and the internal iid marker must both be cleared.
        ch = _make_channel(iid="w2", name="WatchMe")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        webui_manager.channels.clear_watching()
        section = webui_manager.main_panel._channels_section
        assert section._watching_channel_iid is None
        assert not any(r["channel"].startswith("▶") for r in section._channel_rows)

    def test_remove_clears_watching_state_for_that_channel(self, webui_manager):
        # Removing a channel that is currently being watched must also clear the
        # watching marker; otherwise a stale iid would point to a non-existent row.
        ch = _make_channel(iid="w3")
        webui_manager.channels.display(ch, add=True)
        webui_manager.channels.set_watching(ch)
        webui_manager.channels.remove(ch)
        assert webui_manager.main_panel._channels_section._watching_channel_iid is None

    def test_get_selection_returns_channel_when_selected(self, webui_manager):
        # twitch.py reads get_selection() during CHANNEL_SWITCH to find out which
        # channel the user clicked; it must return the actual Channel object.
        ch = _make_channel(iid="s1")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s1"
        assert webui_manager.channels.get_selection() is ch

    def test_clear_selection_makes_get_selection_return_none(self, webui_manager):
        # After a channel switch completes, twitch.py calls clear_selection() so a
        # stale selection doesn't re-trigger another switch on the next state cycle.
        ch = _make_channel(iid="s2")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s2"
        webui_manager.channels.clear_selection()
        assert webui_manager.channels.get_selection() is None

    def test_remove_clears_selection_for_that_channel(self, webui_manager):
        # If the selected channel is removed (e.g. goes offline and is pruned),
        # the stale selection must be cleared to avoid returning a dead reference.
        ch = _make_channel(iid="s3")
        webui_manager.channels.display(ch, add=True)
        webui_manager.main_panel._channels_section._selected_channel_iid = "s3"
        webui_manager.channels.remove(ch)
        assert webui_manager.main_panel._channels_section._selected_channel_iid is None

    def test_channel_row_reflects_online_status(self, webui_manager):
        # _build_rows() maps channel.online/pending_online to a localised status
        # string; online=True must produce the "online" translation key text.
        from translate import _
        ch = _make_channel(iid="r1", online=True, pending_online=False)
        webui_manager.channels.display(ch, add=True)
        row = next(r for r in webui_manager.main_panel._channels_section._channel_rows if r["iid"] == "r1")
        assert row["status"] == _("gui", "channels", "online")

    def test_channel_row_reflects_offline_status(self, webui_manager):
        # online=False, pending_online=False must produce the "offline" status text
        # (not "pending"), so the table doesn't mislead the user.
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
        # countdown=True means twitch.py just started watching; the section must
        # start the per-second timer so the remaining-time display counts down.
        drop = _make_drop()
        webui_manager.progress.display(drop, countdown=True)
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is drop
        assert section._countdown_active is True

    def test_display_without_countdown_stores_60_seconds(self, webui_manager):
        # countdown=False is used when the miner resumes an already-in-progress
        # minute; the display should show a full 60 s but not tick down.
        drop = _make_drop()
        webui_manager.progress.display(drop, countdown=False)
        section = webui_manager.main_panel._drop_section
        assert section._countdown_active is False
        assert section._progress_seconds == 60

    def test_display_subone_sets_progress_to_zero(self, webui_manager):
        # subone=True signals "this drop is the sub-minute remainder"; progress
        # starts at 0 so minute_almost_done() returns True immediately.
        webui_manager.progress.display(_make_drop(), countdown=False, subone=True)
        assert webui_manager.main_panel._drop_section._progress_seconds == 0

    def test_display_none_clears_drop(self, webui_manager):
        # twitch.py passes None when there is no active drop; the section must
        # clear its state rather than leaving stale campaign data on screen.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.progress.display(None)
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is None
        assert section._countdown_active is False

    def test_display_populates_campaign_and_drop_text(self, webui_manager):
        # The campaign game, name, and reward text are extracted from the Drop
        # object and stored as plain strings that NiceGUI bind_text_from reads.
        drop = _make_drop(game_name="MyGame", campaign_name="MyCampaign", rewards="Gold")
        webui_manager.progress.display(drop, countdown=False)
        section = webui_manager.main_panel._drop_section
        assert section._campaign_game_text == "MyGame"
        assert section._campaign_name_text == "MyCampaign"
        assert section._drop_rewards_text == "Gold"

    def test_clear_drop_resets_display_text_and_progress(self, webui_manager):
        # clear_drop() is called when a drop is claimed or abandoned; all display
        # attributes must return to their "no drop" placeholder values.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.clear_drop()
        section = webui_manager.main_panel._drop_section
        assert section._current_drop is None
        assert section._campaign_game_text == "..."
        assert section._drop_rewards_text == "..."
        assert section._campaign_progress_value == 0.0
        assert section._drop_progress_value == 0.0

    def test_stop_timer_deactivates_countdown(self, webui_manager):
        # stop_timer() is called when the miner pauses (e.g. no eligible stream);
        # the countdown must freeze so the display doesn't keep ticking.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.progress.stop_timer()
        assert webui_manager.main_panel._drop_section._countdown_active is False

    def test_minute_almost_done_false_while_countdown_active_with_time_remaining(self, webui_manager):
        # twitch.py calls minute_almost_done() to decide whether to send a watch
        # heartbeat; it must return False when there is still time left in the minute.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 59
        assert webui_manager.progress.minute_almost_done() is False

    def test_minute_almost_done_true_after_stop_timer(self, webui_manager):
        # Once the countdown is stopped, minute_almost_done() must return True
        # regardless of _progress_seconds so the heartbeat is sent promptly.
        webui_manager.progress.display(_make_drop(), countdown=True)
        webui_manager.main_panel._drop_section._progress_seconds = 59
        webui_manager.progress.stop_timer()
        assert webui_manager.progress.minute_almost_done() is True

    def test_minute_almost_done_true_at_ten_second_boundary(self, webui_manager):
        # The threshold is <= 10 s; at exactly 10 the heartbeat window opens so
        # twitch.py can send the watch request before the minute rolls over.
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
        # First update for a slot initialises the entry with the provided status
        # and topic count so the WS status card shows correct data immediately.
        webui_manager.websockets.update(0, status="connected", topics=5)
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["status"] == "connected"
        assert entry["topics"] == 5

    def test_update_status_only_leaves_topics_unchanged(self, webui_manager):
        # twitch.py updates status and topics independently; a status-only call
        # must not zero out the topic count that was set by an earlier call.
        webui_manager.websockets.update(0, status="connected", topics=5)
        webui_manager.websockets.update(0, status="disconnected")
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["topics"] == 5
        assert entry["status"] == "disconnected"

    def test_update_topics_only_leaves_status_unchanged(self, webui_manager):
        # Same independence in the other direction: updating the topic count must
        # not reset a "connected" status back to the disconnected default.
        webui_manager.websockets.update(0, status="connected", topics=5)
        webui_manager.websockets.update(0, topics=8)
        entry = webui_manager.main_panel._ws_section._ws_data[0]
        assert entry["status"] == "connected"
        assert entry["topics"] == 8

    def test_update_with_no_params_raises_type_error(self, webui_manager):
        # Calling update() without either keyword arg is a programmer error;
        # the adapter must raise TypeError rather than silently doing nothing.
        with pytest.raises(TypeError):
            webui_manager.websockets.update(0)

    def test_remove_drops_entry(self, webui_manager):
        # When a WebSocket connection is torn down twitch.py calls remove(); the
        # slot must disappear from _ws_data so the status card stops showing it.
        webui_manager.websockets.update(0, status="connected", topics=3)
        webui_manager.websockets.remove(0)
        assert 0 not in webui_manager.main_panel._ws_section._ws_data

    def test_multiple_slots_tracked_independently(self, webui_manager):
        # The app can run up to MAX_WEBSOCKETS connections simultaneously; each
        # slot's status and topic count must be stored and removed independently.
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
        # The user ID (an integer from the Twitch API) must be converted to a
        # string so the login card's label can display it directly.
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 12345)
        assert webui_manager.main_panel._login_section._user_str == "12345"

    def test_update_none_user_id_shows_dash(self, webui_manager):
        # Before login the user ID is None; the card must show "-" rather than
        # "None" to keep the UI clean.
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_out"), None)
        assert webui_manager.main_panel._login_section._user_str == "-"

    def test_update_maps_localized_status_to_internal_key(self, webui_manager):
        # twitch.py passes the full localised string; LoginSection must map it back
        # to a stable key ("logged_in") that controls button visibility and text.
        from translate import _
        webui_manager.login.update(_("gui", "login", "logged_in"), 1)
        assert webui_manager.main_panel._login_section._login_state == "logged_in"

    def test_login_required_mirrors_to_status_bar(self, webui_manager):
        # When device-code login is needed the main loop hasn't set a status yet;
        # the login adapter must push the status to the bar so the user sees it.
        from translate import _
        status = _("gui", "login", "required")
        webui_manager.login.update(status, None)
        assert webui_manager._status_text == status

    def test_logged_in_does_not_mirror_to_status_bar(self, webui_manager):
        # Once logged in, twitch.py owns the status bar; the login adapter must
        # not overwrite it with "logged in" and erase the current mining status.
        from translate import _
        webui_manager.status.update("Mining")
        webui_manager.login.update(_("gui", "login", "logged_in"), 1)
        assert webui_manager._status_text == "Mining"


# ---------------------------------------------------------------------------
# coro_unless_closed — async interrupt races
# ---------------------------------------------------------------------------

class TestCoroUnlessClosed:
    def test_normal_coroutine_returns_its_result(self, webui_manager):
        # When neither close nor reload is signalled the wrapped coroutine must
        # run to completion and its return value must be forwarded to the caller.
        async def _run():
            async def produce():
                return 42
            return await webui_manager.coro_unless_closed(produce())

        assert asyncio.run(_run()) == 42

    def test_close_event_pre_set_raises_exit_request(self, webui_manager):
        # If close was already requested before the coroutine starts (e.g. the
        # user closed the browser), coro_unless_closed must raise ExitRequest
        # immediately rather than letting the coroutine run.
        from exceptions import ExitRequest

        async def _run():
            webui_manager._close_requested.set()
            await webui_manager.coro_unless_closed(asyncio.sleep(9999))

        with pytest.raises(ExitRequest):
            asyncio.run(_run())

    def test_reload_event_pre_set_raises_reload_request(self, webui_manager):
        # logout() arms _reload_requested; the next coro_unless_closed call must
        # raise ReloadRequest so run() can call shutdown() then restart _run().
        from exceptions import ReloadRequest

        async def _run():
            webui_manager._reload_requested.set()
            await webui_manager.coro_unless_closed(asyncio.sleep(9999))

        with pytest.raises(ReloadRequest):
            asyncio.run(_run())

    def test_reload_clears_the_event_after_raising(self, webui_manager):
        # _reload_requested must be cleared before raising so the fresh _run()
        # that follows doesn't immediately raise ReloadRequest again.
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
        # close() can be called from within an already-running coroutine (e.g. an
        # error handler); the race must still fire and cancel the hanging coro.
        from exceptions import ExitRequest

        async def _run():
            async def set_close_then_hang():
                webui_manager._close_requested.set()
                await asyncio.sleep(9999)

            await webui_manager.coro_unless_closed(set_close_then_hang())

        with pytest.raises(ExitRequest):
            asyncio.run(_run())
