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


@pytest.mark.parametrize(
    "source",
    [
        "object.__new__(ActorContext)",
        "from you_story.shared.context import ActorContext as A\nobject.__new__(A)",
        "from you_story.identity.public import _ACTORS as registry",
        "public._SESSIONS[id(session)] = reference",
        "AuthenticatedSession(actor, 'ready', session_id, expiry, bearer)",
    ],
)
def test_actor_evidence_forgery_sites_rejected(source: str) -> None:
    errors = check_source("delivery/browser.py", source)
    assert errors
    assert any("issuer" in error or "registry" in error for error in errors)


def test_only_exact_identity_issuer_can_construct_evidence() -> None:
    source = "actor = object.__new__(ActorContext)"
    assert check_source("identity/infrastructure/actors.py", source) == []
    assert check_source("identity/infrastructure/other.py", source)


def test_new_behavior_cannot_hide_inside_module_inventory() -> None:
    from tools.check_architecture import check_file_inventory

    assert check_file_inventory("identity/infrastructure/actors.py", "pass") == []
    assert check_file_inventory("identity/infrastructure/admin.py", "pass")
    assert check_file_inventory("practice/public/__init__.py", "def grant(): pass")


@pytest.mark.parametrize(
    "mutation",
    [
        "{{ user_text | safe }}",
        "{% autoescape false %}{{ user_text }}{% endautoescape %}",
        '<img src="x" onerror="run()">',
        '<script nonce="{{ nonce }}">run()</script>',
        "<style>body { color: red }</style>",
        '<p style="color: red">hello</p>',
        '<a href="javascript:run()">hello</a>',
    ],
)
def test_template_sink_mutations(mutation: str) -> None:
    from tools.check_architecture import check_template

    assert check_template("delivery/templates/profile.html", "<p>{{ value }}</p>") == []
    assert check_template("delivery/templates/profile.html", mutation)
    assert check_template("delivery/templates/admin.html", "<p>hello</p>")


def test_registered_private_sql_mutations_are_independent_of_rls(tmp_path: Path) -> None:
    import json

    from tools.check_architecture import REGISTERED_SQL, check_sql_registry, sql_sites

    root = Path(__file__).resolve().parents[1] / "src/you_story"
    for relative in REGISTERED_SQL:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((root / relative).read_text())
    (tmp_path / "technical-sql.json").write_text((root / "technical-sql.json").read_text())
    assert check_sql_registry(tmp_path) == []
    path = tmp_path / "catalog/infrastructure/provisioning.py"
    original = path.read_text()
    for changed in (
        original.replace("actor.tenant_id", "request.tenant_id"),
        original.replace(".where(_catalog.c.tenant_id == tenant)", ""),
        original
        + "\ndef extra(connection):\n connection.execute('SELECT * FROM catalog.catalog')\n",
    ):
        assert changed != original
        path.write_text(changed)
        assert check_sql_registry(tmp_path)
    path.write_text(original)
    adapter = tmp_path / "identity/infrastructure/postgres.py"
    adapter_original = adapter.read_text()
    adapter.write_text(adapter_original.replace("identity.resolve_web_session", "identity.user"))
    assert check_sql_registry(tmp_path), "generic execution helper must cover wrapper call sites"
    adapter.write_text(adapter_original)
    registry = json.loads((tmp_path / "technical-sql.json").read_text())
    registry["catalog/unlisted.py"] = dict(sql_sites("pass"))
    (tmp_path / "technical-sql.json").write_text(json.dumps(registry))
    assert "unclassified reviewed SQL file" in check_sql_registry(tmp_path)


def test_regex_compiler_does_not_open_dynamic_compilation() -> None:
    assert check_source("identity/infrastructure/google.py", "import re\nre.compile('fixed')") == []
    assert check_source("identity/infrastructure/google.py", "compile(source, 'x', 'exec')")
    assert check_source("identity/infrastructure/google.py", "compiler.compile(source)")
    assert check_source(
        "identity/infrastructure/google.py", "from unknown import re\nre.compile(source)"
    )


def test_makefile_cannot_add_unreviewed_execution_root(tmp_path: Path) -> None:
    from tools.check_architecture import DEPLOYMENT_CHECKSUMS, check_deployment

    root = Path(__file__).resolve().parents[1]
    for path in DEPLOYMENT_CHECKSUMS:
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / path).read_bytes())
    assert check_deployment(tmp_path) == []
    with (tmp_path / "Makefile").open("a") as file:
        file.write("\nworker:\n\tpython -m hidden_worker\n")
    assert check_deployment(tmp_path) == ["unreviewed deployment command/descriptor"]


@pytest.mark.parametrize(
    "path",
    [
        "identity/infrastructure/google.py",
        "identity/infrastructure/crypto.py",
        "identity/infrastructure/postgres.py",
        "identity/public/__init__.py",
        "delivery/browser.py",
    ],
)
@pytest.mark.parametrize(
    "source",
    [
        "from you_story.identity.infrastructure.actors import issue_session\n"
        "issue_session(user,tenant,session,'ready',expiry,bearer)",
        "from you_story.identity.infrastructure.actors import issue_session as mint\n"
        "mint(user,tenant,session,'ready',expiry,bearer)",
        "import you_story.identity.infrastructure.actors as actors\n"
        "actors.issue_session(user,tenant,session,'ready',expiry,bearer)",
        "from you_story.identity.infrastructure import actors as evidence\n"
        "mint = evidence.issue_session",
        "from you_story.identity.infrastructure.actors import issue_session as mint\n"
        "register(mint)",
        "from you_story.identity.infrastructure.actors import _issue_actor as mint\nregister(mint)",
        "from you_story.identity.infrastructure.wiring import _issuer as mint\nregister(mint)",
        "from you_story.identity.infrastructure.actors import *",
        "from you_story.identity.infrastructure.wiring import *",
        "import you_story.identity.infrastructure.wiring as wiring\nregister(wiring._issuer)",
        "import you_story.identity.infrastructure.wiring\n"
        "register(you_story.identity.infrastructure.wiring._issuer)",
    ],
)
def test_minting_capabilities_cannot_escape_approved_chain(path: str, source: str) -> None:
    errors = check_source(path, source)
    assert any("issuance capability" in error for error in errors)


def test_minting_capability_has_one_exact_call_site_and_no_extraction() -> None:
    source = (
        "from you_story.identity.infrastructure.actors import issue_session\n"
        "def _issuer(row, bearer):\n"
        " return issue_session(row.user,row.tenant,row.session,'ready',row.expiry,bearer)"
    )
    assert check_source("identity/infrastructure/wiring.py", source) == []
    for mutation in (
        source.replace("def _issuer(", "def other("),
        source.replace(
            " return issue_session(", " register(issue_session)\n return issue_session("
        ),
        source + "\nexternal = issue_session\n",
    ):
        assert any(
            "issuance capability" in error
            for error in check_source("identity/infrastructure/wiring.py", mutation)
        )
