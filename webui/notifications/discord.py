from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp

from .config import NotificationDestination
from .models import NotificationEvent


def build_discord_payload(
    event: NotificationEvent, destination: NotificationDestination
) -> dict:
    benefits = event.benefits or ()
    if benefits:
        embeds = []
        for benefit in benefits[:10]:
            embed = {
                "title": event.title,
                "description": benefit.name,
                "url": event.link_url,
                "color": destination.color,
                "timestamp": event.created_at.isoformat(),
                "fields": [
                    {
                        "name": "Campaign",
                        "value": event.campaign_name or "Unknown campaign",
                        "inline": False,
                    }
                ],
            }
            if benefit.image_url:
                embed["image"] = {"url": benefit.image_url}
            if event.game_image_url:
                embed["thumbnail"] = {"url": event.game_image_url}
            embeds.append(embed)
    else:
        embed = {
            "title": event.title,
            "description": event.message,
            "color": destination.color,
            "timestamp": event.created_at.isoformat(),
        }
        if event.game_image_url:
            embed["thumbnail"] = {"url": event.game_image_url}
        embeds = [embed]
    return {"username": destination.bot_name, "embeds": embeds}


async def send_discord(
    event: NotificationEvent,
    destination: NotificationDestination,
    session: aiohttp.ClientSession,
) -> None:
    parts = urlsplit(destination.url)
    query = dict(parse_qsl(parts.query))
    query["wait"] = "true"
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    async with session.post(
        url,
        json=build_discord_payload(event, destination),
        timeout=aiohttp.ClientTimeout(total=10),
    ) as response:
        if response.status not in (200, 204):
            body = (await response.text())[:200]
            raise RuntimeError(f"Discord returned HTTP {response.status}: {body}")
