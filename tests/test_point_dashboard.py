import asyncio

pytest_plugins = ["tests.test_point_farming"]

import pytest

from exceptions import GQLException
from tests.test_point_farming import channel, context


def test_observed_gains_ignore_first_balance_and_spending(client):
    farmer = client.point_farming
    watched = channel()
    farmer.record_balance(watched, 400)
    assert farmer.gained[1] == 0
    farmer.record_balance(watched, 412)
    farmer.record_balance(watched, 300)
    farmer.record_balance(watched, 310)
    assert farmer.gained[1] == 22
    assert farmer.dashboard_rows()[0]["balance_value"] == "310"
    assert farmer.dashboard_rows()[0]["gained"] == "+22"
    farmer.record_balance(channel("second", cid=2), 5000)
    assert farmer.gained[2] == 0


def test_claims_confirmed_bonus_once_and_includes_reported_credit(client):
    async def check():
        farmer = client.point_farming
        watched = channel()
        client.watching_channel.set(watched)
        client.gql_request.side_effect = [
            context(100, {"id": "fixture_bonus"}),
            {
                "data": {
                    "claimCommunityPoints": {
                        "error": None,
                        "currentPoints": {"balance": 200},
                    }
                }
            },
            context(200, {"id": "fixture_bonus"}),
        ]
        await farmer.refresh_points(watched)
        assert farmer.bonus_claims == {1: 1}
        assert farmer.balances == {1: 200}
        assert farmer.gained == {1: 100}
        farmer.last_points = float("-inf")
        await farmer.refresh_points(watched)
        assert client.gql_request.await_count == 3
        assert farmer.bonus_claims == {1: 1}

    asyncio.run(check())


@pytest.mark.parametrize(
    "result",
    [
        {"data": {"claimCommunityPoints": {"error": "ALREADY_CLAIMED"}}},
        {"data": {"claimCommunityPoints": None}},
        {"data": {"claimCommunityPoints": {}}},
        {"data": {}},
        {"errors": [{"message": "fixture"}]},
    ],
)
def test_failed_or_unconfirmed_claims_never_count(client, result):
    async def check():
        watched = channel()
        client.watching_channel.set(watched)
        client.gql_request.side_effect = [context(100, {"id": "fixture_bonus"}), result]
        await client.point_farming.refresh_points(watched)
        assert client.point_farming.bonus_claims == {}
        assert client.point_farming.gained == {1: 0}

    asyncio.run(check())


def test_balance_and_bonus_polling_work_during_drops_without_watch_telemetry(client):
    async def check():
        watched = channel(drop=True)
        client.channels = {1: watched}
        client.watching_channel.set(watched)
        assert not client.point_farming.active(watched)
        client.gql_request.return_value = context(150)
        await client.point_farming.refresh_points(watched)
        assert client.point_farming.balances == {1: 150}
        client.point_farming.send_minute.assert_not_awaited()

    asyncio.run(check())


def test_failed_refresh_preserves_last_balance_and_reports_staleness(client):
    async def check():
        farmer = client.point_farming
        watched = channel()
        client.watching_channel.set(watched)
        farmer.record_balance(watched, 42)
        previous_check = farmer.checked_at[1]
        client.gql_request.side_effect = GQLException("fixture")
        await farmer.refresh_points(watched)
        assert farmer.refresh_failed
        assert farmer.balances == {1: 42}
        assert farmer.checked_at[1] == previous_check
        farmer.last_points = float("-inf")
        client.gql_request.side_effect = None
        client.gql_request.return_value = context(54)
        await farmer.refresh_points(watched)
        assert not farmer.refresh_failed
        assert farmer.gained[1] == 12

    asyncio.run(check())


def test_concurrent_pollers_do_not_duplicate_claims(client):
    async def check():
        watched = channel()
        client.watching_channel.set(watched)
        client.gql_request.side_effect = [
            context(100, {"id": "fixture_bonus"}),
            {
                "data": {
                    "claimCommunityPoints": {
                        "error": None,
                        "currentPoints": {"balance": 150},
                    }
                }
            },
        ]
        farmer = client.point_farming
        await asyncio.gather(
            farmer.refresh_points(watched), farmer.refresh_points(watched)
        )
        assert farmer.bonus_claims[1] == 1
        assert client.gql_request.await_count == 2

    asyncio.run(check())
