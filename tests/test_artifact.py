import json
import zipfile
from pathlib import Path

from tools.check_architecture import EXPECTED_COMPOSITION
from tools.check_artifact import check_wheel


def test_packaged_execution_root_mutation(tmp_path: Path) -> None:
    wheel = tmp_path / "mutation.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("you_story/something/__main__.py", "pass")
    assert "unregistered executable module" in check_wheel(wheel)


def test_packaged_entrypoint_mutation(tmp_path: Path) -> None:
    wheel = tmp_path / "mutation.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("x.dist-info/entry_points.txt", "[console_scripts]\na = a:run\n")
    assert "unregistered wheel entry points" in check_wheel(wheel)


def test_valid_package_control(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "__init__.py").write_text('"""Foundation."""')
    (source / "composition.json").write_text(json.dumps(EXPECTED_COMPOSITION))
    wheel = tmp_path / "control.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for file in source.iterdir():
            archive.writestr("you_story/" + file.name, file.read_bytes())
    assert check_wheel(wheel, source) == []


def test_payload_and_composition_mutations(tmp_path: Path) -> None:
    wheel = tmp_path / "mutation.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("you_story/sneaky.so", b"foreign executable")
        archive.writestr("you_story/composition.json", "{}")
    errors = check_wheel(wheel)
    assert "unregistered wheel payload" in errors
    assert "unapproved/missing wheel composition" in errors
    assert "wheel differs from reviewed source inventory/bytes" in errors
