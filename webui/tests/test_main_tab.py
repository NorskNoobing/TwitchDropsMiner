"""Integration tests for the main tab UI elements."""

from __future__ import annotations

import pytest
from nicegui import app
from nicegui.testing import User


def _manager():
    return app.webui_manager


@pytest.fixture()
def user(user: User) -> User:
    return user


async def test_status_displays_initializing(user: User):
    await user.open("/")
    await user.should_see("Initializing...")


async def test_status_updates(user: User):
    await user.open("/")
    _manager().update_status("Mining drops")
    await user.should_see("Mining drops")


async def test_console_receives_messages(user: User):
    await user.open("/")
    _manager().print("Hello from test")
    await user.should_see("Hello from test")
