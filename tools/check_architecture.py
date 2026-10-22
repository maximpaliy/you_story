"""Fail-closed checks for the deliberately health-only foundation artifact."""

from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from collections import Counter
from pathlib import Path

MODULES = {"identity", "catalog", "practice", "media", "reporting"}
EDGES = {
    "identity": set(),
    "catalog": set(),
    "practice": {"catalog"},
    "media": {"practice"},
    "reporting": {"identity", "catalog", "practice", "media"},
}
EXPECTED_COMPOSITION = {
    "http": "you_story.app:create_app",
    "migration": "you_story.migrations",
    "private_statements": [],
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


def check_source(relative: str, source: str) -> list[str]:
    errors: list[str] = []
    path = Path(relative)
    parts = path.parts
    module = parts[0] if parts and parts[0] in MODULES else None
    tree = ast.parse(source)
    package = "you_story." + ".".join(parts[:-1])
    dependencies = imports(tree, package)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
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
            target[0] in {"fastapi", "starlette", "sqlalchemy", "psycopg", "google"}
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
        if isinstance(node, ast.ClassDef) and "repository" in node.name.lower():
            errors.append("private repository not approved")
        if (
            isinstance(node, ast.Attribute)
            and node.attr
            in {
                "execute",
                "executemany",
                "exec_driver_sql",
                "cursor",
            }
            and relative not in TECHNICAL_SQL
        ):
            errors.append("unregistered SQL execution site")
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else (node.func.id if isinstance(node.func, ast.Name) else "")
            )
            name = aliases.get(name, name)
            if name in {
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
            if name in {"execute", "executemany", "exec_driver_sql", "cursor"}:
                if relative not in TECHNICAL_SQL:
                    errors.append("unregistered SQL execution site")
            if name in {"create_task", "ensure_future", "add_task", "add_job", "start_soon"}:
                errors.append("unregistered asynchronous execution root")
            if name in {"ActorContext", "_issue_actor"}:
                errors.append("production actor issuer absent until authentication gate")
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
    """No product executable code exists in this restricted increment."""
    if relative in TECHNICAL_FILES:
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
    actual = {
        file.relative_to(package).as_posix()
        for file in package.rglob("*")
        if file.is_file() and file.suffix in {".sql", ".json"}
    }
    return [] if actual == allowed else ["unclassified/missing packaged data"]


DEPLOYMENT_CHECKSUMS = {
    "compose.yaml": "a78d62f8a44d364a58e02ae986a3a6845cb12275887b0dc99fc6c0e72100c00c",
    ".github/workflows/checks.yml": (
        "1ceff4b0f7e16ff99f369afd758184c32fc3d733b3122886cf33d99ba57dc928"
    ),
}


def check_deployment(root: Path) -> list[str]:
    actual = {
        p.relative_to(root).as_posix()
        for pattern in (
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
    registry = json.loads((package / "technical-sql.json").read_text())
    for relative in TECHNICAL_SQL:
        if dict(sql_sites((package / relative).read_text())) != registry.get(relative):
            errors.append(f"{relative}: unregistered technical SQL statement site")
    if set(registry) != TECHNICAL_SQL:
        errors.append("unclassified technical SQL file")
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
