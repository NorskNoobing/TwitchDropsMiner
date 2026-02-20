from __future__ import annotations

from typing import TypedDict


class ThemeColors(TypedDict):
    bg: str
    fg: str
    sel_bg: str
    sel_fg: str
    link: str
    surface: str
    header: str
    fieldbg: str
    border: str
    muted: str
    accent: str


DARK_THEME: ThemeColors = {
    "bg": "#1e1e1e",
    "fg": "#e6e6e6",
    "sel_bg": "#094771",
    "sel_fg": "#ffffff",
    "link": "#4ea3ff",
    "surface": "#252525",
    "header": "#2a2a2a",
    "fieldbg": "#2b2b2b",
    "border": "#3c3c3c",
    "muted": "#b3b3b3",
    "accent": "#0d99ff",
}

LIGHT_THEME: ThemeColors = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "sel_bg": "#cce5ff",
    "sel_fg": "#000000",
    "link": "blue",
    "surface": "#ffffff",
    "header": "#eeeeee",
    "fieldbg": "#ffffff",
    "border": "#cccccc",
    "muted": "#404040",
    "accent": "#0a84ff",
}


def get_theme(dark: bool = True) -> ThemeColors:
    """Get the appropriate theme colors based on the dark mode setting."""
    return DARK_THEME if dark else LIGHT_THEME
