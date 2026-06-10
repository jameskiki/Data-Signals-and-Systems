"""Tests for shared.base_app_shell.BaseAppShell."""

from shared.base_app_shell import BaseAppShell
from shared import base_app_shell


class DummyVar:
    """Simple variable mock that records trace_add registrations."""

    def __init__(self):
        self.calls = []

    def trace_add(self, mode, handler):
        self.calls.append((mode, handler))


def test_error_dialog_marks_failed_on_exception(monkeypatch):
    shell = BaseAppShell()
    shown = []
    monkeypatch.setattr(base_app_shell.messagebox, "showerror", lambda title, msg: shown.append((title, msg)))

    with shell._error_dialog("Operation Error") as failed:
        raise ValueError("invalid value")

    assert len(shown) == 1
    assert shown[0][0] == "Operation Error"
    assert "invalid value" in shown[0][1]
    assert len(failed) == 1
    assert isinstance(failed[0], ValueError)


def test_error_dialog_no_exception_keeps_failed_empty(monkeypatch):
    shell = BaseAppShell()
    shown = []
    monkeypatch.setattr(base_app_shell.messagebox, "showerror", lambda title, msg: shown.append((title, msg)))

    with shell._error_dialog("Operation Error") as failed:
        _ = 1 + 1

    assert failed == []
    assert shown == []


def test_bind_write_registers_handler_for_all_vars():
    shell = BaseAppShell()
    var_a = DummyVar()
    var_b = DummyVar()

    def _handler(*_args):
        return None

    shell._bind_write(_handler, var_a, var_b)

    assert var_a.calls == [("write", _handler)]
    assert var_b.calls == [("write", _handler)]
