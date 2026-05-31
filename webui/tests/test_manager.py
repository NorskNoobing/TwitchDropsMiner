"""Integration tests for WebUIManager top-level methods."""

from __future__ import annotations

import asyncio

import pytest
from nicegui import app
from nicegui.testing import User


def _manager():
    return app.webui_manager


@pytest.fixture()
def user(user: User) -> User:
    return user


async def test_close_sets_close_requested_and_calls_twitch_close(user: User):
    await user.open("/")
    m = _manager()
    m._close_requested.clear()
    m._twitch.close.reset_mock()
    m.close()
    assert m.close_requested is True
    m._twitch.close.assert_called_once()
    m._close_requested.clear()


async def test_prevent_close_clears_close_requested(user: User):
    await user.open("/")
    m = _manager()
    m._close_requested.set()
    m.prevent_close()
    assert m.close_requested is False


async def test_coro_unless_closed_raises_exit_on_close(user: User):
    from exceptions import ExitRequest

    await user.open("/")
    m = _manager()
    m._close_requested.clear()
    m._reload_requested.clear()

    async def never_resolves():
        await asyncio.Event().wait()

    task = asyncio.create_task(m.coro_unless_closed(never_resolves()))
    await asyncio.sleep(0.05)
    m._close_requested.set()
    with pytest.raises(ExitRequest):
        await asyncio.wait_for(task, timeout=2.0)
    m._close_requested.clear()


async def test_coro_unless_closed_raises_reload_on_reload(user: User):
    from exceptions import ReloadRequest

    await user.open("/")
    m = _manager()
    m._close_requested.clear()
    m._reload_requested.clear()

    async def never_resolves():
        await asyncio.Event().wait()

    task = asyncio.create_task(m.coro_unless_closed(never_resolves()))
    await asyncio.sleep(0.05)
    m._reload_requested.set()
    with pytest.raises(ReloadRequest):
        await asyncio.wait_for(task, timeout=2.0)
    assert not m._reload_requested.is_set()


async def test_coro_unless_closed_returns_result(user: User):
    await user.open("/")
    m = _manager()
    m._close_requested.clear()
    m._reload_requested.clear()

    async def returns_42():
        return 42

    result = await m.coro_unless_closed(returns_42())
    assert result == 42


async def test_set_dark_mode_calls_save_with_force(user: User):
    await user.open("/")
    m = _manager()
    original_save = m._twitch.settings.save
    saved = {}
    def _track_save(*, force=False):
        saved["force"] = force
    m._twitch.settings.save = _track_save
    try:
        m.set_dark_mode(True)
        assert saved["force"] is True
        assert m._twitch.settings.dark_mode is True
    finally:
        m._twitch.settings.save = original_save
