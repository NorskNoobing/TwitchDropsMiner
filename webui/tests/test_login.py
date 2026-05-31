"""Integration tests for the login section UI."""

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


async def test_login_button_visible_when_required(user: User):
    await user.open("/")
    from translate import _
    _manager().login.update(_("gui", "login", "required"), None)
    await user.should_see(_("gui", "login", "button"))


async def test_logout_button_visible_when_logged_in(user: User):
    await user.open("/")
    _manager().login.update("Logged in", 12345)
    await user.should_see("Logout")


async def test_logout_button_calls_manager_logout(user: User):
    await user.open("/")
    _manager().login.update("Logged in", 12345)
    await user.should_see("Logout")

    called = False
    original_logout = _manager().logout

    def _mock_logout():
        nonlocal called
        called = True
        _manager().channels.clear()

    _manager().logout = _mock_logout
    try:
        user.find("Logout").click()
        await asyncio.sleep(0.1)
        assert called
    finally:
        _manager().logout = original_logout


async def test_login_state_shows_user_id(user: User):
    await user.open("/")
    _manager().login.update("Logged in", 99999)
    await user.should_see("99999")


async def test_login_state_shows_dash_for_no_user(user: User):
    await user.open("/")
    from translate import _
    _manager().login.update(_("gui", "login", "required"), None)
    await user.should_see("-")


async def test_login_state_transitions_to_required(user: User):
    await user.open("/")
    from translate import _
    _manager().login.update(_("gui", "login", "required"), None)
    section = _manager().main_panel._login_section
    assert section._login_state == "required"


async def test_ask_enter_code_stores_url():
    from yarl import URL

    m = _manager()
    url = URL("https://twitch.tv/activate")
    m.login.page_url = None
    m.login._confirm.clear()
    m.login._manager.grab_attention = lambda **kw: None
    m.login._manager.print = lambda msg: None

    async def _ask():
        await m.login.ask_enter_code(url, "ABCD-1234")

    task = asyncio.create_task(_ask())
    await asyncio.sleep(0.05)
    assert m.login.page_url == url
    m.login.confirm()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except Exception:
        task.cancel()
