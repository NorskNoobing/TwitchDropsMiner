"""Reproduce stale stream discovery without contacting Twitch or sending alerts."""

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from channel import Channel, Stream
from tests.test_point_farming import channel, client  # noqa: F401
from webui import point_farming as pf
from webui.handlers import WebUIOutputHandler


def prepare_stream(client, body):
    client.settings.available_drops_check = False
    client.point_farming.drop_can_watch = lambda t, ch: False
    client.on_channel_update = MagicMock()
    watched = Channel(client, id=1, login="first")
    watched._stream = Stream(watched, id=100, game=None, viewers=1, title="fixture")
    client.channels = {watched.id: watched}
    client.gql_request.return_value = {
        "data": {"streamPlaybackAccessToken": {"value": "fixture", "signature": "fixture"}}
    }
    response = SimpleNamespace(text=AsyncMock(return_value=body))
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    client.request = MagicMock(return_value=context)
    return watched, response


@pytest.mark.parametrize("as_list", [False, True])
def test_missing_playback_marks_offline_without_error_notification(client, as_list):
    body = {"error": "Can not find channel"}
    watched, _ = prepare_stream(client, json.dumps([body] if as_list else body))
    output = MagicMock()
    handler = WebUIOutputHandler(output)
    logger = logging.getLogger("TwitchDrops")
    logger.addHandler(handler)
    try:
        assert asyncio.run(watched.send_watch()) is False
    finally:
        logger.removeHandler(handler)
    assert watched.offline
    assert client.point_farming.unavailable_streams[1][0] == 100
    output.notification_service.queue.assert_not_called()


def test_other_playback_errors_still_notify_and_do_not_pause(client):
    watched, _ = prepare_stream(client, json.dumps({"error": "Unauthorized"}))
    output = MagicMock()
    handler = WebUIOutputHandler(output)
    logger = logging.getLogger("TwitchDrops")
    logger.addHandler(handler)
    try:
        assert asyncio.run(watched.send_watch()) is False
    finally:
        logger.removeHandler(handler)
    assert watched.offline
    assert not client.point_farming.unavailable_streams
    output.notification_service.queue.assert_called_once()


def test_stale_discovery_cannot_rewatch_same_broadcast_until_retry_deadline(
    client, monkeypatch
):
    async def check():
        monkeypatch.setattr(pf, "monotonic", lambda: 100)
        watched, _ = prepare_stream(client, json.dumps({"error": "Can not find channel"}))
        assert not await watched.send_watch()
        assert watched.offline
        # Discovery constructs a fresh Channel, so cooldown state must outlive it.
        stale = Channel(client, id=1, login="first")
        stale._stream = Stream(stale, id=100, game=None, viewers=1, title="fixture")
        client.channels = {stale.id: stale}
        for elapsed in (60, 120, 180, 240, 299):
            monkeypatch.setattr(pf, "monotonic", lambda: 100 + elapsed)
            assert not client.can_watch(stale)
            assert not await stale.send_watch()
        assert client.request.call_count == 1
        monkeypatch.setattr(pf, "monotonic", lambda: 400)
        assert client.can_watch(stale)
        assert not client.point_farming.unavailable_streams
        assert not await stale.send_watch()
        assert client.request.call_count == 2
        assert client.point_farming.unavailable_streams[1] == (100, 700)

    asyncio.run(check())


def test_new_broadcast_bypasses_old_broadcast_pause(client, monkeypatch):
    monkeypatch.setattr(pf, "monotonic", lambda: 100)
    watched, _ = prepare_stream(client, json.dumps({"error": "Can not find channel"}))
    assert not asyncio.run(watched.send_watch())
    watched._stream = Stream(watched, id=101, game=None, viewers=1, title="new stream")
    assert client.can_watch(watched)
    assert not client.point_farming.unavailable_streams


def test_paused_drop_channel_does_not_prevent_other_fallback(client, monkeypatch):
    monkeypatch.setattr(pf, "monotonic", lambda: 100)
    fallback, drop = channel(), channel("drops", drop=True, cid=2)
    drop._stream.broadcast_id = 100
    client.channels = {1: fallback, 2: drop}
    assert not client.can_watch(fallback)
    client.point_farming.unavailable_streams[2] = (100, 400)
    assert client.can_watch(fallback)
    monkeypatch.setattr(pf, "monotonic", lambda: 400)
    assert not client.can_watch(fallback)


def test_drop_eligibility_cannot_bypass_pause_with_farming_disabled(client, monkeypatch):
    monkeypatch.setattr(pf, "monotonic", lambda: 100)
    drop = channel("drops", cid=2)
    drop._stream.broadcast_id = 100
    drop.game = SimpleNamespace()
    drop.drops_enabled = True
    client.wanted_games = [drop.game]
    client.inventory = [SimpleNamespace(can_earn=lambda ch: ch is drop)]
    client.settings.point_farming_enabled = False
    assert client.can_watch(drop)
    client.point_farming.unavailable_streams[2] = (100, 400)
    assert not client.can_watch(drop)


def test_successful_playlist_keeps_normal_url_cache(client):
    watched, _ = prepare_stream(client, "#EXTM3U\nhttps://fixture.invalid/playlist.m3u8\n")
    stream = watched._stream
    first = asyncio.run(stream.get_stream_url())
    assert str(first) == "https://fixture.invalid/playlist.m3u8"
    assert asyncio.run(stream.get_stream_url()) == first
    assert client.request.call_count == 1
    assert not stream.playback_unavailable
    assert watched.online


def test_later_success_resets_unavailable_signal(client):
    watched, response = prepare_stream(client, json.dumps({"error": "Can not find channel"}))
    stream = watched._stream
    assert asyncio.run(stream.get_stream_url()) is None
    assert stream.playback_unavailable
    response.text.return_value = "#EXTM3U\nhttps://fixture.invalid/playlist.m3u8\n"
    assert asyncio.run(stream.get_stream_url()) is not None
    assert not stream.playback_unavailable
