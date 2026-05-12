"""UI widgets for displaying notifications and status."""

import tkinter as tk
from tkinter import ttk

from shared.notifications import Notification, NotificationManager, NotificationSeverity


class StatusBar(tk.Frame):
    """A status bar that displays current notifications."""

    def __init__(self, parent: tk.Widget, notification_manager: NotificationManager):
        super().__init__(parent, relief=tk.SUNKEN, bg="#f0f0f0", height=25)
        self.notification_manager = notification_manager
        self.pack_propagate(False)

        # Color scheme for severity levels
        self.colors = {
            NotificationSeverity.INFO: "#0d47a1",  # blue
            NotificationSeverity.SUCCESS: "#1b5e20",  # green
            NotificationSeverity.WARNING: "#f57f17",  # orange
            NotificationSeverity.ERROR: "#b71c1c",  # red
        }

        # Create the status display
        self.status_frame = tk.Frame(self, bg="#f0f0f0")
        self.status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        self.status_icon = tk.Label(self.status_frame, text="●", font=("Segoe UI", 10), fg="#0d47a1", bg="#f0f0f0")
        self.status_icon.pack(side=tk.LEFT, padx=(0, 8))

        self.status_text = tk.Label(
            self.status_frame,
            text="Ready",
            font=("Segoe UI", 9),
            fg="#333333",
            bg="#f0f0f0",
            wraplength=600,
            justify=tk.LEFT,
        )
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.status_details = tk.Label(
            self.status_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#666666",
            bg="#f0f0f0",
            wraplength=300,
            justify=tk.RIGHT,
        )
        self.status_details.pack(side=tk.RIGHT, padx=(8, 0))

        # Subscribe to notifications
        notification_manager.subscribe(self._on_notification)
        self._update_display(None)

    def _on_notification(self, notification: Notification | None) -> None:
        """Handle incoming notifications."""
        if notification is None:
            self._show_ready()
        else:
            self._update_display(notification)

    def _update_display(self, notification: Notification | None) -> None:
        """Update the display based on the current notification."""
        if notification is None:
            self._show_ready()
        else:
            severity = notification.severity
            color = self.colors.get(severity, "#0d47a1")

            self.status_icon.config(fg=color)
            self.status_text.config(text=notification.message)

            if notification.details:
                self.status_details.config(text=notification.details)
            else:
                self.status_details.config(text="")

            # Auto-dismiss after the specified time
            if notification.auto_dismiss_ms:
                self.after(notification.auto_dismiss_ms, lambda: self.notification_manager.clear())

    def _show_ready(self) -> None:
        """Show the ready state."""
        self.status_icon.config(fg="#0d47a1")
        self.status_text.config(text="Ready")
        self.status_details.config(text="")
