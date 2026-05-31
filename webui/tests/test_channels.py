"""Integration tests for the channel list UI."""

from __future__ import annotations

import pytest
from nicegui import app
from nicegui.testing import User

from webui.tests.mocks import make_mock_channel


def _manager():
    return app.webui_manager


def _section():
    return _manager().main_panel._channels_section


def _table_rows(user: User):
    tables = _section()._channel_tables
    if not tables:
        return []
    with user._client:
        return tables[0].rows


@pytest.fixture()
def user(user: User) -> User:
    return user


async def test_add_channel_populates_table(user: User):
    await user.open("/")
    ch = make_mock_channel(name="lirik", game="Rust", iid="ch1")
    _manager().channels.display(ch, add=True)
    rows = _table_rows(user)
    assert any(r["channel"] == "lirik" and r["game"] == "Rust" for r in rows)


async def test_add_multiple_channels(user: User):
    await user.open("/")
    ch1 = make_mock_channel(name="lirik", game="Rust", iid="ch1")
    ch2 = make_mock_channel(name="summit1g", game="CS2", iid="ch2")
    _manager().channels.display(ch1, add=True)
    _manager().channels.display(ch2, add=True)
    rows = _table_rows(user)
    names = [r["channel"] for r in rows]
    assert "lirik" in names
    assert "summit1g" in names


async def test_remove_channel(user: User):
    await user.open("/")
    ch = make_mock_channel(name="lirik", iid="ch1")
    _manager().channels.display(ch, add=True)
    assert any(r["channel"] == "lirik" for r in _table_rows(user))
    _manager().channels.remove(ch)
    assert not any(r["channel"] == "lirik" for r in _table_rows(user))


async def test_clear_channels(user: User):
    await user.open("/")
    ch1 = make_mock_channel(name="lirik", iid="ch1")
    ch2 = make_mock_channel(name="summit1g", iid="ch2")
    _manager().channels.display(ch1, add=True)
    _manager().channels.display(ch2, add=True)
    assert len(_table_rows(user)) == 2
    _manager().channels.clear()
    assert len(_table_rows(user)) == 0


async def test_watching_channel_has_arrow(user: User):
    await user.open("/")
    ch = make_mock_channel(name="lirik", iid="ch1")
    _manager().channels.display(ch, add=True)
    _manager().channels.set_watching(ch)
    rows = _table_rows(user)
    assert any("▶" in r["channel"] and "lirik" in r["channel"] for r in rows)


async def test_clear_watching_removes_arrow(user: User):
    await user.open("/")
    ch = make_mock_channel(name="lirik", iid="ch1")
    _manager().channels.display(ch, add=True)
    _manager().channels.set_watching(ch)
    assert any("▶" in r["channel"] for r in _table_rows(user))
    _manager().channels.clear_watching()
    assert not any("▶" in r["channel"] for r in _table_rows(user))


async def test_display_update_existing_channel(user: User):
    await user.open("/")
    ch = make_mock_channel(name="lirik", game="Rust", iid="ch1")
    _manager().channels.display(ch, add=True)
    assert any(r["game"] == "Rust" for r in _table_rows(user))
    ch.game = "NewGame"
    _manager().channels.display(ch, add=False)
    assert any(r["game"] == "NewGame" for r in _table_rows(user))


async def test_display_without_add_ignores_unknown_channel(user: User):
    await user.open("/")
    ch = make_mock_channel(name="unknown", iid="ch_unknown")
    _manager().channels.display(ch, add=False)
    assert len(_table_rows(user)) == 0


async def test_offline_channel_status(user: User):
    await user.open("/")
    ch = make_mock_channel(name="offline_ch", iid="ch_off", online=False)
    _manager().channels.display(ch, add=True)
    rows = _table_rows(user)
    assert any("OFFLINE" in r["status"] for r in rows)


async def test_drops_enabled_shows_check(user: User):
    await user.open("/")
    ch = make_mock_channel(name="drops_ch", iid="ch_d", drops_enabled=True)
    _manager().channels.display(ch, add=True)
    rows = _table_rows(user)
    assert any(r["drops"] == "✔" for r in rows)


async def test_drops_disabled_shows_x(user: User):
    await user.open("/")
    ch = make_mock_channel(name="nodrops_ch", iid="ch_nd", drops_enabled=False)
    _manager().channels.display(ch, add=True)
    rows = _table_rows(user)
    assert any(r["drops"] == "❌" for r in rows)


async def test_remove_watching_channel_clears_watching(user: User):
    await user.open("/")
    ch = make_mock_channel(name="lirik", iid="ch_rw")
    _manager().channels.display(ch, add=True)
    _manager().channels.set_watching(ch)
    _manager().channels.remove(ch)
    rows = _table_rows(user)
    assert not any(r["channel"] == "lirik" for r in rows)
    assert _section()._watching_channel_iid is None
