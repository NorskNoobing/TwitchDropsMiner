# Event handlers and logging handlers for the WebUI
# Contains all callback functions and logging integration

import logging
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webui.manager import WebUIManager


class WebUIOutputHandler(logging.Handler):
    """Logging handler that outputs to the web UI"""

    def __init__(self, output: "WebUIManager"):
        super().__init__()
        self._output = output

    def emit(self, record):
        self._output.print(self.format(record))
        if record.levelno >= logging.ERROR:
            from webui.notifications import NotificationEvent, NotificationEventType

            detail = record.getMessage()
            if record.exc_info:
                detail = "".join(traceback.format_exception(*record.exc_info))[-1000:]
            self._output.notification_service.queue(
                NotificationEvent.simple(
                    NotificationEventType.MINER_ERROR,
                    "Twitch Drops Miner error",
                    detail,
                    f"{record.created}:{record.getMessage()}",
                )
            )
