"""Closed Yousician policy and safe catalog errors."""

from __future__ import annotations

import unicodedata
from typing import Any
from uuid import UUID

MAX_VERSION = 9223372036854775807


class CatalogFailure(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code
        super().__init__("Catalog request failed")


def invalid() -> CatalogFailure:
    return CatalogFailure(422, "invalid_input")


def identifier(value: object) -> UUID:
    try:
        if type(value) is UUID:
            return value
        if type(value) is not str:
            raise ValueError
        result = UUID(value)
        if str(result) != value:
            raise ValueError
        return result
    except (ValueError, TypeError, AttributeError):
        raise invalid() from None


def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise invalid()
    return value


def name(value: object, *, empty: bool = False) -> str:
    if type(value) is not str:
        raise invalid()
    result = unicodedata.normalize("NFC", value).strip()
    if len(result) > 200 or (not empty and not result) or "\x00" in result:
        raise invalid()
    return result


def metadata(entry_type: str, value: object, *, create: bool) -> dict[str, Any]:
    if type(value) is not dict or any(type(k) is not str for k in value):
        raise invalid()
    if entry_type == "song":
        if set(value) - {"author"} or (not create and "author" not in value):
            raise invalid()
        author = value.get("author")
        return {"author": None if author is None else name(author)}
    if entry_type == "version":
        if set(value) != {"level"}:
            raise invalid()
        return {"level": integer(value["level"], 0, 15)}
    if entry_type == "fragment":
        fields = {"length_seconds", "notes_count"}
        if set(value) - fields or (not create and set(value) != fields):
            raise invalid()
        length = value.get("length_seconds")
        return {
            "length_seconds": None if length is None else integer(length, 1, 2147483647),
            "notes_count": integer(value.get("notes_count", 0), 0, 2147483647),
        }
    raise invalid()


def exact(value: object, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) - allowed or not required <= set(value):
        raise invalid()
    return value


def require_version(values: dict[str, Any]) -> int:
    if "expected_entry_version" not in values:
        raise CatalogFailure(428, "precondition_required")
    return integer(values["expected_entry_version"], 1, MAX_VERSION)


def defined_metadata(
    definition: dict[str, Any],
    entry_type: str,
    value: object,
    *,
    create: bool,
) -> dict[str, Any]:
    """Validate immutable published field descriptors, never executable schemas."""
    rules = [rule for rule in definition["metadata_rules"] if rule["entry_type"] == entry_type]
    if len(rules) != 1 or type(value) is not dict:
        raise invalid()
    fields = rules[0]["fields"]
    allowed = {field["key"] for field in fields}
    if set(value) - allowed:
        raise invalid()
    result: dict[str, Any] = {}
    for field in fields:
        key = field["key"]
        required = field["required_on_create"] if create else field["required_on_replace"]
        if key not in value and required:
            raise invalid()
        item = value.get(key, field["default"])
        if item is None:
            if not field["nullable"]:
                raise invalid()
        elif field["kind"] == "integer":
            item = integer(item, field["min"], field["max"])
        elif field["kind"] == "text":
            item = name(item)
            if not field["min"] <= len(item) <= field["max"]:
                raise invalid()
        else:
            raise invalid()
        result[key] = item
    return result
