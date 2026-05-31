"""Root conftest — must run before any plugin that transitively imports websocket.

The project's ``websocket.py`` shadows the ``websocket`` pip package that
python-engineio (a NiceGUI dependency) imports at module level.  Pre-seeding
sys.modules with a stub prevents the collision.

This conftest also registers the NiceGUI user testing plugin. We cannot use
``addopts = -p nicegui.testing.user_plugin`` in pytest.ini because that
triggers the import before any conftest runs.
"""

from __future__ import annotations

import types
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

_ws_stub = types.ModuleType("websocket")
_ws_stub.__path__ = []
_ws_stub.__file__ = "<websocket stub for testing>"
sys.modules.setdefault("websocket", _ws_stub)

sys.argv[0] = str(PROJECT_ROOT / "main_webui.py")


def pytest_configure(config):
    config.pluginmanager.import_plugin("nicegui.testing.user_plugin")
