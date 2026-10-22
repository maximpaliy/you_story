"""Inspect built wheel contents and executable registrations, not source alone."""

from __future__ import annotations

import configparser
import json
import tempfile
import zipfile
from pathlib import Path

from tools.check_architecture import EXPECTED_COMPOSITION, check_file_inventory, check_source


def check_wheel(wheel: Path, source_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    source_root = source_root or Path(__file__).resolve().parents[1] / "src/you_story"
    expected = {
        "you_story/" + file.relative_to(source_root).as_posix(): file.read_bytes()
        for file in source_root.rglob("*")
        if file.is_file() and file.suffix in {".py", ".sql", ".json"}
    }
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(wheel) as archive:
        target = Path(temp)
        archive.extractall(target)
        metadata_names = {"METADATA", "WHEEL", "RECORD", "top_level.txt"}
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            parts = Path(name).parts
            is_metadata = (
                len(parts) == 2
                and parts[0].startswith("you_story-")
                and (parts[0].endswith(".dist-info") and parts[1] in metadata_names)
            )
            if name not in expected and not is_metadata:
                errors.append("unclassified wheel archive path")
        actual = {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("you_story/") and not name.endswith("/")
        }
        if actual != expected:
            errors.append("wheel differs from reviewed source inventory/bytes")
        for file in target.rglob("*.py"):
            if "you_story" not in file.parts:
                errors.append("unregistered code outside package")
                continue
            relative = Path(*file.parts[file.parts.index("you_story") + 1 :]).as_posix()
            errors.extend(check_source(relative, file.read_text()))
            errors.extend(check_file_inventory(relative, file.read_text()))
        for entries in target.rglob("entry_points.txt"):
            parser = configparser.ConfigParser()
            parser.read(entries)
            if parser.sections():
                errors.append("unregistered wheel entry points")
        composition = target / "you_story/composition.json"
        if not composition.exists() or json.loads(composition.read_text()) != EXPECTED_COMPOSITION:
            errors.append("unapproved/missing wheel composition")
        for file in target.rglob("*"):
            if (
                file.is_file()
                and "you_story" in file.parts
                and file.suffix not in {".py", ".sql", ".json"}
            ):
                errors.append("unregistered wheel payload")
            if ".data" in file.as_posix() and file.is_file():
                errors.append("unregistered executable/data payload")
    return errors


if __name__ == "__main__":
    wheels = list(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Exactly one wheel required")
    errors = check_wheel(wheels[0])
    if errors:
        raise SystemExit("\n".join(errors))
    print("Built wheel composition checks passed")
