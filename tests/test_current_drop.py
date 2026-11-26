"""Exercise nullable Twitch responses through the real watch and claim paths."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from constants import State
from exceptions import GQLException
from tests.test_point_farming import channel, client  # noqa: F401


SESSION = {"dropID": "drop", "currentMinutesWatched": 12}
RESPONSES = [
    {"data": None},
    {"data": {"currentUser": None}},
    {"data": {"currentUser": {"dropCurrentSession": None}}},
    {"data": {"currentUser": {"dropCurrentSession": SESSION}}},
]


@pytest.mark.parametrize("response", RESPONSES + [GQLException("fixture")])
def test_watch_loop_handles_missing_session_and_keeps_polling(client, monkeypatch, response):
    from twitch import Twitch

    watched = channel(drop=True)
    watched.send_watch = AsyncMock(return_value=True)
    client.watching_channel.set(watched)
    drop = MagicMock(name="drop")
    drop.can_earn.return_value = True
    client._drops = {"drop": drop}
    client.get_active_campaign = MagicMock(return_value=None)
    client._watch_sleep = AsyncMock(side_effect=asyncio.CancelledError)
    if isinstance(response, Exception):
        client.gql_request.side_effect = response
    else:
        client.gql_request.return_value = response
    monkeypatch.setattr("twitch.asyncio.sleep", AsyncMock())

    # Cancellation at the ordinary poll wait proves the critical loop survived.
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(Twitch._watch_loop.__wrapped__(client))

    client._watch_sleep.assert_awaited_once()
    watched.send_watch.assert_awaited_once()
    if response == RESPONSES[-1]:
        drop.update_minutes.assert_called_once_with(12)
        client.get_active_campaign.assert_not_called()
    else:
        drop.update_minutes.assert_not_called()
        client.get_active_campaign.assert_called_once_with(watched)


@pytest.mark.parametrize("response", RESPONSES)
@pytest.mark.parametrize("can_earn", [False, True])
def test_claim_continues_selection_after_nullable_session(
    client, monkeypatch, response, can_earn
):
    from twitch import Twitch

    watched = channel(drop=True)
    client.watching_channel.set(watched)
    drop = MagicMock()
    drop.id = "drop"
    drop.claim = AsyncMock(return_value=True)
    drop.campaign.can_earn.return_value = can_earn
    client._drops = {"drop": drop}
    client.restart_watching = MagicMock()
    client.change_state = MagicMock()
    # A still-current claimed drop gets another poll, then an empty session.
    client.gql_request.side_effect = [response, RESPONSES[2]]
    monkeypatch.setattr("twitch.asyncio.sleep", AsyncMock())

    asyncio.run(Twitch.process_drops.__wrapped__(client, 1, {
        "type": "drop-claim",
        "data": {"drop_id": "drop", "drop_instance_id": "fixture"},
    }))

    drop.claim.assert_awaited_once()
    drop.update_claim.assert_called_once_with("fixture")
    assert client.gql_request.await_count == (2 if response == RESPONSES[-1] else 1)
    if can_earn:
        client.restart_watching.assert_called_once_with()
        client.change_state.assert_not_called()
    else:
        client.restart_watching.assert_not_called()
        client.change_state.assert_called_once_with(State.INVENTORY_FETCH)
