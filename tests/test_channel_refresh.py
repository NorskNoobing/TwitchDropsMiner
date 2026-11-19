import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from channel import Channel
from constants import PriorityMode, State

pytest_plugins = ["tests.test_point_farming"]


@pytest.mark.parametrize("channel_id", [43683025, 71092938])
def test_stream_event_during_discovery_keeps_tracked_channel(
    client, caplog, channel_id
):
    async def check():
        farmer = client.point_farming
        farmer.drop_can_watch = lambda t, ch: False
        fallback = Channel(client, id=channel_id, login="first")
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
        client.settings.priority_mode = PriorityMode.PRIORITY_ONLY
        refreshed = asyncio.Event()
        calls = 0

        async def discover(existing=()):
            nonlocal calls
            calls += 1
            if calls > 1:
                # A real callback runs while the refresh awaits Twitch's response.
                await asyncio.sleep(0)
                await client.process_stream_state(
                    channel_id, {"type": "viewcount", "viewers": 123}
                )
                refreshed.set()
            return [fallback]

        async def background():
            await asyncio.Event().wait()

        farmer.channels = discover
        farmer.run = background
        task = asyncio.create_task(client._run())
        try:
            for _ in range(100):
                await asyncio.sleep(0)
                if client.watching_channel.get_with_default(None) is fallback:
                    break
            assert client.channels.get(channel_id) is fallback
            client.change_state(State.CHANNELS_FETCH)
            await asyncio.wait_for(refreshed.wait(), 1)
            assert fallback.viewers == 123
            assert client.channels[channel_id] is fallback
            assert "non-existing channel" not in caplog.text
            client.close()
            await asyncio.wait_for(task, 1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if client._watching_task:
                client._watching_task.cancel()
                await asyncio.gather(client._watching_task, return_exceptions=True)

    with caplog.at_level(logging.ERROR, logger="TwitchDrops"):
        asyncio.run(check())


def test_genuinely_unknown_channel_still_reports_error(client, caplog):
    with caplog.at_level(logging.ERROR, logger="TwitchDrops"):
        asyncio.run(
            client.process_stream_state(99999, {"type": "viewcount", "viewers": 1})
        )
    assert "non-existing channel: 99999" in caplog.text
