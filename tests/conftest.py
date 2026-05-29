"""
Conftest for TwitchDropsMiner tests.

Fixes two import-time issues that break when running under pytest:

1. Module name collision: the project's websocket.py shadows the ``websocket``
   pip package that python-engineio (a NiceGUI dependency) tries to import at
   module level.  When ``engineio.client`` does ``import websocket``, it finds
   the project file, which cascades into translate.py → constants.py and tries
   to write files to the wrong directory.  We pre-seed sys.modules with a
   lightweight stub so the project file is never triggered through that path.

2. Path resolution: constants.py derives WORKING_DIR from sys.argv[0], which
   may not point to the project directory at test time.  We patch it so the
   project root is used instead.
"""

from __future__ import annotations

import types
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Fix 1: websocket module collision ----------------------------------------
_ws_stub = types.ModuleType("websocket")
_ws_stub.__path__ = []
_ws_stub.__file__ = "<websocket stub for testing>"
sys.modules.setdefault("websocket", _ws_stub)

# --- Fix 2: Path resolution ---------------------------------------------------
# constants.py uses sys.argv[0] to compute SELF_PATH / WORKING_DIR / LANG_PATH.
# Under pytest, sys.argv[0] may be the python interpreter itself (not the
# project entry point), which makes translate.py try writing language files
# to the wrong directory.  Unconditionally override to the project root.
sys.argv[0] = str(PROJECT_ROOT / "main_webui.py")

# ---------------------------------------------------------------------------
# Shared helpers and fixtures
# ---------------------------------------------------------------------------

_webui_manager_cls = None


def _import_webui_manager():
    global _webui_manager_cls
    if _webui_manager_cls is not None:
        return _webui_manager_cls
    from webui.manager import WebUIManager
    _webui_manager_cls = WebUIManager
    return WebUIManager


def make_mock_twitch():
    twitch = MagicMock()
    twitch.settings.dark_mode = False
    twitch.settings.tray_notifications = False
    twitch.settings.stdlog = False
    twitch.settings.language = "en"
    twitch.state_change = MagicMock(return_value=MagicMock())
    twitch._session = None
    return twitch


@pytest.fixture()
def webui_manager():
    WebUIManager = _import_webui_manager()
    twitch = make_mock_twitch()
    manager = WebUIManager(twitch)
    yield manager
    try:
        from nicegui import app
        app.routes.clear()
    except Exception:
        pass


@pytest.fixture()
def nicegui_loop(monkeypatch):
    """Stub NiceGUI background task creation so @ui.refreshable works without a running server.

    @ui.refreshable.refresh() calls background_tasks.create() which asserts core.loop
    is not None.  In tests there is no NiceGUI server, but the state update always
    happens *before* the refresh call, so stubbing create() out is sufficient.
    """
    import nicegui.background_tasks as _bt

    def _noop_create(awaitable=None, *, coroutine=None, **kw):
        # Close the coroutine immediately to prevent "never awaited" warnings.
        coro = awaitable or coroutine
        if coro is not None and hasattr(coro, "close"):
            coro.close()

    monkeypatch.setattr(_bt, "create", _noop_create)
