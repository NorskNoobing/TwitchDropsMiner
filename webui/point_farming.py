"""Opt-in WebUI fallback; the core remains the sole owner of stream watching."""

from __future__ import annotations

import asyncio
import logging
import re
from base64 import b64encode
from contextlib import suppress
from time import monotonic
from urllib.parse import urlsplit

from channel import Channel
from constants import GQL_QUERIES, MAX_INT, State
from exceptions import ExitRequest, ReloadRequest, RequestException
from translate import _
from utils import isonow, json_minify

logger = logging.getLogger("TwitchDrops")
CHANNEL_INTERVAL = 60
CAMPAIGN_INTERVAL = 300
REQUEST_TIMEOUT = 20


def parse_channels(text: str) -> list[str]:
    channels = []
    for item in re.split(r"[\s,]+", text.strip()):
        if not item:
            continue
        if "://" in item:
            url = urlsplit(item)
            if url.scheme != "https" or url.netloc.lower() not in (
                "twitch.tv",
                "www.twitch.tv",
                "m.twitch.tv",
            ):
                raise ValueError("Invalid Twitch channel")
            item = url.path.strip("/")
        name = item.removeprefix("@").lower()
        if not re.fullmatch(r"[a-z0-9_]{1,25}", name):
            raise ValueError("Invalid Twitch channel")
        if name not in channels:
            channels.append(name)
    if len(channels) > 20:
        raise ValueError("Too many channels")
    return channels


class PointFarming:
    def __init__(self, twitch, can_watch):
        self.twitch = twitch
        self.drop_can_watch = can_watch
        self.last_minute = float("-inf")
        self.last_channel_check = monotonic()
        self.last_campaign_check = monotonic()
        self.balances: dict[int, int] = {}

    @property
    def logins(self) -> list[str]:
        return self.twitch.settings.point_farming_channels

    @property
    def enabled(self) -> bool:
        return bool(self.twitch.settings.point_farming_enabled and self.logins)

    def drop_available(self) -> bool:
        return any(
            self.drop_can_watch(self.twitch, ch) for ch in self.twitch.channels.values()
        )

    def can_farm(self, channel) -> bool:
        return (
            self.enabled
            and channel.online
            and channel._login.lower() in self.logins
            and not self.drop_available()
        )

    def active(self, channel) -> bool:
        return (
            self.can_farm(channel)
            and not self.drop_can_watch(self.twitch, channel)
            and self.twitch.watching_channel.get_with_default(None) is channel
            and not self.twitch.gui._reload_requested.is_set()
            and self.twitch._state not in (State.EXIT, State.RESTART)
        )

    async def channels(self, existing=()) -> list[Channel]:
        if not self.enabled or self.twitch.settings.dump:
            return []
        logins = list(self.logins)
        existing = {ch._login.lower(): ch for ch in existing}
        try:
            responses = await asyncio.wait_for(
                self.twitch.gql_request(
                    [
                        GQL_QUERIES["GetStreamInfo"].with_variables({"channel": login})
                        for login in logins
                    ]
                ),
                REQUEST_TIMEOUT,
            )
        except (ExitRequest, ReloadRequest):
            raise
        except (RequestException, asyncio.TimeoutError):
            logger.warning(
                "Could not refresh point-farming channels; retrying next minute"
            )
            return []
        result = []
        for login, response in zip(logins, responses):
            try:
                data = response["data"]["user"]
                if data is None:
                    continue
                channel = existing.get(login)
                if channel is None:
                    channel = Channel(
                        self.twitch,
                        id=data["id"],
                        login=login,
                        display_name=data.get("displayName"),
                    )
                channel.external_update(data, [])
                result.append(channel)
            except (KeyError, TypeError, ValueError):
                # API response bodies and exception strings can contain session data.
                logger.warning(
                    "Could not refresh a point-farming channel; retrying next minute"
                )
        return result

    def status(self, channel):
        if channel.id in self.balances:
            return _("webui", "points", "balance").format(
                channel=channel.name, balance=self.balances[channel.id]
            )
        return _("webui", "points", "farming").format(channel=channel.name)

    async def send_minute(self, channel):
        if not self.active(channel):
            return False
        # Points use the beacon POST pipeline, not the legacy sendSpadeEvents mutation.
        payload = [
            {
                "event": "minute-watched",
                "properties": {
                    **channel._stream._watch_payload[0]["properties"],
                    "client_time": isonow(),
                    "player": "site",
                    "location": "channel",
                },
            }
        ]
        data = b64encode(json_minify(payload).encode("utf8")).decode("ascii")
        async with self.twitch.request(
            "POST", "https://beacon.twitch.tv/track", data={"data": data}
        ) as response:
            return response.status == 204

    async def minute(self, channel):
        if not self.active(channel) or monotonic() - self.last_minute < 60:
            return
        self.last_minute = monotonic()
        try:
            sent = await asyncio.wait_for(self.send_minute(channel), REQUEST_TIMEOUT)
            if not sent:
                logger.warning("Twitch did not accept channel point watch telemetry")
            if not self.active(channel):
                return
            response = await asyncio.wait_for(
                self.twitch.gql_request(
                    GQL_QUERIES["ChannelPointsContext"].with_variables(
                        {"channelLogin": channel._login}
                    )
                ),
                REQUEST_TIMEOUT,
            )
            if not self.active(channel):
                return
            context = response["data"]["community"]["channel"]
            points = context["self"]["communityPoints"]
            balance = points["balance"]
            if type(balance) is int and balance >= 0:
                if self.balances.get(channel.id) != balance:
                    logger.info(
                        "Channel point balance for %s: %d", channel.name, balance
                    )
                self.balances[channel.id] = balance
            claim = points.get("availableClaim")
            if claim and self.active(channel):
                await asyncio.wait_for(
                    self.twitch.gql_request(
                        GQL_QUERIES["ClaimCommunityPoints"].with_variables(
                            {
                                "input": {
                                    "claimID": claim["id"],
                                    "channelID": str(channel.id),
                                }
                            }
                        )
                    ),
                    REQUEST_TIMEOUT,
                )
            if self.active(channel):
                self.twitch.gui.status.update(self.status(channel))
        except (ExitRequest, ReloadRequest):
            raise
        except (
            RequestException,
            asyncio.TimeoutError,
            KeyError,
            TypeError,
            ValueError,
        ):
            logger.warning("Channel point update unavailable; retrying next minute")

    def poll(self):
        twitch = self.twitch
        if (
            not self.enabled
            or twitch.settings.dump
            or not twitch._auth_state._logged_in.is_set()
            or twitch.gui._reload_requested.is_set()
            or twitch._state not in (State.IDLE, State.CHANNEL_SWITCH)
            or twitch._state_change.is_set()
        ):
            return
        now = monotonic()
        if now - self.last_campaign_check >= CAMPAIGN_INTERVAL:
            self.last_campaign_check = self.last_channel_check = now
            twitch.change_state(State.INVENTORY_FETCH)
        elif (
            now - self.last_channel_check >= CHANNEL_INTERVAL
            and not self.drop_available()
        ):
            self.last_channel_check = now
            twitch.change_state(State.CHANNELS_FETCH)

    async def run(self):
        while True:
            await asyncio.sleep(1)
            self.poll()


def install(twitch_cls):
    """Install with the existing WebUI patches, never in the desktop entry point."""
    original_init = twitch_cls.__init__
    original_run = twitch_cls._run
    original_can_watch = twitch_cls.can_watch
    original_priority = twitch_cls.get_priority
    original_watch = twitch_cls.watch
    original_send = Channel.send_watch

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.point_farming = PointFarming(self, original_can_watch)

    async def run(self):
        farmer = self.point_farming
        task = asyncio.create_task(farmer.run())
        try:
            return await original_run(self)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            farmer.balances.clear()
            farmer.last_minute = float("-inf")
            farmer.last_channel_check = farmer.last_campaign_check = monotonic()

    def can_watch(self, channel):
        return original_can_watch(self, channel) or self.point_farming.can_farm(channel)

    def priority(self, channel):
        farmer = self.point_farming
        order = original_priority(self, channel)
        if not farmer.enabled or original_can_watch(self, channel):
            return order
        if channel._login.lower() in farmer.logins:
            return MAX_INT + 1 + farmer.logins.index(channel._login.lower())
        # Retain fallback candidates when the core trims its bounded channel list.
        return MAX_INT + 21 + order

    def watch(self, channel, *, update_status=True):
        original_watch(self, channel, update_status=update_status)
        if self.point_farming.active(channel):
            self.gui.clear_drop()
            self.gui.status.update(self.point_farming.status(channel))

    async def send_watch(channel):
        farmer = getattr(channel._twitch, "point_farming", None)
        if farmer is not None and not channel._twitch.can_watch(channel):
            return False
        succeeded = await original_send(channel)
        if succeeded and farmer is not None:
            await farmer.minute(channel)
        return succeeded

    twitch_cls.__init__ = init
    twitch_cls._run = run
    twitch_cls.can_watch = can_watch
    twitch_cls.get_priority = priority
    twitch_cls.watch = watch
    Channel.send_watch = send_watch
