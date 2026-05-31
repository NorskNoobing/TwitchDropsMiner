"""Integration tests for the websocket status section."""

from __future__ import annotations

import pytest
from nicegui import app
from nicegui.testing import User


def _manager():
    return app.webui_manager


@pytest.fixture()
def user(user: User) -> User:
    return user


async def test_websocket_update_creates_entry(user: User):
    await user.open("/")
    _manager().websockets.update(0, status="Connected", topics=25)
    await user.should_see("Connected")
    await user.should_see("25/50")


async def test_websocket_update_multiple(user: User):
    await user.open("/")
    _manager().websockets.update(0, status="Connected", topics=10)
    _manager().websockets.update(1, status="Connected", topics=20)
    await user.should_see("10/50")
    await user.should_see("20/50")


async def test_websocket_remove(user: User):
    await user.open("/")
    _manager().websockets.update(0, status="Connected", topics=10)
    await user.should_see("Connected")
    _manager().websockets.remove(0)
    await user.should_not_see("Connected")


async def test_websocket_update_status_preserves_topics(user: User):
    await user.open("/")
    _manager().websockets.update(0, status="Connected", topics=10)
    await user.should_see("10/50")
    _manager().websockets.update(0, status="Disconnected")
    await user.should_see("Disconnected")
    await user.should_see("10/50")


async def test_websocket_update_topics_preserves_status(user: User):
    await user.open("/")
    _manager().websockets.update(0, status="Connected", topics=10)
    _manager().websockets.update(0, topics=30)
    await user.should_see("Connected")
    await user.should_see("30/50")


async def test_websocket_update_requires_status_or_topics():
    with pytest.raises(TypeError):
        _manager().websockets.update(0)
