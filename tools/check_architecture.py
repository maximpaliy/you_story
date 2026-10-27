"""Fail-closed source, SQL and composition gates for the approved login slice."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import tomllib
from collections import Counter
from pathlib import Path

MODULES = {"identity", "catalog", "practice", "media", "reporting"}
EDGES = {
    "identity": set(),
    "catalog": {"identity"},
    "practice": {"catalog"},
    "media": {"practice"},
    "reporting": {"identity", "catalog", "practice", "media"},
}
EXPECTED_COMPOSITION = {
    "http": "you_story.app:create_app",
    "migration": "you_story.migrations",
    "private_statements": [
        "catalog/infrastructure/provisioning.py:_ensure_pair:catalog_insert",
        "catalog/infrastructure/provisioning.py:_ensure_pair:catalog_select",
        "catalog/infrastructure/provisioning.py:_ensure_pair:grant_insert",
        "catalog/infrastructure/provisioning.py:_ensure_pair:grant_select",
    ],
    "workers": [],
    "media_adapters": [],
}
TECHNICAL_FILES = {
    "__init__.py",
    "app.py",
    "delivery/__init__.py",
    "delivery/contracts.py",
    "shared/__init__.py",
    "shared/config.py",
    "shared/context.py",
    "shared/database.py",
    "shared/primitives.py",
    "migrations/__init__.py",
    "migrations/__main__.py",
    "migrations/runner.py",
    "migrations/manifest.py",
}
TECHNICAL_SQL = {"shared/database.py", "migrations/runner.py"}
REGISTERED_SQL = TECHNICAL_SQL | {
    "identity/infrastructure/postgres.py",
    "catalog/infrastructure/provisioning.py",
    "catalog/infrastructure/repository.py",
}
FEATURE_FILES = {
    "identity/public/__init__.py",
    "identity/application/service.py",
    "identity/domain/contracts.py",
    "identity/infrastructure/config.py",
    "identity/infrastructure/crypto.py",
    "identity/infrastructure/postgres.py",
    "identity/infrastructure/actors.py",
    "identity/infrastructure/wiring.py",
    "identity/infrastructure/google.py",
    "catalog/public/__init__.py",
    "catalog/infrastructure/provisioning.py",
    "delivery/browser.py",
    "delivery/catalog.py",
    "catalog/infrastructure/config.py",
    "catalog/infrastructure/repository.py",
    "catalog/domain/policy.py",
    "catalog/application/service.py",
    "catalog/application/cursors.py",
}
ACTOR_ISSUER = "identity/infrastructure/actors.py"
EVIDENCE_REGISTRY = "identity/public/__init__.py"
TEMPLATES = {
    "delivery/templates/login.html",
    "delivery/templates/profile.html",
    "delivery/templates/failure.html",
    "delivery/templates/catalog_index.html",
    "delivery/templates/catalog_entry.html",
    "delivery/templates/catalog_edit.html",
    "delivery/templates/catalog_failure.html",
}


def imports(tree: ast.AST, package: str) -> list[str]:
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                parts = package.split(".")
                prefix = ".".join(
                    parts[: len(parts) - node.level + 1] + ([prefix] if prefix else [])
                )
            result.append(prefix)
            result.extend(f"{prefix}.{alias.name}" for alias in node.names)
    return result


def check_issuance_capabilities(relative: str, tree: ast.AST, aliases: dict[str, str]) -> list[str]:
    """Minting functions are capabilities, including imports and extracted references."""
    issuer = "identity/infrastructure/actors.py"
    wiring = "identity/infrastructure/wiring.py"
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def qualified_reference(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return qualified_reference(node.value) + "." + node.attr
        return ""

    def enclosing_function(node: ast.AST) -> str | None:
        current = parents.get(node)
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
            current = parents.get(current)
        return None

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").endswith(("actors", "wiring")) and any(
                item.name == "*" for item in node.names
            ):
                errors.append("identity issuance capability wildcard import forbidden")
            for item in node.names:
                if item.name in {"issue_session", "_issue_actor"}:
                    allowed = relative == wiring and item.name == "issue_session"
                    if not allowed:
                        errors.append("identity issuance capability import outside exact wiring")
                if item.name == "_issuer" and (node.module or "").endswith("wiring"):
                    errors.append("identity issuance capability import outside exact wiring")
                if item.name == "actors" and relative not in {issuer, wiring}:
                    errors.append("identity issuer module outside exact wiring")
                if item.name == "wiring" and relative not in {wiring, EVIDENCE_REGISTRY}:
                    errors.append("identity wiring module outside approved factory facade")
        if isinstance(node, ast.Import):
            if any(
                item.name.endswith("identity.infrastructure.actors") for item in node.names
            ) and relative not in {issuer, wiring}:
                errors.append("identity issuer module outside exact wiring")
            if any(
                item.name.endswith("identity.infrastructure.wiring") for item in node.names
            ) and relative not in {wiring, EVIDENCE_REGISTRY}:
                errors.append("identity wiring module outside approved factory facade")
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "_issuer"
            and qualified_reference(node.value).endswith("wiring")
        ):
            errors.append("identity issuance capability outside exact call site")
        name = None
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name = aliases.get(node.id, node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            name = node.attr
        if name not in {"issue_session", "_issue_actor"}:
            continue
        parent = parents.get(node)
        direct_call = isinstance(parent, ast.Call) and parent.func is node
        allowed = direct_call and (
            (
                name == "issue_session"
                and relative == wiring
                and enclosing_function(node) == "_issuer"
            )
            or (
                name == "_issue_actor"
                and relative == issuer
                and enclosing_function(node) == "issue_session"
            )
        )
        if not allowed:
            errors.append("identity issuance capability outside exact call site")
    return sorted(set(errors))


def check_source(relative: str, source: str) -> list[str]:
    errors: list[str] = []
    path = Path(relative)
    parts = path.parts
    module = parts[0] if parts and parts[0] in MODULES else None
    tree = ast.parse(source)
    package = "you_story." + ".".join(parts[:-1])
    dependencies = imports(tree, package)
    regex_modules = {
        alias.asname or "re"
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "re"
    }
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
    errors.extend(check_issuance_capabilities(relative, tree, aliases))
    for dependency in dependencies:
        if not dependency.startswith("importlib.resources") and dependency.split(".")[0] in {
            "threading",
            "_thread",
            "multiprocessing",
            "asyncio",
            "concurrent",
            "subprocess",
            "importlib",
            "celery",
            "apscheduler",
            "rq",
        }:
            errors.append("unapproved runtime execution/import facility")
    private_layer = module and any(x in {"domain", "application"} for x in parts[1:])
    for dependency in dependencies:
        target = dependency.split(".")
        if private_layer and (
            target[0]
            in {
                "fastapi",
                "starlette",
                "sqlalchemy",
                "psycopg",
                "google",
                "httpx",
                "jwt",
                "cryptography",
                "jinja2",
            }
            or ".delivery" in dependency
            or ".infrastructure" in dependency
        ):
            errors.append("domain/application adapter dependency")
        if target[0] != "you_story" or len(target) < 2:
            continue
        owner = target[1]
        if owner in MODULES and owner != module:
            if len(target) < 3 or target[2] != "public":
                # app may only wire technical infrastructure, never module-private code.
                errors.append("foreign module private import")
            if module and owner not in EDGES[module]:
                errors.append("forbidden module edge")
    if relative not in {ACTOR_ISSUER, EVIDENCE_REGISTRY} and any(
        (isinstance(node, ast.Name) and node.id in {"_ACTORS", "_SESSIONS"})
        or (isinstance(node, ast.Attribute) and node.attr in {"_ACTORS", "_SESSIONS"})
        for node in ast.walk(tree)
    ):
        errors.append("identity evidence registry outside trusted issuer")
    if relative not in {ACTOR_ISSUER, EVIDENCE_REGISTRY} and any(
        dependency.rsplit(".", 1)[-1] in {"_ACTORS", "_SESSIONS"} for dependency in dependencies
    ):
        errors.append("identity evidence registry outside trusted issuer")
    behavior = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    if module == "media" and "infrastructure" in parts and behavior:
        errors.append("dormant media adapter")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ClassDef)
            and "repository" in node.name.lower()
            and not (
                relative == "catalog/infrastructure/repository.py"
                and node.name == "CatalogRepository"
            )
        ):
            errors.append("private repository not approved")
        if (
            isinstance(node, ast.Attribute)
            and node.attr
            in {
                "execute",
                "executemany",
                "exec_driver_sql",
                "cursor",
                "_rows",
            }
            and relative not in REGISTERED_SQL
        ):
            errors.append("unregistered SQL execution site")
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else (node.func.id if isinstance(node.func, ast.Name) else "")
            )
            name = aliases.get(name, name)
            regex_compile = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "compile"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in regex_modules
            )
            if not regex_compile and name in {
                "__import__",
                "eval",
                "exec",
                "compile",
                "import_module",
                "fork",
                "forkpty",
                "posix_spawn",
                "posix_spawnp",
                "system",
                "popen",
                "start_new_thread",
            }:
                errors.append("dynamic execution/import forbidden")
            if name in {"execute", "executemany", "exec_driver_sql", "cursor", "_rows"}:
                if relative not in REGISTERED_SQL:
                    errors.append("unregistered SQL execution site")
            if name in {"create_task", "ensure_future", "add_task", "add_job", "start_soon"}:
                errors.append("unregistered asynchronous execution root")
            if name == "ActorContext":
                errors.append("actor construction outside trusted identity issuer")
            if name in {"_issue_actor", "AuthenticatedSession"} and relative != ACTOR_ISSUER:
                errors.append("session/actor issuance outside trusted identity issuer")
            if (
                name == "__new__"
                and any(
                    isinstance(item, ast.Name) and aliases.get(item.id, item.id) == "ActorContext"
                    for argument in node.args
                    for item in ast.walk(argument)
                )
                and relative != ACTOR_ISSUER
            ):
                errors.append("actor construction outside trusted identity issuer")
            if name == "Table":
                schemas = [keyword.value for keyword in node.keywords if keyword.arg == "schema"]
                if len(schemas) != 1 or not isinstance(schemas[0], ast.Constant):
                    errors.append("unclassified schema mapping")
                elif schemas[0].value != module:
                    errors.append("foreign schema mapping")
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__table_args__" for t in node.targets
        ):
            for value in ast.walk(node.value):
                if isinstance(value, ast.Dict):
                    for key, item in zip(value.keys, value.values, strict=True):
                        if isinstance(key, ast.Constant) and key.value == "schema":
                            if not isinstance(item, ast.Constant) or item.value != module:
                                errors.append("foreign schema mapping")
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            if any(isinstance(n, ast.Name) and n.id == "__name__" for n in ast.walk(node.test)):
                if relative != "migrations/__main__.py":
                    errors.append("unregistered executable root")
    if path.name == "__main__.py" and relative != "migrations/__main__.py":
        errors.append("unregistered executable module")
    return sorted(set(errors))


def check_file_inventory(relative: str, source: str) -> list[str]:
    """Only the explicit reviewed feature implementation may carry behavior."""
    if relative in TECHNICAL_FILES | FEATURE_FILES:
        return []
    parts = Path(relative).parts
    if parts[0] in MODULES and parts[-1] in {"__init__.py", "public.py"}:
        body = ast.parse(source).body
        if all(
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for node in body
        ):
            return []
    return ["unregistered packaged source/behavior"]


def sql_sites(source: str) -> Counter[str]:
    sites: Counter[str] = Counter()

    def visit(node: ast.AST, function: str = "<module>") -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr
            in {
                "execute",
                "executemany",
                "exec_driver_sql",
                "cursor",
                "_rows",
            }
        ):
            arguments = ast.dump(node, include_attributes=False)
            key = (
                function
                + ":"
                + node.func.attr
                + ":"
                + hashlib.sha256(arguments.encode()).hexdigest()
            )
            sites[key] += 1
        if isinstance(node, ast.Attribute) and node.attr in {
            "execute",
            "executemany",
            "exec_driver_sql",
            "cursor",
            "_rows",
        }:
            sites[function + ":reference:" + ast.dump(node, include_attributes=False)] += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            isinstance(item, ast.Attribute)
            and item.attr
            in {
                "execute",
                "executemany",
                "exec_driver_sql",
                "cursor",
                "_rows",
            }
            for item in ast.walk(node)
        ):
            sites[
                function
                + ":body:"
                + hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            ] += 1
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(ast.parse(source))
    return sites


def check_data_inventory(package: Path) -> list[str]:
    allowed = {
        "composition.json",
        "technical-sql.json",
        "migrations/000_security.sql",
        "migrations/schema_manifest.json",
        "identity/infrastructure/migrations/005_identity.sql",
        "catalog/infrastructure/migrations/006_catalog.sql",
        "delivery/catalog-contract.json",
    }
    allowed.update(
        f"{module}/infrastructure/migrations/{version}_{module}.sql"
        for module, version in [
            ("identity", "001"),
            ("catalog", "002"),
            ("practice", "003"),
            ("media", "004"),
        ]
    )
    allowed.update(TEMPLATES)
    actual = {
        file.relative_to(package).as_posix()
        for file in package.rglob("*")
        if file.is_file() and file.suffix in {".sql", ".json", ".html"}
    }
    return [] if actual == allowed else ["unclassified/missing packaged data"]


def check_template(relative: str, source: str) -> list[str]:
    """This slice has escaped forms only: no scripts, styles or safe-marked text."""
    if relative not in TEMPLATES:
        return ["unregistered template"]
    forbidden = (
        r"\|\s*safe\b",
        r"\bautoescape\s+(?:false|off)\b",
        r"<(?:script|style|iframe|object|embed|link|img|audio|video|source|base)\b",
        r"\b(?:on[a-z]+|style)\s*=",
        r"(?:javascript|data)\s*:",
    )
    if any(re.search(pattern, source, re.IGNORECASE) for pattern in forbidden):
        return ["unapproved template sink/resource"]
    return []


def check_sql_registry(package: Path) -> list[str]:
    registry_file = package / "technical-sql.json"
    if not registry_file.exists():
        return ["missing reviewed SQL registry"]
    registry = json.loads(registry_file.read_text())
    errors = []
    for relative in REGISTERED_SQL:
        file = package / relative
        if not file.exists() or dict(sql_sites(file.read_text())) != registry.get(relative):
            errors.append(f"{relative}: unregistered reviewed SQL statement site")
    if set(registry) != REGISTERED_SQL:
        errors.append("unclassified reviewed SQL file")
    return errors


DEPLOYMENT_CHECKSUMS = {
    "Makefile": "39725a061a9af8f44f3c94ec6da91dd6fb7dbfaca1ee1ef098035c21cb08f3c6",
    "compose.yaml": "a78d62f8a44d364a58e02ae986a3a6845cb12275887b0dc99fc6c0e72100c00c",
    ".github/workflows/checks.yml": (
        "798fb4c018c4b3d22ab97f003d55bacc5f9acd2ed33739d709d49ed26c417cfd"
    ),
}


def check_deployment(root: Path) -> list[str]:
    actual = {
        p.relative_to(root).as_posix()
        for pattern in (
            "Makefile",
            "*.yaml",
            "*.yml",
            "Dockerfile*",
            "deploy/**/*",
            "infra/**/*",
            ".github/workflows/*",
        )
        for p in root.glob(pattern)
        if p.is_file()
    }
    if actual != set(DEPLOYMENT_CHECKSUMS):
        return ["unregistered deployment descriptor"]
    if any(
        hashlib.sha256((root / path).read_bytes()).hexdigest() != checksum
        for path, checksum in DEPLOYMENT_CHECKSUMS.items()
    ):
        return ["unreviewed deployment command/descriptor"]
    return []


def check_project(root: Path) -> list[str]:
    errors = []
    package = root / "src/you_story"
    for file in package.rglob("*.py"):
        relative = file.relative_to(package).as_posix()
        errors.extend(
            f"{relative}: {error}"
            for error in check_source(relative, file.read_text())
            + check_file_inventory(relative, file.read_text())
        )
    errors.extend(check_data_inventory(package))
    errors.extend(check_deployment(root))
    errors.extend(check_sql_registry(package))
    for file in package.rglob("*.html"):
        errors.extend(check_template(file.relative_to(package).as_posix(), file.read_text()))
    project = tomllib.loads((root / "pyproject.toml").read_text())
    if project["project"].get("scripts") or project["project"].get("gui-scripts"):
        errors.append("unregistered packaged executable")
    if project["project"].get("entry-points"):
        errors.append("unregistered plugin/consumer")
    manifest = json.loads((package / "composition.json").read_text())
    if manifest != EXPECTED_COMPOSITION:
        errors.append("unapproved composition manifest")
    return errors


if __name__ == "__main__":
    failures = check_project(Path(__file__).resolve().parents[1])
    if failures:
        raise SystemExit("\n".join(failures))
    print("Architecture source/composition checks passed")
