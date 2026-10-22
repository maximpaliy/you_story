from pathlib import Path

import pytest

from tools.check_architecture import check_project, check_source


def test_real_project() -> None:
    assert check_project(Path(__file__).resolve().parents[1]) == []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("practice/domain/model.py", "from you_story.catalog.infrastructure import tables"),
        ("catalog/application/use_case.py", "import fastapi"),
        ("catalog/public.py", "from you_story.practice.public import Port"),
        ("catalog/infrastructure/model.py", "Table('x', schema='practice')"),
        ("catalog/infrastructure/model.py", "class X:\n __table_args__={'schema':'practice'}"),
        ("catalog/infrastructure/repository.py", "class EntryRepository: pass"),
        ("catalog/infrastructure/query.py", "connection.execute(statement)"),
        ("media/infrastructure/adapter.py", "class Whatever: pass"),
        ("catalog/another_name.py", "scheduler.add_job(handler)"),
        ("reporting/consumer.py", "asyncio.create_task(handler())"),
        ("other/__main__.py", "pass"),
        ("other/run.py", "if __name__ == '__main__': run()"),
        ("delivery/handler.py", "actor = ActorContext(user, tenant)"),
    ],
)
def test_forbidden_mutations(path: str, source: str) -> None:
    assert check_source(path, source)


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("practice/public.py", "from you_story.catalog.public import Port"),
        ("practice/domain/model.py", "from uuid import UUID"),
        ("catalog/infrastructure/tables.py", "Table('entry', schema='catalog')"),
        ("practice/application/use_case.py", "from ...catalog.public import Port"),
    ],
)
def test_allowed_controls(path: str, source: str) -> None:
    assert check_source(path, source) == []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("catalog/infrastructure/model.py", "Table('record', schema=variable)"),
        ("catalog/infrastructure/model.py", "Table('record')"),
        ("delivery/handler.py", "run = connection.execute\nrun(statement)"),
        ("app.py", "import threading\nthreading.Thread(target=handler).start()"),
        ("app.py", "from asyncio import create_task as launch\nlaunch(handler())"),
        ("app.py", "__import__('you_story.catalog.infrastructure')"),
        ("app.py", "from you_story.shared.context import ActorContext as A\nA()"),
    ],
)
def test_independent_review_mutations(path: str, source: str) -> None:
    assert check_source(path, source)


def test_new_private_sql_in_technical_file_is_unregistered() -> None:
    from tools.check_architecture import sql_sites

    original = "def ready():\n connection.execute(text('SELECT 1'))"
    mutation = original + "\n connection.execute(text('SELECT * FROM catalog.entry'))"
    assert sql_sites(original) != sql_sites(mutation)
    assert sql_sites(original) == sql_sites(original)


@pytest.mark.parametrize(
    "source",
    [
        "import os\nos.fork()",
        "import _thread\n_thread.start_new_thread(handler, ())",
    ],
)
def test_unapproved_process_root(source: str) -> None:
    assert check_source("app.py", source)


def test_deployment_descriptor_mutations(tmp_path: Path) -> None:
    from tools.check_architecture import DEPLOYMENT_CHECKSUMS, check_deployment

    root = Path(__file__).resolve().parents[1]
    for path in DEPLOYMENT_CHECKSUMS:
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / path).read_bytes())
    assert check_deployment(tmp_path) == []
    (tmp_path / "compose.yaml").write_text("services:\n  worker:\n    command: python worker.py\n")
    assert check_deployment(tmp_path) == ["unreviewed deployment command/descriptor"]
    (tmp_path / "Dockerfile.worker").write_text("CMD python worker.py")
    assert check_deployment(tmp_path) == ["unregistered deployment descriptor"]


def test_alias_extraction_in_technical_file_changes_registry() -> None:
    from tools.check_architecture import sql_sites

    baseline = "def ready():\n connection.execute(text('SELECT 1'), {'x': actor.tenant_id})"
    mutation = baseline + "\n run=connection.execute\n run(text('SELECT * FROM catalog.entry'))"
    assert sql_sites(baseline) != sql_sites(mutation)
    wrong_bind = baseline.replace("actor.tenant_id", "request.tenant_id")
    assert sql_sites(baseline) != sql_sites(wrong_bind)
