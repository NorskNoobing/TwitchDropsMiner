from __future__ import annotations

from nicegui import ui

from constants import State
from translate import _
from webui.point_farming import parse_channels


class PointsSection:
    def __init__(self, manager):
        self._manager = manager

    def build(self):
        settings = self._manager._twitch.settings
        with (
            ui.card()
            .props("flat bordered")
            .classes("grow shrink basis-60 min-w-0 gap-2")
        ):
            ui.label(_("webui", "points", "title")).classes("font-bold text-sm")
            ui.label(_("webui", "points", "description")).classes("text-xs")
            enabled = ui.switch(
                _("webui", "points", "enabled"), value=settings.point_farming_enabled
            )
            channels = (
                ui.textarea(
                    _("webui", "points", "channels"),
                    value="\n".join(settings.point_farming_channels),
                )
                .classes("w-full")
                .props("rows=5")
            )

            def save():
                try:
                    names = self.apply(bool(enabled.value), channels.value or "")
                except ValueError:
                    ui.notify(_("webui", "points", "invalid"), type="negative")
                    return
                channels.value = "\n".join(names)
                ui.notify(_("webui", "points", "saved"), type="positive")

            ui.button(_("webui", "points", "save"), on_click=save).props("dense")

    def apply(self, enabled: bool, text: str) -> list[str]:
        names = parse_channels(text)
        twitch = self._manager._twitch
        settings = twitch.settings
        settings.point_farming_channels = names
        settings.point_farming_enabled = enabled
        settings.save(force=True)
        # Stop the previous fallback immediately, before async rediscovery.
        watching = twitch.watching_channel.get_with_default(None)
        if watching is not None and not twitch.point_farming.drop_can_watch(
            twitch, watching
        ):
            twitch.stop_watching()
        twitch.gui.channels.clear_selection()
        twitch.change_state(State.GAMES_UPDATE)
        return names
