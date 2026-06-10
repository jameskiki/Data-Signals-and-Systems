"""Shared notification state and helpers for non-blocking UI feedback."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class NotificationSeverity(Enum):
    """Severity level for notifications."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class Notification:
    """A single notification event."""
    message: str
    severity: NotificationSeverity
    details: Optional[str] = None
    auto_dismiss_ms: Optional[int] = None  # None means stay visible until cleared


class NotificationManager:
    """Manages transient notifications for the app UI."""

    def __init__(self):
        self.current: Optional[Notification] = None
        self.callbacks: list[Callable[[Notification], None]] = []

    def subscribe(self, callback: Callable[[Notification], None]) -> None:
        """Register a callback to be invoked when a notification is posted."""
        self.callbacks.append(callback)

    def post(
        self,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        details: Optional[str] = None,
        auto_dismiss_ms: Optional[int] = None,
    ) -> None:
        """Publish a notification."""
        self.current = Notification(
            message=message,
            severity=severity,
            details=details,
            auto_dismiss_ms=auto_dismiss_ms,
        )
        for callback in self.callbacks:
            callback(self.current)

    def info(self, message: str, details: Optional[str] = None) -> None:
        """Post an info notification."""
        self.post(message, NotificationSeverity.INFO, details, auto_dismiss_ms=5000)

    def success(self, message: str, details: Optional[str] = None) -> None:
        """Post a success notification."""
        self.post(message, NotificationSeverity.SUCCESS, details, auto_dismiss_ms=4000)

    def warning(self, message: str, details: Optional[str] = None) -> None:
        """Post a warning notification."""
        self.post(message, NotificationSeverity.WARNING, details)

    def error(self, message: str, details: Optional[str] = None) -> None:
        """Post an error notification."""
        self.post(message, NotificationSeverity.ERROR, details)

    def clear(self) -> None:
        """Clear the current notification."""
        self.current = None
        for callback in self.callbacks:
            callback(None)  # type: ignore
