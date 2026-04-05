"""Shared helpers for opening project help targets from the GUI."""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
import webbrowser


@dataclass(frozen=True)
class DocumentationLink:
    """Menu metadata for one help destination."""

    label: str
    relative_path: str


DOCUMENTATION_LINKS: tuple[DocumentationLink, ...] = (
    DocumentationLink("Open GitHub Repository", "https://github.com/jameskiki/Data-Signals-and-Systems"),
)


def _is_web_url(target: str) -> bool:
    parsed_target = urlparse(target)
    return parsed_target.scheme in {"http", "https"} and bool(parsed_target.netloc)


def resolve_documentation_path(relative_path: str) -> Path:
    """Resolve a documentation path relative to the repository root."""

    return Path(__file__).resolve().parent / relative_path


def open_documentation_path(relative_path: str) -> Path:
    """Open a help target with the OS default handler."""

    if _is_web_url(relative_path):
        webbrowser.open(relative_path, new=2)
        return Path(relative_path)

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