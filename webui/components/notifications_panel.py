from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from nicegui import ui

from translate import _
from webui.notifications import NotificationDestination, NotificationEventType

from .base_panel import BasePanel

if TYPE_CHECKING:
    from webui.manager import WebUIManager


class NotificationsPanel(BasePanel):
    def __init__(self, manager: "WebUIManager") -> None:
        super().__init__(manager)
        manager.notification_service.subscribe(self._refresh)

    @property
    def _config(self):
        return self._manager.notification_service.config

    def build(self) -> None:
        with ui.column().classes("w-full max-w-5xl mx-auto gap-4 p-2"):
            with ui.row().classes("w-full items-center"):
                ui.label(_("webui", "notifications", "title")).classes(
                    "text-h5 font-bold"
                )
                ui.space()
                with ui.button(
                    _("webui", "notifications", "add"), icon="add"
                ).props("unelevated"):
                    with ui.menu():
                        ui.menu_item(
                            "Discord", lambda: self._open_editor(provider="discord")
                        )
                        ui.menu_item(
                            "Email / SMTP", lambda: self._open_editor(provider="email")
                        )
                        ui.menu_item(
                            "Apprise URL", lambda: self._open_editor(provider="apprise")
                        )
            ui.label(_("webui", "notifications", "description")).classes(
                "text-sm text-gray-500"
            )
            if self._config.load_error:
                ui.label(self._config.load_error).classes("text-sm text-negative")
            self._destination_content()
            ui.separator()
            ui.label(_("webui", "notifications", "recent")).classes(
                "text-h6 font-bold"
            )
            self._history_content()

    @ui.refreshable
    def _destination_content(self) -> None:
        if not self._config.destinations:
            ui.label(_("webui", "notifications", "empty")).classes(
                "text-sm text-gray-500 p-4"
            )
            return
        for destination in self._config.destinations:
            with ui.card().props("flat bordered").classes("w-full"):
                with ui.row().classes("w-full items-center"):
                    ui.icon(self._provider_icon(destination.provider)).classes("text-xl")
                    with ui.column().classes("gap-0"):
                        ui.label(destination.name).classes("font-bold")
                        ui.label(destination.provider.title()).classes(
                            "text-xs text-gray-500"
                        )
                    ui.space()
                    ui.switch(
                        value=destination.enabled,
                        on_change=lambda event, item=destination: self._set_enabled(
                            item, event.value
                        ),
                    )
                    ui.button(
                        icon="send",
                        on_click=lambda item=destination: self._test(item),
                    ).props("flat round").tooltip(
                        _("webui", "notifications", "test")
                    )
                    ui.button(
                        icon="edit",
                        on_click=lambda item=destination: self._open_editor(item),
                    ).props("flat round")
                    ui.button(
                        icon="delete",
                        on_click=lambda item=destination: self._delete(item),
                    ).props("flat round color=negative")
                with ui.row().classes("gap-1"):
                    for event_name in destination.events:
                        ui.badge(self._event_label(event_name)).props("outline")

    @ui.refreshable
    def _history_content(self) -> None:
        history = list(self._manager.notification_service.history)
        if not history:
            ui.label(_("webui", "notifications", "no_history")).classes(
                "text-sm text-gray-500"
            )
            return
        rows = [
            {
                "time": item.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                "event": self._event_label(item.event_type.value),
                "destination": item.destination_name,
                "status": "✓" if item.success else "✗",
                "detail": item.detail,
            }
            for item in history
        ]
        ui.table(
            columns=[
                {"name": "time", "label": "Time", "field": "time", "align": "left"},
                {"name": "event", "label": "Event", "field": "event", "align": "left"},
                {
                    "name": "destination",
                    "label": "Destination",
                    "field": "destination",
                    "align": "left",
                },
                {"name": "status", "label": "Status", "field": "status"},
                {
                    "name": "detail",
                    "label": "Detail",
                    "field": "detail",
                    "align": "left",
                },
            ],
            rows=rows,
            row_key="time",
        ).props("flat dense").classes("w-full")

    def _open_editor(
        self,
        destination: NotificationDestination | None = None,
        *,
        provider: str | None = None,
    ) -> None:
        item = replace(destination) if destination else NotificationDestination(
            name=(provider or "apprise").title(), provider=provider or "apprise"
        )
        item.events = list(item.events)
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
            ui.label(
                _("webui", "notifications", "edit")
                if destination
                else _("webui", "notifications", "add")
            ).classes("text-h6 font-bold")
            name_input = ui.input("Name", value=item.name).classes("w-full")
            provider_select = ui.select(
                {"discord": "Discord", "email": "Email / SMTP", "apprise": "Apprise URL"},
                value=item.provider,
                label="Provider",
            ).classes("w-full")
            url_input = ui.input(
                "Discord webhook URL" if item.provider == "discord" else "Apprise URL",
                value="" if destination else item.url,
                password=True,
                password_toggle_button=True,
            ).props("placeholder='Leave blank to keep the saved value'").classes("w-full")
            bot_input = ui.input("Bot name", value=item.bot_name).classes("w-full")
            color_input = ui.input(
                "Embed color", value=f"#{item.color:06x}"
            ).classes("w-full")
            with ui.column().classes("w-full") as email_fields:
                smtp_host = ui.input("SMTP host", value=item.smtp_host).classes("w-full")
                with ui.row().classes("w-full"):
                    smtp_port = ui.number(
                        "SMTP port", value=item.smtp_port, min=1, max=65535
                    ).classes("flex-1")
                    smtp_security = ui.select(
                        {"none": "None", "starttls": "STARTTLS", "ssl": "SSL"},
                        value=item.smtp_security,
                        label="Security",
                    ).classes("flex-1")
                smtp_username = ui.input(
                    "SMTP username", value=item.smtp_username
                ).classes("w-full")
                smtp_password = ui.input(
                    "SMTP password",
                    value="",
                    password=True,
                    password_toggle_button=True,
                ).props("placeholder='Leave blank to keep the saved value'").classes("w-full")
                smtp_from = ui.input("From address", value=item.smtp_from).classes(
                    "w-full"
                )
                smtp_recipients = ui.input(
                    "Recipients (comma separated)", value=item.smtp_recipients
                ).classes("w-full")

            event_select = ui.select(
                {event.value: self._event_label(event.value) for event in NotificationEventType},
                value=item.events,
                label="Events",
                multiple=True,
            ).props("use-chips").classes("w-full")
            error_label = ui.label().classes("text-negative text-sm")

            def update_visibility() -> None:
                selected = provider_select.value
                email_fields.set_visibility(selected == "email")
                url_input.set_visibility(selected in ("discord", "apprise"))
                bot_input.set_visibility(selected == "discord")
                color_input.set_visibility(selected == "discord")

            provider_select.on_value_change(lambda _: update_visibility())
            update_visibility()

            def save() -> None:
                try:
                    item.name = name_input.value.strip()
                    item.provider = provider_select.value
                    if url_input.value.strip() or destination is None:
                        item.url = url_input.value.strip()
                    item.bot_name = bot_input.value.strip() or "Twitch Drops Miner"
                    item.color = int(color_input.value.lstrip("#"), 16)
                    item.events = list(event_select.value or [])
                    item.smtp_host = smtp_host.value.strip()
                    item.smtp_port = int(smtp_port.value)
                    item.smtp_security = smtp_security.value
                    item.smtp_username = smtp_username.value.strip()
                    if smtp_password.value or destination is None:
                        item.smtp_password = smtp_password.value
                    item.smtp_from = smtp_from.value.strip()
                    item.smtp_recipients = smtp_recipients.value.strip()
                    item.validate()
                    if destination is None:
                        self._config.destinations.append(item)
                    else:
                        index = self._config.destinations.index(destination)
                        self._config.destinations[index] = item
                    self._config.save()
                except (ValueError, OSError) as exc:
                    error_label.set_text(str(exc))
                    return
                dialog.close()
                self._destination_content.refresh()

            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save).props("unelevated")
        dialog.open()

    def _set_enabled(
        self, destination: NotificationDestination, enabled: bool
    ) -> None:
        destination.enabled = enabled
        self._config.save()

    def _test(self, destination: NotificationDestination) -> None:
        queued = self._manager.notification_service.send_test(
            destination.id, self._manager._twitch.inventory
        )
        if queued:
            ui.notify(_("webui", "notifications", "test_queued"), type="positive")
        else:
            ui.notify(
                "No campaign with benefit artwork is currently loaded.",
                type="warning",
            )

    def _delete(self, destination: NotificationDestination) -> None:
        self._config.remove(destination.id)
        self._destination_content.refresh()

    def _refresh(self) -> None:
        self._history_content.refresh()

    @staticmethod
    def _provider_icon(provider: str) -> str:
        return {"discord": "forum", "email": "email", "apprise": "notifications"}.get(
            provider, "notifications"
        )

    @staticmethod
    def _event_label(event_name: str) -> str:
        return event_name.replace("_", " ").title()
