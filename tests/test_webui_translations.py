"""Tests for webui/translations.py.

Verifies that fork-specific translation keys are merged into the Translator
and that language switching with webui/lang/<language>.json overrides works
without corrupting default_translation.
"""

from __future__ import annotations

import json

import pytest

import webui.translations  # noqa: side effects
from translate import _, default_translation


@pytest.fixture
def restore_english():
    """Ensure the Translator is back to English after the test."""
    yield
    _.set_language("English")


@pytest.mark.parametrize(
    "path,expected",
    [
        (("webui", "help", "about"), "About"),
        (("webui", "login", "logout"), "Logout"),
        (("webui", "status", "name"), "Status:"),
        (
            ("webui", "settings", "advanced", "priority_link_override"),
            "Mine unlinked games from the Priority List: ",
        ),
        (("webui", "auth", "username"), "Username"),
        (("webui", "inventory", "no_campaigns"), "No campaigns match the current filters."),
        (("webui", "game_list", "cancel"), "Cancel"),
    ],
    ids=lambda p: ".".join(p) if isinstance(p, tuple) else str(p),
)
def test_webui_key(path: tuple[str, ...], expected: str):
    """Fork keys are merged into the live Translator at import time."""
    assert _(*path) == expected


@pytest.mark.usefixtures("restore_english")
@pytest.mark.parametrize(
    "language",
    ["Deutsch", "Français", "Polski"],
)
def test_webui_keys_fallback_without_override(language: str):
    """Fork keys fall back to English when the language has no webui/lang/ file."""
    _.set_language(language)
    assert _("webui", "help", "about") == "About"
    assert _("webui", "login", "logout") == "Logout"
    assert _("webui", "status", "name") == "Status:"


@pytest.mark.usefixtures("restore_english")
def test_override_applied_on_language_switch(tmp_path, monkeypatch):
    """A webui/lang/<language>.json override is applied on set_language."""
    import webui.translations as wt

    monkeypatch.setattr(wt, "_WEBUI_LANG_DIR", tmp_path)
    (tmp_path / "Deutsch.json").write_text(
        json.dumps({"webui": {"help": {"about": "Über"}}}),
        encoding="utf-8",
    )

    _.set_language("Deutsch")
    assert _("webui", "help", "about") == "Über"
    # Non-overridden keys still fall back to English
    assert _("webui", "login", "logout") == "Logout"


@pytest.mark.usefixtures("restore_english")
def test_override_doesnt_corrupt_default_translation(tmp_path, monkeypatch):
    """A non-English webui/lang/ override must not mutate default_translation."""
    import webui.translations as wt

    monkeypatch.setattr(wt, "_WEBUI_LANG_DIR", tmp_path)
    (tmp_path / "Deutsch.json").write_text(
        json.dumps({"webui": {"help": {"about": "Über"}}}),
        encoding="utf-8",
    )

    assert default_translation["webui"]["help"]["about"] == "About"

    _.set_language("Deutsch")
    assert _("webui", "help", "about") == "Über"

    _.set_language("English")
    assert default_translation["webui"]["help"]["about"] == "About"
    assert _("webui", "help", "about") == "About"
