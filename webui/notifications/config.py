from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlparse

from constants import CONFIG_PATH

from .models import DEFAULT_EVENT_TYPES, NotificationEventType


CONFIG_VERSION = 3
DEFAULT_DISCORD_COLOR = 0x237FEB
LEGACY_DEFAULT_DISCORD_COLOR = 0x7D46FF
LEGACY_DEFAULT_EVENTS = {
    NotificationEventType.DROP_CLAIMED.value,
    NotificationEventType.CAMPAIGN_COMPLETED.value,
    NotificationEventType.LOGIN_REQUIRED.value,
    NotificationEventType.MINER_ERROR.value,
}


@dataclass
class NotificationDestination:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Notifications"
    provider: str = "discord"
    enabled: bool = True
    events: list[str] = field(
        default_factory=lambda: sorted(event.value for event in DEFAULT_EVENT_TYPES)
    )
    url: str = ""
    bot_name: str = "Twitch Drops Miner"
    color: int = DEFAULT_DISCORD_COLOR
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_recipients: str = ""

    def handles(self, event_type: NotificationEventType) -> bool:
        return self.enabled and event_type.value in self.events

    def apprise_url(self) -> str:
        if self.provider != "email":
            return self.url.strip()
        scheme = "mailto" if self.smtp_security == "none" else "mailtos"
        query: dict[str, str] = {
            "smtp": self.smtp_host.strip(),
            "to": self.smtp_recipients.strip(),
        }
        if self.smtp_username:
            query["user"] = self.smtp_username
        if self.smtp_password:
            query["pass"] = self.smtp_password
        if self.smtp_from:
            query["from"] = self.smtp_from
        if self.smtp_security == "ssl":
            query["mode"] = "ssl"
        host = quote(self.smtp_host.strip(), safe=".-[]:")
        return f"{scheme}://{host}:{self.smtp_port}?{urlencode(query)}"

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Destination name is required")
        if self.provider == "discord":
            parsed = urlparse(self.url.strip())
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"discord.com", "discordapp.com"}
                or not parsed.path.startswith("/api/webhooks/")
            ):
                raise ValueError("Enter a valid Discord webhook URL")
        elif self.provider == "email":
            if not self.smtp_host.strip() or not self.smtp_recipients.strip():
                raise ValueError("SMTP host and recipients are required")
            if not 1 <= int(self.smtp_port) <= 65535:
                raise ValueError("SMTP port must be between 1 and 65535")
        elif self.provider == "apprise":
            if not self.url.strip() or "://" not in self.url:
                raise ValueError("Enter a valid Apprise URL")
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NotificationDestination":
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in known})


class NotificationConfig:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or CONFIG_PATH / "notifications.json"
        self.destinations: list[NotificationDestination] = []
        self.load_error = ""
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.destinations = [
                NotificationDestination.from_dict(item)
                for item in data.get("destinations", [])
            ]
            version = int(data.get("version", 1))
            if version < 2:
                for destination in self.destinations:
                    if (
                        destination.provider == "discord"
                        and destination.color == LEGACY_DEFAULT_DISCORD_COLOR
                    ):
                        destination.color = DEFAULT_DISCORD_COLOR
            if version < 3:
                for destination in self.destinations:
                    if set(destination.events) == LEGACY_DEFAULT_EVENTS:
                        destination.events = sorted(
                            event.value for event in DEFAULT_EVENT_TYPES
                        )
            if version < CONFIG_VERSION:
                self.save()
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.load_error = f"Unable to load notification settings: {exc}"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CONFIG_VERSION,
            "destinations": [asdict(item) for item in self.destinations],
        }
        handle, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=".notifications-", suffix=".json"
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_path, 0o600)
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def add(self, destination: NotificationDestination) -> None:
        destination.validate()
        self.destinations.append(destination)
        self.save()

    def remove(self, destination_id: str) -> None:
        self.destinations = [
            item for item in self.destinations if item.id != destination_id
        ]
        self.save()

    def get(self, destination_id: str) -> NotificationDestination:
        return next(item for item in self.destinations if item.id == destination_id)
