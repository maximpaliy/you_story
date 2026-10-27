"""Reviewed schema-only revision list and strict PostgreSQL parse guard."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any

from pglast import parser

REVISION_PATHS = {
    "000_security": "migrations/000_security.sql",
    "001_identity": "identity/infrastructure/migrations/001_identity.sql",
    "002_catalog": "catalog/infrastructure/migrations/002_catalog.sql",
    "003_practice": "practice/infrastructure/migrations/003_practice.sql",
    "004_media": "media/infrastructure/migrations/004_media.sql",
    "005_identity": "identity/infrastructure/migrations/005_identity.sql",
    "006_catalog": "catalog/infrastructure/migrations/006_catalog.sql",
}


def migration_sql(version: str) -> str:
    return files("you_story").joinpath(REVISION_PATHS[version]).read_text()


REVIEWED_CHECKSUMS = {
    "000_security": "9b8a4bdb3e93d1956fdd8577ac7afb890021a1002edfd7726d15758159a91d3f",
    "001_identity": "3673481b1e90f9c2f73545a0b69b4af760cfd6eabca29ca41fb203750d010f4f",
    "002_catalog": "d8124495463d4179ed62b711a709af68f847e9871ed13928af38b36510800f60",
    "003_practice": "4be1452ba450c3bce52105fcc5c1a280b36b29921ab1a551502127229cf15115",
    "004_media": "a941bacb7712493f6e6ea1896c4c1e28591c79e53b6c0753e389f74e2576e0ce",
    "005_identity": "4cad83d3b26ad8dab1abbb2666c21ed1a6db7c088cec844745009d55c91e04bc",
    "006_catalog": "89a595b28751fb0da53a64b5000ec5eb4b4812c2272559adcbff04d3dc6b5d39",
}


def expected_revisions() -> dict[str, str]:
    return dict(REVIEWED_CHECKSUMS)


def validate_migration(owner: str, sql: str) -> None:
    """Only packaged, reviewed ASTs may run; unknown statements fail closed.

    Comparing parsed trees, rather than SQL substrings, makes every ownership,
    privilege, policy and migration classification change an explicit reviewed
    artifact change. Comments and formatting are immaterial to the guard.
    """

    def statements(text: str) -> Any:
        return json.loads(parser.parse_sql_json(text))["stmts"]

    versions = (
        [owner]
        if owner in REVISION_PATHS
        else [v for v in REVISION_PATHS if v.split("_", 1)[1] == owner]
    )
    if not versions:
        raise ValueError("unreviewed migration owner")
    for version in versions:
        reviewed = migration_sql(version)
        if hashlib.sha256(reviewed.encode()).hexdigest() != REVIEWED_CHECKSUMS[version]:
            raise ValueError("unreviewed packaged migration checksum")
    candidate = statements(sql)
    if not any(candidate == statements(migration_sql(version)) for version in versions):
        raise ValueError("unreviewed migration AST/classification")
