"""Integration tests for the settings panel."""

from __future__ import annotations

import pytest
from nicegui import app
from nicegui.testing import User


def _manager():
    return app.webui_manager


@pytest.fixture()
def user(user: User) -> User:
    return user


def _priority():
    return _manager().settings_panel._priority_section


def _exclude():
    return _manager().settings_panel._exclude_section


def _settings():
    return _manager()._twitch.settings


async def test_priority_add_game(user: User):
    await user.open("/")
    _settings().priority = []
    _priority()._game_names = {"NewGame", "OtherGame"}
    _priority()._do_add("NewGame", None)
    assert _settings().priority == ["NewGame"]


async def test_priority_delete_selected(user: User):
    await user.open("/")
    _settings().priority = ["GameA", "GameB", "GameC"]
    _priority()._game_names = {"GameA", "GameB", "GameC"}
    _priority()._selected = 1
    _priority()._on_delete()
    assert _settings().priority == ["GameA", "GameC"]
    assert _priority()._selected is None


async def test_priority_delete_no_selection_noop(user: User):
    await user.open("/")
    _settings().priority = ["GameA"]
    _priority()._selected = None
    _priority()._on_delete()
    assert _settings().priority == ["GameA"]


async def test_priority_delete_out_of_range_noop(user: User):
    await user.open("/")
    _settings().priority = ["GameA"]
    _priority()._selected = 5
    _priority()._on_delete()
    assert _settings().priority == ["GameA"]


async def test_priority_move_up(user: User):
    await user.open("/")
    _settings().priority = ["A", "B", "C"]
    _priority()._selected = 2
    _priority()._move("up")
    assert _settings().priority == ["A", "C", "B"]
    assert _priority()._selected == 1


async def test_priority_move_down(user: User):
    await user.open("/")
    _settings().priority = ["A", "B", "C"]
    _priority()._selected = 0
    _priority()._move("down")
    assert _settings().priority == ["B", "A", "C"]
    assert _priority()._selected == 1


async def test_priority_move_top(user: User):
    await user.open("/")
    _settings().priority = ["A", "B", "C"]
    _priority()._selected = 2
    _priority()._move("top")
    assert _settings().priority == ["C", "A", "B"]
    assert _priority()._selected == 0


async def test_priority_move_bottom(user: User):
    await user.open("/")
    _settings().priority = ["A", "B", "C"]
    _priority()._selected = 0
    _priority()._move("bottom")
    assert _settings().priority == ["B", "C", "A"]
    assert _priority()._selected == 2


async def test_exclude_delete_selected(user: User):
    await user.open("/")
    _settings().exclude = {"GameA", "GameB"}
    _exclude()._selected = "GameA"
    _exclude()._on_delete()
    assert "GameA" not in _settings().exclude
    assert "GameB" in _settings().exclude
    assert _exclude()._selected is None


def test_correct_game_case():
    s = _manager().settings_panel._priority_section
    s._game_names = {"Fortnite", "Valorant"}
    assert s._correct_game_case("fortnite") == "Fortnite"
    assert s._correct_game_case("VALORANT") == "Valorant"
    assert s._correct_game_case("unknown") == "unknown"


def test_proxy_validation_valid():
    from webui.components.settings.general_section import GeneralSection

    assert GeneralSection._proxy_is_valid("http://user:pass@host:8080") is True
    assert GeneralSection._proxy_is_valid("http://127.0.0.1:8080") is True
    assert GeneralSection._proxy_is_valid("") is True


def test_proxy_validation_invalid():
    from webui.components.settings.general_section import GeneralSection

    assert GeneralSection._proxy_is_valid("not a url at all") is False
    assert GeneralSection._proxy_is_valid("://missing-scheme") is False


async def test_set_games_propagates_to_sections(user: User):
    await user.open("/")
    from unittest.mock import MagicMock

    games = [MagicMock(name="Game1"), MagicMock(name="Game2")]
    for g in games:
        g.name = g._mock_name
    _manager().set_games(games)
    assert "Game1" in _priority()._game_names
    assert "Game2" in _exclude()._game_names
