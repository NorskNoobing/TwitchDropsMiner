"""NiceGUI test entry point for WebUI integration tests.

This file is loaded by the NiceGUI pytest plugin via ``runpy.run_path``
as the ``main_file``. It creates a WebUIManager backed by a mock Twitch
object and registers the ``/`` page handler.

Test files should NOT import this module — use ``webui.tests.mocks`` for
factories and access the manager via ``nicegui.app`` at runtime.
"""

from __future__ import annotations

import types
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.argv[0] = str(PROJECT_ROOT / "main_webui.py")

_ws_stub = types.ModuleType("websocket")
_ws_stub.__path__ = []
_ws_stub.__file__ = "<websocket stub for testing>"
sys.modules.setdefault("websocket", _ws_stub)

from webui.tests.mocks import make_mock_twitch
from webui.manager import WebUIManager
from nicegui import ui

mock_twitch = make_mock_twitch()
manager = WebUIManager(mock_twitch)

from nicegui import app as _app
_app.webui_manager = manager

ui.run(title="Twitch Drops Miner", show=False, reload=False)
