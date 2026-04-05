"""Shared helpers for opening project documentation from the GUI."""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class DocumentationLink:
    """Menu metadata for one documentation destination."""

    label: str
    relative_path: str


DOCUMENTATION_LINKS: tuple[DocumentationLink, ...] = (
    DocumentationLink("Quickstart", "docs/quickstart.md"),
    DocumentationLink("User Guide", "docs/user-guide.md"),
    DocumentationLink("Which Tool When", "docs/which-tool-when.md"),
    DocumentationLink("Analysis Methods", "docs/analysis-methods.md"),
    DocumentationLink("Technical Overview", "docs/technical-overview.md"),
    DocumentationLink("Open Docs Folder", "docs"),
)


def resolve_documentation_path(relative_path: str) -> Path:
    """Resolve a documentation path relative to the repository root."""

    return Path(__file__).resolve().parent / relative_path


def open_documentation_path(relative_path: str) -> Path:
    """Open a documentation file or directory with the OS default handler."""

    target_path = resolve_documentation_path(relative_path).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"Documentation target not found: {target_path}")

    if sys.platform.startswith("win"):
        os.startfile(str(target_path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target_path)])
    else:
        subprocess.Popen(["xdg-open", str(target_path)])
    return target_path