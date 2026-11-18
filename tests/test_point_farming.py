"""Fallback regressions run without Twitch credentials or network requests."""

import asyncio
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from constants import MAX_INT, State
from exceptions import GQLException, ReloadRequest
from utils import AwaitableValue
from webui import point_farming as pf


@pytest.fixture
def client(webui_auth_state):
    from twitch import Twitch

    twitch = Twitch.__new__(Twitch)
    twitch.settings = SimpleNamespace(
        point_farming_enabled=True,
        point_farming_channels=["first", "second"],
        dump=False,
    )
    twitch._state = State.IDLE
    twitch._state_change = asyncio.Event()
    twitch._auth_state = SimpleNamespace(_logged_in=asyncio.Event())
    twitch._auth_state._logged_in.set()
    twitch.gui = MagicMock()
    twitch.gui._reload_requested = asyncio.Event()
    twitch.channels = OrderedDict()
    twitch.watching_channel = AwaitableValue()
    twitch.wanted_games = []
    twitch.inventory = []
    twitch.gql_request = AsyncMock()
    twitch._watching_restart = asyncio.Event()
    twitch.point_farming = pf.PointFarming(twitch, lambda t, ch: ch.drop)
    twitch.point_farming.send_minute = AsyncMock(return_value=True)
    return twitch


def channel(login="first", *, drop=False, online=True, cid=1):
    return SimpleNamespace(
        _login=login,
        id=cid,
        name=login,
        online=online,
        drop=drop,
        game=None,
        acl_based=False,
        _stream=SimpleNamespace(),
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        (" First,second\n@FIRST ", ["first", "second"]),
        ("https://www.twitch.tv/First/\nhttps://twitch.tv/second", ["first", "second"]),
        ("", []),
    ],
)
def test_parse_channels(text, expected):
    assert pf.parse_channels(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "https://evil.example/first",
        "https://twitch.tv/first/videos",
        "first!",
        "https://twitch.tv@evil.example/name",
        ",".join(f"channel_{i}" for i in range(21)),
    ],
)
def test_reject_invalid_channels(text):
    with pytest.raises(ValueError):
        pf.parse_channels(text)


def test_disabled_empty_offline_and_unselected_do_not_farm(client):
    farmer = client.point_farming
    assert not farmer.can_farm(channel("other"))
    assert not farmer.can_farm(channel(online=False))
    client.settings.point_farming_enabled = False
    assert not farmer.can_farm(channel())
    client.settings.point_farming_enabled = True
    client.settings.point_farming_channels = []
    assert not farmer.enabled


def test_drop_blocks_manual_fallback_and_resumes_when_drop_unavailable(client):
    fallback, drop = channel(), channel("drops", drop=True, cid=2)
    client.channels = {1: fallback, 2: drop}
    assert not client.can_watch(fallback)
    client.point_farming.drop_can_watch = lambda t, ch: ch.drop and ch.online
    drop.online = False
    assert client.can_watch(fallback)


def test_fallback_priority_order_cannot_beat_lowest_priority_drop(client):
    first, second = channel(), channel("second", cid=2)
    assert client.get_priority(first) == MAX_INT + 1
    assert client.get_priority(second) == MAX_INT + 2
    assert client.get_priority(channel("ineligible")) > client.get_priority(second)
    # The existing core switch logic respects fallback order.
    client.watching_channel.set(second)
    assert client.should_switch(first)
    client.watching_channel.set(first)
    assert not client.should_switch(second)


def test_real_campaign_preempts_farming_and_manual_selection(client):
    fallback, drop = channel(), channel("drops", cid=2)
    drop.game = SimpleNamespace()
    drop.drops_enabled = True
    client.wanted_games = [drop.game]
    client.inventory = [
        SimpleNamespace(
            can_earn=lambda ch: ch is drop,
            game=SimpleNamespace(is_special=lambda: False),
        )
    ]
    client.point_farming.drop_can_watch = lambda t, ch: (
        any(c.can_earn(ch) for c in t.inventory) and ch.online
    )
    client.channels = {1: fallback, 2: drop}
    client.watching_channel.set(fallback)
    assert client.can_watch(drop)
    assert not client.can_watch(fallback)
    assert client.should_switch(drop)
    client.watching_channel.set(drop)
    drop.online = False
    assert client.can_watch(fallback)
    assert client.should_switch(fallback)


def context(balance=50, claim=None):
    return {
        "data": {
            "community": {
                "channel": {
                    "self": {
                        "communityPoints": {"balance": balance, "availableClaim": claim}
                    }
                }
            }
        }
    }


def test_minute_claims_available_bonus_and_throttles(client, monkeypatch):
    async def check():
        watched = channel()
        client.channels = {1: watched}
        client.watching_channel.set(watched)
        client.gql_request.side_effect = [
            context(claim={"id": "fixture_claim"}),
            {"data": {}},
        ]
        monkeypatch.setattr(pf, "monotonic", lambda: 100)
        await client.point_farming.minute(watched)
        await client.point_farming.minute(watched)
        assert client.point_farming.send_minute.await_count == 1
        assert client.gql_request.await_count == 2
        claim_op = client.gql_request.call_args_list[1].args[0]
        assert claim_op["variables"]["input"] == {
            "claimID": "fixture_claim",
            "channelID": "1",
        }
        assert client.point_farming.balances == {1: 50}

    asyncio.run(check())


def test_settings_default_off_persist_and_disable_immediately(
    client, tmp_path, monkeypatch
):
    import settings
    from webui.components.settings.points_section import PointsSection

    monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")
    client.settings = settings.Settings(SimpleNamespace())
    assert client.settings.point_farming_enabled is False
    assert client.settings.point_farming_channels == []
    section = PointsSection(SimpleNamespace(_twitch=client))
    section.apply(True, "Second\n@first\nSECOND")
    restored = settings.Settings(SimpleNamespace())
    assert restored.point_farming_enabled is True
    assert restored.point_farming_channels == ["second", "first"]
    client.watching_channel.set(channel())
    section.apply(False, "second\nfirst")
    assert client.watching_channel.get_with_default(None) is None
    assert client._state is State.GAMES_UPDATE
    restored = settings.Settings(SimpleNamespace())
    assert restored.point_farming_enabled is False
    assert restored.point_farming_channels == ["second", "first"]


def test_invalid_settings_leave_current_farming_intact(client):
    from webui.components.settings.points_section import PointsSection

    section = PointsSection(SimpleNamespace(_twitch=client))
    with pytest.raises(ValueError):
        section.apply(False, "https://evil.example/channel")
    assert client.settings.point_farming_enabled is True
    assert client.settings.point_farming_channels == ["first", "second"]


def test_stale_context_never_claims_or_overwrites_status(client):
    async def check():
        watched = channel()
        client.watching_channel.set(watched)

        async def swapped(op):
            client.watching_channel.clear()
            return context(claim={"id": "fixture_claim"})

        client.gql_request.side_effect = swapped
        await client.point_farming.minute(watched)
        assert client.gql_request.await_count == 1
        assert client.point_farming.balances == {}
        client.gui.status.update.assert_not_called()

    asyncio.run(check())


@pytest.mark.parametrize(
    "response", [{"data": {"community": None}}, context(balance=True)]
)
def test_unsupported_points_and_invalid_balance_do_not_crash(client, response):
    async def check():
        watched = channel()
        client.watching_channel.set(watched)
        client.gql_request.return_value = response
        await client.point_farming.minute(watched)
        assert client.point_farming.balances == {}

    asyncio.run(check())


def test_point_api_failure_is_nonfatal_but_reload_propagates(client):
    async def check():
        watched = channel()
        client.watching_channel.set(watched)
        client.gql_request.side_effect = GQLException("fixture")
        await client.point_farming.minute(watched)
        client.point_farming.last_minute = float("-inf")
        client.point_farming.last_points = float("-inf")
        client.gql_request.side_effect = ReloadRequest()
        with pytest.raises(ReloadRequest):
            await client.point_farming.minute(watched)

    asyncio.run(check())


def test_poll_checks_campaigns_and_offline_channels_without_a_watch_task(
    client, monkeypatch
):
    farmer = client.point_farming
    farmer.last_channel_check = farmer.last_campaign_check = 0
    monkeypatch.setattr(pf, "monotonic", lambda: 61)
    farmer.poll()
    assert client._state is State.CHANNELS_FETCH
    client._state = State.IDLE
    client._state_change.clear()
    monkeypatch.setattr(pf, "monotonic", lambda: 301)
    farmer.poll()
    assert client._state is State.INVENTORY_FETCH


@pytest.mark.parametrize(
    "state", [State.EXIT, State.RESTART, State.INVENTORY_FETCH, State.CHANNELS_FETCH]
)
def test_poll_never_overwrites_inflight_or_terminal_state(client, state):
    client._state = state
    client.point_farming.last_campaign_check = float("-inf")
    client.point_farming.poll()
    assert client._state is state


def test_poll_stops_when_logged_out_or_disabled(client):
    client._auth_state._logged_in.clear()
    client.point_farming.last_campaign_check = float("-inf")
    client.point_farming.poll()
    assert client._state is State.IDLE
    client._auth_state._logged_in.set()
    client.settings.point_farming_enabled = False
    client.point_farming.poll()
    assert client._state is State.IDLE


def test_discovery_handles_missing_and_offline_channels(client):
    async def check():
        client.gql_request.return_value = [
            {"data": {"user": None}},
            {"data": {"user": {"id": "2", "displayName": "Second", "stream": None}}},
        ]
        channels = await client.point_farming.channels()
        assert len(channels) == 1
        assert channels[0]._login == "second"
        assert not channels[0].online

    asyncio.run(check())


def test_discovery_keeps_other_channels_after_one_malformed_response(client):
    async def check():
        client.gql_request.return_value = [
            {"errors": []},
            {"data": {"user": {"id": "2", "displayName": "Second", "stream": None}}},
        ]
        assert len(await client.point_farming.channels()) == 1

    asyncio.run(check())


def test_polling_refreshes_existing_offline_channel_in_place(client):
    from channel import Channel

    async def check():
        existing = Channel(client, id="1", login="first")
        client.settings.available_drops_check = False
        client.settings.point_farming_channels = ["first"]
        client.gql_request.return_value = [
            {
                "data": {
                    "user": {
                        "id": "1",
                        "displayName": "First",
                        "stream": {"id": "123", "viewersCount": 1},
                        "broadcastSettings": {"game": None, "title": "Fixture"},
                    }
                }
            }
        ]
        refreshed = await client.point_farming.channels([existing])
        assert refreshed == [existing]
        assert refreshed[0] is existing
        assert existing.online
        client.gql_request.return_value[0]["data"]["user"]["stream"] = None
        await client.point_farming.channels([existing])
        assert not existing.online

    asyncio.run(check())


def test_discovery_failure_and_timeout_are_nonfatal(client):
    async def check():
        for error in (GQLException("fixture"), asyncio.TimeoutError()):
            client.gql_request.side_effect = error
            assert await client.point_farming.channels() == []

    asyncio.run(check())


def test_core_enters_fallback_without_any_drop_campaign_and_tears_down(client):
    from channel import Channel

    async def check():
        farmer = client.point_farming
        farmer.drop_can_watch = lambda t, ch: False
        fallback = Channel(client, id="1", login="first")
        fallback._stream = SimpleNamespace(game=None, viewers=1, drops_enabled=False)
        client._watching_task = None
        client._auth_state.user_id = 10
        client.get_auth = AsyncMock(return_value=client._auth_state)
        client.fetch_inventory = AsyncMock()
        client.save = MagicMock()
        client.websocket = MagicMock()
        client.websocket.start = AsyncMock()
        client._watch_loop = AsyncMock()
        client.settings.exclude = set()
        client.settings.priority = []
        from constants import PriorityMode

        client.settings.priority_mode = PriorityMode.PRIORITY_ONLY
        farmer.channels = AsyncMock(return_value=[fallback])
        stopped = asyncio.Event()

        async def background():
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        farmer.run = background
        task = asyncio.create_task(client._run())
        try:
            for _ in range(100):
                await asyncio.sleep(0)
                if client.watching_channel.get_with_default(None) is fallback:
                    break
            assert client.watching_channel.get_with_default(None) is fallback
            assert client._state is State.CHANNEL_SWITCH
            client.close()
            await asyncio.wait_for(task, 1)
            assert stopped.is_set()
            assert farmer.balances == {}
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if client._watching_task:
                client._watching_task.cancel()
                await asyncio.gather(client._watching_task, return_exceptions=True)

    asyncio.run(check())


def test_point_heartbeat_uses_beacon_form_and_fresh_browser_attribution(
    client, monkeypatch
):
    import json
    from base64 import b64decode
    from contextlib import asynccontextmanager

    async def check():
        calls = []

        @asynccontextmanager
        async def request(*args, **kwargs):
            calls.append((args, kwargs))
            yield SimpleNamespace(status=204)

        client.request = request
        watched = channel()
        original = {
            "user_id": 123,
            "channel_id": "1",
            "broadcast_id": "2",
            "client_time": "old",
        }
        client.watching_channel.set(watched)
        watched._stream._watch_payload = [
            {"event": "minute-watched", "properties": original}
        ]
        monkeypatch.setattr(pf, "isonow", lambda: "new")
        assert await pf.PointFarming.send_minute(client.point_farming, watched)
        args, kwargs = calls[0]
        assert args == ("POST", "https://beacon.twitch.tv/track")
        event = json.loads(b64decode(kwargs["data"]["data"]))[0]
        assert event["event"] == "minute-watched"
        assert event["properties"]["client_time"] == "new"
        assert event["properties"]["player"] == "site"
        assert event["properties"]["location"] == "channel"
        assert event["properties"]["user_id"] == 123
        assert original["client_time"] == "old"

    asyncio.run(check())
