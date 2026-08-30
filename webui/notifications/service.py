from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Callable

import aiohttp
import apprise

from .config import NotificationConfig, NotificationDestination
from .discord import send_discord
from .models import DeliveryAttempt, NotificationEvent, NotificationEventType

logger = logging.getLogger("TwitchDropsNotifications")


class NotificationService:
    def __init__(self, config: NotificationConfig | None = None) -> None:
        self.config = config or NotificationConfig()
        self.history: deque[DeliveryAttempt] = deque(maxlen=20)
        self._seen: deque[str] = deque(maxlen=256)
        self._seen_set: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._subscribers: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> None:
        self._subscribers.append(callback)

    def queue(self, event: NotificationEvent, *, force: bool = False) -> None:
        if not force and event.deduplication_key in self._seen_set:
            return
        if not force:
            if len(self._seen) == self._seen.maxlen:
                self._seen_set.discard(self._seen[0])
            self._seen.append(event.deduplication_key)
            self._seen_set.add(event.deduplication_key)
        try:
            task = asyncio.create_task(self.send(event, force=force))
        except RuntimeError:
            logger.warning("Notification skipped because no event loop is running")
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def check_for_updates(self, current_version: str) -> None:
        if not any(
            item.handles(NotificationEventType.UPDATE_AVAILABLE)
            for item in self.config.destinations
        ):
            return
        try:
            task = asyncio.create_task(self._check_for_updates(current_version))
        except RuntimeError:
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _check_for_updates(self, current_version: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.github.com/repos/NorskNoobing/TwitchDropsMiner/releases/latest",
                    headers={"Accept": "application/vnd.github+json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        return
                    latest = str((await response.json()).get("tag_name", "")).lstrip("v")
            current = current_version.lstrip("v")
            if latest and latest != current:
                self.queue(
                    NotificationEvent.simple(
                        NotificationEventType.UPDATE_AVAILABLE,
                        "Twitch Drops Miner update available",
                        f"Version {latest} is available; this container is running {current}.",
                        latest,
                    )
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            logger.debug("Unable to check for notification-enabled updates")

    async def send(self, event: NotificationEvent, *, force: bool = False) -> None:
        destinations = [
            item
            for item in self.config.destinations
            if item.enabled and (force or item.handles(event.event_type))
        ]
        if not destinations:
            return
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                *(self._deliver(event, item, session) for item in destinations)
            )

    async def _deliver(
        self,
        event: NotificationEvent,
        destination: NotificationDestination,
        session: aiohttp.ClientSession,
    ) -> None:
        last_error = "Unknown delivery error"
        for attempt, delay in enumerate((0, 1, 2, 4)):
            if delay:
                await asyncio.sleep(delay)
            try:
                if destination.provider == "discord":
                    await send_discord(event, destination, session)
                else:
                    await self._send_apprise(event, destination)
                self._record(event, destination, True, "Delivered")
                return
            except Exception as exc:
                last_error = self._sanitize_error(str(exc), destination)
                logger.warning(
                    "Notification delivery attempt %s failed for %s: %s",
                    attempt + 1,
                    destination.name,
                    last_error,
                )
        self._record(event, destination, False, last_error)

    @staticmethod
    async def _send_apprise(
        event: NotificationEvent, destination: NotificationDestination
    ) -> None:
        client = apprise.Apprise()
        if not client.add(destination.apprise_url()):
            raise ValueError("Apprise rejected the destination URL")
        attachment = next(
            (benefit.image_url for benefit in event.benefits if benefit.image_url),
            None,
        )
        result = await client.async_notify(
            title=event.title,
            body=event.message,
            attach=attachment,
        )
        if not result:
            raise RuntimeError("Apprise did not deliver the notification")

    def _record(
        self,
        event: NotificationEvent,
        destination: NotificationDestination,
        success: bool,
        detail: str,
    ) -> None:
        self.history.appendleft(
            DeliveryAttempt(
                datetime.now(timezone.utc),
                event.event_type,
                destination.name,
                success,
                detail,
            )
        )
        for callback in list(self._subscribers):
            callback()

    @staticmethod
    def _sanitize_error(detail: str, destination: NotificationDestination) -> str:
        secrets = (
            destination.url,
            destination.smtp_password,
            destination.smtp_username,
        )
        for secret in secrets:
            if secret:
                detail = detail.replace(secret, "[redacted]")
        return detail[:300]

    def send_test(self, destination_id: str, inventory) -> bool:
        destination = self.config.get(destination_id)
        sample_drop = next(
            (
                drop
                for campaign in inventory
                for drop in campaign.drops
                if drop.benefits
            ),
            None,
        )
        if sample_drop is None:
            return False
        test_event = NotificationEvent.from_claimed_drop(sample_drop)
        try:
            task = asyncio.create_task(self._send_test(test_event, destination))
        except RuntimeError:
            logger.warning("Test notification skipped because no event loop is running")
            return False
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return True

    async def _send_test(
        self, event: NotificationEvent, destination: NotificationDestination
    ) -> None:
        async with aiohttp.ClientSession() as session:
            await self._deliver(event, destination, session)
