"""Cross-platform paths for source, packaged, and test deployments."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve_bundle_dir(source_root: Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return source_root.resolve()


def platform_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        return Path(base) / "TypEng" if base else Path.home() / "AppData" / "Roaming" / "TypEng"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TypEng"
    xdg = os.environ.get("XDG_DATA_HOME", "")
    return Path(xdg) / "TypEng" if xdg else Path.home() / ".local" / "share" / "TypEng"


def migrate_legacy_data(new_data_dir: Path, executable_dir: Path) -> None:
    new_db = new_data_dir / "typeng.db"
    old_data_dir = executable_dir / "data"
    if new_db.exists() or not (old_data_dir / "typeng.db").exists():
        return
    new_data_dir.mkdir(parents=True, exist_ok=True)
    for item in old_data_dir.iterdir():
        destination = new_data_dir / item.name
        if destination.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)
    notice = old_data_dir / "DATA_MOVED.txt"
    if not notice.exists():
        try:
            notice.write_text(
                f"Your TypEng data has been moved to:\n{new_data_dir}\n\n"
                "This folder is no longer used. You can safely delete it.\n",
                encoding="utf-8",
            )
        except OSError:
            pass


def resolve_app_home(source_root: Path) -> Path:
    configured_home = os.environ.get("TYPENG_HOME", "").strip()
    if configured_home:
        return Path(configured_home).resolve()
    if not getattr(sys, "frozen", False):
        return source_root.resolve()
    home = platform_data_dir()
    home.mkdir(parents=True, exist_ok=True)
    migrate_legacy_data(home / "data", Path(sys.executable).resolve().parent)
    return home


def resolve_resource_dir(app_home: Path, bundle_root: Path) -> Path:
    def contains_dictionary(directory: Path) -> bool:
        return any(
            path.is_file()
            for path in (
                directory / "lexicon" / "typeng-lexicon.sqlite3",
                directory / "ecdict.csv",
                directory / "efllex" / "EFLLex.tsv",
                directory / "wiktionary" / "exam-pos-index.tsv",
                directory / "wiktionary" / "kaikki.org-dictionary-English.jsonl",
            )
        )

    if getattr(sys, "frozen", False):
        executable_resources = Path(sys.executable).resolve().parent / "resources"
        if contains_dictionary(executable_resources):
            return executable_resources
    external_resources = app_home / "resources"
    if contains_dictionary(external_resources):
        return external_resources
    return bundle_root / "resources"
