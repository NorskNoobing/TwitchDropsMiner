from __future__ import annotations

from nicegui import ui

from translate import _


class PointsDashboard:
    def __init__(self, manager):
        self._manager = manager

    def build(self):
        with (
            ui.card().props("flat bordered id=tdm-points-card").classes("w-full gap-2")
        ):
            ui.label(_("webui", "points", "dashboard")).classes("font-bold text-sm")
            ui.label(_("webui", "points", "session_note")).classes("text-xs")
            status = ui.label().classes("text-xs")
            columns = [
                {
                    "name": key,
                    "field": key,
                    "label": _("webui", "points", key),
                    "align": "left",
                }
                for key in (
                    "channel",
                    "balance_value",
                    "gained",
                    "bonus_claims",
                    "checked",
                )
            ]
            table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")

            def update():
                farmer = getattr(self._manager._twitch, "point_farming", None)
                rows = farmer.dashboard_rows() if farmer else []
                text = (
                    _("webui", "points", "refresh_failed")
                    if farmer and farmer.refresh_failed
                    else _("webui", "points", "waiting_balance")
                    if not rows
                    else _("webui", "points", "auto_bonus")
                )
                status.set_text(text)
                if table.rows != rows:
                    table.rows = rows
                    table.update()

            update()
            ui.timer(1, update)
