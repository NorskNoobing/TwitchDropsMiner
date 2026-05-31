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
