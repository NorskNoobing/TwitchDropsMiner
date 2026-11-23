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
UNAVAILABLE_STREAM_RETRY = 300


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
        self.gained: dict[int, int] = {}
        self.bonus_claims: dict[int, int] = {}
        self.channel_names: dict[int, str] = {}
        self.checked_at: dict[int, float] = {}
        self.last_points = float("-inf")
        self.refresh_failed = False
        self._points_lock = asyncio.Lock()
        self.unavailable_streams: dict[int, tuple[int, float]] = {}
        self._claimed_ids: list[tuple[int, str]] = []

    @property
    def logins(self) -> list[str]:
        return self.twitch.settings.point_farming_channels

    @property
    def enabled(self) -> bool:
        return bool(self.twitch.settings.point_farming_enabled and self.logins)

    def stream_available(self, channel) -> bool:
        blocked = self.unavailable_streams.get(channel.id)
        if blocked is None:
            return True
        stream = channel._stream
        if stream is None:
            return False
        if stream.broadcast_id != blocked[0] or monotonic() >= blocked[1]:
            self.unavailable_streams.pop(channel.id, None)
            return True
        return False

    def drop_available(self) -> bool:
        return any(
            self.stream_available(ch) and self.drop_can_watch(self.twitch, ch)
            for ch in self.twitch.channels.values()
        )

    def can_farm(self, channel) -> bool:
        return (
            self.enabled
            and channel.online
            and self.stream_available(channel)
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

    def is_current(self, channel):
        return (
            self.enabled
            and channel.online
            and self.twitch.watching_channel.get_with_default(None) is channel
            and not self.twitch.gui._reload_requested.is_set()
            and self.twitch._state not in (State.EXIT, State.RESTART)
        )

    def record_balance(self, channel, balance):
        if type(balance) is not int or balance < 0:
            raise ValueError("Invalid point balance")
        previous = self.balances.get(channel.id, balance)
        self.gained[channel.id] = self.gained.get(channel.id, 0) + max(
            0, balance - previous
        )
        if self.balances.get(channel.id) != balance:
            logger.info("Channel point balance for %s: %d", channel.name, balance)
        self.balances[channel.id] = balance
        self.channel_names[channel.id] = channel.name
        self.checked_at[channel.id] = monotonic()

    def dashboard_rows(self):
        return [
            {
                "id": cid,
                "channel": self.channel_names[cid],
                "balance_value": f"{balance:,}",
                "gained": f"+{self.gained[cid]:,}",
                "bonus_claims": self.bonus_claims.get(cid, 0),
                "checked": _("webui", "points", "seconds_ago").format(
                    seconds=max(0, int(monotonic() - self.checked_at[cid]))
                ),
            }
            for cid, balance in self.balances.items()
        ]

    async def refresh_points(self, channel):
        async with self._points_lock:
            if not self.is_current(channel) or monotonic() - self.last_points < 60:
                return
            self.last_points = monotonic()
            try:
                response = await asyncio.wait_for(
                    self.twitch.gql_request(
                        GQL_QUERIES["ChannelPointsContext"].with_variables(
                            {"channelLogin": channel._login}
                        )
                    ),
                    REQUEST_TIMEOUT,
                )
                if not self.is_current(channel):
                    return
                points = response["data"]["community"]["channel"]["self"][
                    "communityPoints"
                ]
                self.record_balance(channel, points["balance"])
                self.refresh_failed = False
                claim = points.get("availableClaim")
                claim_key = (channel.id, claim["id"]) if claim else None
                if (
                    claim_key
                    and claim_key not in self._claimed_ids
                    and self.is_current(channel)
                ):
                    result = await asyncio.wait_for(
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
                    if not self.is_current(channel):
                        return
                    claimed = (result.get("data") or {}).get("claimCommunityPoints")
                    # Twitch's ClaimCommunityPointsPayload.currentPoints is an Int.
                    balance = (
                        claimed.get("currentPoints")
                        if isinstance(claimed, dict)
                        else None
                    )
                    if (
                        isinstance(claimed, dict)
                        and claimed.get("error") is None
                        and not result.get("errors")
                        and type(balance) is int
                        and balance >= 0
                    ):
                        self._claimed_ids.append(claim_key)
                        self._claimed_ids = self._claimed_ids[-256:]
                        self.bonus_claims[channel.id] = (
                            self.bonus_claims.get(channel.id, 0) + 1
                        )
                        self.record_balance(channel, balance)
                    else:
                        self.refresh_failed = True
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
                self.refresh_failed = True
                logger.warning("Channel point update unavailable; retrying next minute")

    async def minute(self, channel):
        if not self.active(channel) or monotonic() - self.last_minute < 60:
            return
        self.last_minute = monotonic()
        try:
            sent = await asyncio.wait_for(self.send_minute(channel), REQUEST_TIMEOUT)
            if not sent:
                logger.warning("Twitch did not accept channel point watch telemetry")
        except (ExitRequest, ReloadRequest):
            raise
        except (RequestException, asyncio.TimeoutError):
            logger.warning("Channel point watch telemetry unavailable")
        # Balance reads and bonus claims do not depend on telemetry acceptance.
        await self.refresh_points(channel)

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
            channel = self.twitch.watching_channel.get_with_default(None)
            if channel is not None:
                await self.refresh_points(channel)


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
            farmer.gained.clear()
            farmer.bonus_claims.clear()
            farmer.channel_names.clear()
            farmer.checked_at.clear()
            farmer._claimed_ids.clear()
            farmer.unavailable_streams.clear()
            farmer.last_points = float("-inf")
            farmer.refresh_failed = False
            farmer.last_minute = float("-inf")
            farmer.last_channel_check = farmer.last_campaign_check = monotonic()

    def can_watch(self, channel):
        farmer = self.point_farming
        return farmer.stream_available(channel) and (
            original_can_watch(self, channel) or farmer.can_farm(channel)
        )

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
        stream = channel._stream
        succeeded = await original_send(channel)
        if farmer is not None and stream is not None and stream.playback_unavailable:
            # Discovery can report the ended broadcast as live for several minutes.
            farmer.unavailable_streams[channel.id] = (
                stream.broadcast_id, monotonic() + UNAVAILABLE_STREAM_RETRY
            )
        if succeeded and farmer is not None:
            await farmer.minute(channel)
        return succeeded

    twitch_cls.__init__ = init
    twitch_cls._run = run
    twitch_cls.can_watch = can_watch
    twitch_cls.get_priority = priority
    twitch_cls.watch = watch
    Channel.send_watch = send_watch
