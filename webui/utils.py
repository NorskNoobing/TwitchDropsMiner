from __future__ import annotations

import flet as ft
from yarl import URL

from utils import webopen as _webopen


def webopen(url: URL | str) -> None:
    """Open a URL in the system's default web browser."""
    _webopen(url)


def create_link_text(text: str, url: str, theme_colors: dict) -> ft.TextSpan:
    """Create a clickable link text span."""
    return ft.TextSpan(
        text=text,
        style=ft.TextStyle(
            color=theme_colors["link"],
            decoration=ft.TextDecoration.UNDERLINE,
        ),
        on_click=lambda e: webopen(url),
    )


def format_time(hours: int, minutes: int, seconds: int) -> str:
    """Format time as HH:MM:SS string."""
    return f"{hours:>2}:{minutes:02}:{seconds:02}"
