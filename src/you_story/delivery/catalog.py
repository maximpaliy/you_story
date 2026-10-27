"""Authenticated, bounded catalog HTTP and native form adapters."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Coroutine
from importlib.resources import files
from typing import Any, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from you_story.catalog.public import CatalogFailure, CatalogService
from you_story.delivery.browser import (
    SESSION_COOKIE,
    BrowserFailure,
    _body,
    _cookie,
    _decode_pairs,
    _origin,
    _provenance,
    _render,
)
from you_story.identity.public import AuthenticatedSession, AuthFailure, IdentityService

_LIMIT = 16384
_SEARCH = {"text", "author", "source_key", "instrument_id", "entry_type", "ancestor_id"}
_PAGE = {"page_size", "cursor"}
_MESSAGES = {
    "unauthenticated": "Authentication required",
    "forbidden": "Request forbidden",
    "resource_not_found": "Resource not found",
    "conflict": "Catalog operation conflicts with current state",
    "version_conflict": "Catalog changed; reload before trying again",
    "precondition_required": "Current catalog and entry versions are required",
    "invalid_input": "Invalid catalog input",
    "payload_too_large": "Request too large",
    "unsupported_media_type": "Unsupported request type",
    "unavailable": "Service unavailable",
    "internal_error": "An unexpected error occurred",
}
_CONTRACT: dict[str, Any] = json.loads(
    files("you_story.delivery").joinpath("catalog-contract.json").read_text()
)


def catalog_schema_components() -> dict[str, Any]:
    """Closed approved component definitions for composition's schema generator."""
    return cast(dict[str, Any], _CONTRACT["components"])


def _failure(status: int = 422, code: str = "invalid_input") -> CatalogFailure:
    return CatalogFailure(status, code)


def _uuid(value: str) -> UUID:
    try:
        result = UUID(value)
        if str(result) != value:
            raise ValueError
        return result
    except (ValueError, AttributeError, TypeError):
        raise _failure() from None


def _integer(value: str) -> int:
    if not re.fullmatch(r"[0-9]{1,19}", value):
        raise _failure()
    return int(value)


def _version(value: str | None) -> int:
    if value is None:
        raise _failure(428, "precondition_required")
    result = _integer(value)
    if not 1 <= result <= 9223372036854775807:
        raise _failure()
    return result


def _match(request: Request) -> tuple[UUID, int]:
    values = request.headers.getlist("if-match")
    if not values:
        raise _failure(428, "precondition_required")
    if len(values) != 1:
        raise _failure()
    match = re.fullmatch(r'"catalog:([0-9a-f-]{36}):([1-9][0-9]{0,18})"', values[0])
    if match is None:
        raise _failure()
    return _uuid(match[1]), _version(match[2])


def _etag(kind: str, value: dict[str, Any]) -> str:
    return f'"{kind}:{value["id"]}:{value["version"]}"'


def _error(request: Request, status: int, code: str, *, html: bool = False) -> Response:
    if code not in _MESSAGES:
        status, code = 500, "internal_error"
    if html:
        return _render("catalog_failure.html", status=status, message=_MESSAGES[code])
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": _MESSAGES[code],
                "correlation_id": request.state.correlation_id,
            }
        },
        status_code=status,
    )


def _pairs(raw: bytes, allowed: set[str], *, csrf: bool = False) -> dict[str, str]:
    try:
        return _decode_pairs(raw, allowed, token_field="csrf" if csrf else None)
    except BrowserFailure as error:
        if error.status == 403:
            raise
        raise _failure() from None


async def _empty_body(request: Request) -> None:
    try:
        await _body(request, 0)
    except BrowserFailure:
        raise _failure() from None


def _query(request: Request, allowed: set[str]) -> dict[str, str]:
    raw = request.scope["query_string"]
    if len(raw) > 8192:
        raise _failure()
    return _pairs(raw, allowed)


async def _payload(request: Request, *, form: bool) -> dict[str, Any]:
    if request.scope["query_string"]:
        raise _failure()
    raw = await _body(request, _LIMIT)
    types = request.headers.getlist("content-type")
    if len(types) != 1:
        raise _failure(415, "unsupported_media_type")
    parts = [part.strip().lower() for part in types[0].split(";")]
    expected = "application/x-www-form-urlencoded" if form else "application/json"
    if parts[0] != expected or (len(parts) > 1 and parts[1:] != ["charset=utf-8"]):
        raise _failure(415, "unsupported_media_type")
    if form:
        return _pairs(
            raw,
            {
                "csrf",
                "expected_catalog_version",
                "expected_entry_version",
                "parent_entry_id",
                "source_key",
                "instrument_id",
                "entry_type",
                "name",
                "author",
                "level",
                "length_seconds",
                "notes_count",
                "new_parent_entry_id",
            },
            csrf=True,
        )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def invalid(value: str) -> Any:
        raise ValueError

    try:
        decoded = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=pairs, parse_constant=invalid
        )
        if type(decoded) is not dict:
            raise ValueError
        return decoded
    except (ValueError, UnicodeError, RecursionError):
        raise _failure() from None


def _page_args(query: dict[str, str]) -> tuple[dict[str, str], int, str | None]:
    size = _integer(query.get("page_size", "50"))
    if not 1 <= size <= 100:
        raise _failure()
    return {key: value for key, value in query.items() if key in _SEARCH}, size, query.get("cursor")


def _form_values(
    fields: dict[str, Any], operation: str, entry: dict[str, Any] | None
) -> dict[str, Any]:
    common = {"csrf", "expected_catalog_version"}
    if operation == "create":
        allowed = common | {
            "parent_entry_id",
            "source_key",
            "instrument_id",
            "entry_type",
            "name",
            "author",
            "level",
            "length_seconds",
            "notes_count",
        }
    elif operation == "update":
        allowed = common | {
            "expected_entry_version",
            "name",
            "author",
            "level",
            "length_seconds",
            "notes_count",
        }
    elif operation == "move":
        allowed = common | {"expected_entry_version", "new_parent_entry_id"}
    else:
        allowed = common | {"expected_entry_version"}
    if set(fields) - allowed:
        raise _failure()
    result: dict[str, Any] = {}
    if operation != "create":
        result["expected_entry_version"] = _version(fields.get("expected_entry_version"))
    if operation == "move":
        if "new_parent_entry_id" not in fields:
            raise _failure()
        result["new_parent_entry_id"] = fields["new_parent_entry_id"]
    if operation in {"create", "update"}:
        if "name" not in fields:
            raise _failure()
        result["name"] = fields["name"]
        kind = fields.get("entry_type") if entry is None else entry["type"]
        metadata: dict[str, Any]
        if kind == "song":
            if operation == "update" and "author" not in fields:
                raise _failure()
            if set(fields) & {"level", "length_seconds", "notes_count"}:
                raise _failure()
            metadata = {"author": fields.get("author") or None}
        elif kind == "version":
            if set(fields) & {"author", "length_seconds", "notes_count"} or "level" not in fields:
                raise _failure()
            metadata = {"level": _integer(fields["level"])}
        elif kind == "fragment":
            if operation == "update" and not {"length_seconds", "notes_count"} <= set(fields):
                raise _failure()
            if set(fields) & {"author", "level"}:
                raise _failure()
            metadata = {
                "length_seconds": _integer(fields["length_seconds"])
                if fields.get("length_seconds")
                else None,
                "notes_count": _integer(fields.get("notes_count", "0")),
            }
        else:
            raise _failure()
        result["metadata"] = metadata
        if operation == "create":
            if not {"source_key", "instrument_id", "entry_type"} <= set(fields):
                raise _failure()
            result.update(
                {key: fields[key] for key in ("source_key", "instrument_id", "entry_type")}
            )
            result["parent_entry_id"] = fields.get("parent_entry_id") or None
    return result


def register_catalog_routes(
    app: FastAPI,
    service: CatalogService | None,
    identity_service: IdentityService,
    *,
    canonical_origin: str,
) -> None:
    expected_origin = _origin(canonical_origin)

    async def session(request: Request, *, html: bool = False) -> AuthenticatedSession:
        current = await run_in_threadpool(
            identity_service.resolve_session, _cookie(request, SESSION_COOKIE)
        )
        if current is None:
            raise _failure(401, "unauthenticated")
        return current

    def available() -> CatalogService:
        if service is None:
            raise _failure(503, "unavailable")
        return service

    async def dispatch(
        request: Request,
        operation: Callable[[], Coroutine[Any, Any, Response]],
        *,
        html: bool = False,
    ) -> Response:
        try:
            return await operation()
        except (CatalogFailure, AuthFailure, BrowserFailure) as error:
            code = "invalid_input" if error.code == "invalid_request" else error.code
            status = 422 if error.code == "invalid_request" else error.status
            if html and request.method == "GET" and status == 401:
                return RedirectResponse("/login", status_code=303)
            return _error(request, status, code, html=html)

    def endpoint(path: str, method: str, operation: str) -> None:
        async def handle(request: Request) -> Response:
            async def action() -> Response:
                current = await session(request)
                target = available()
                entry_id = (
                    _uuid(request.path_params["entry_id"])
                    if "entry_id" in request.path_params
                    else None
                )
                if method == "GET":
                    await _empty_body(request)
                    allowed = (
                        (_SEARCH | _PAGE)
                        if operation == "search"
                        else _PAGE
                        if operation == "children"
                        else set()
                    )
                    query = _query(request, allowed)
                    filters, size, cursor = _page_args(query)
                    if operation == "get_catalog":
                        value = await run_in_threadpool(target.get_catalog, current.actor)
                    elif operation == "references":
                        value = await run_in_threadpool(target.references, current.actor)
                    elif operation == "search":
                        value = await run_in_threadpool(
                            target.search, current.actor, filters, size, cursor
                        )
                    elif operation == "children":
                        assert entry_id is not None
                        value = await run_in_threadpool(
                            target.children, current.actor, entry_id, size, cursor
                        )
                    elif operation == "ancestors":
                        assert entry_id is not None
                        value = await run_in_threadpool(target.ancestors, current.actor, entry_id)
                    else:
                        assert entry_id is not None
                        value = await run_in_threadpool(target.get_entry, current.actor, entry_id)
                    response = JSONResponse(value)
                    if operation in {"get_catalog", "get_entry"}:
                        response.headers["ETag"] = _etag(
                            "catalog" if operation == "get_catalog" else "entry", value
                        )
                    return response
                _provenance(request, expected_origin)
                values = await _payload(request, form=False)
                tokens = request.headers.getlist("x-csrf-token")
                if len(tokens) != 1 or not await run_in_threadpool(
                    identity_service.validate_csrf, current, tokens[0]
                ):
                    raise _failure(403, "forbidden")
                expected_catalog = _match(request)
                if operation == "create":
                    value = await run_in_threadpool(
                        target.create, current.actor, expected_catalog, values
                    )
                else:
                    assert entry_id is not None
                    value = await run_in_threadpool(
                        getattr(target, operation),
                        current.actor,
                        entry_id,
                        expected_catalog,
                        values,
                    )
                response = JSONResponse(value, status_code=201 if operation == "create" else 200)
                response.headers["ETag"] = _etag("catalog", value["catalog"])
                if operation == "create":
                    response.headers["Location"] = "/api/v1/catalog/entries/" + str(
                        value["entry"]["id"]
                    )
                return response

            return await dispatch(request, action)

        contract = dict(_CONTRACT["paths"][path][method.lower()])
        operation_id = contract.pop("operationId")
        responses = contract.pop("responses")
        app.add_api_route(
            path,
            handle,
            methods=[method],
            operation_id=operation_id,
            openapi_extra=contract,
            responses=responses,
            status_code=201 if operation == "create" else 200,
        )

    base = "/api/v1/catalog"
    for suffix, method, operation in [
        ("", "GET", "get_catalog"),
        ("/references", "GET", "references"),
        ("/entries", "GET", "search"),
        ("/entries/{entry_id}", "GET", "get_entry"),
        ("/entries/{entry_id}/children", "GET", "children"),
        ("/entries/{entry_id}/ancestors", "GET", "ancestors"),
        ("/entries", "POST", "create"),
        ("/entries/{entry_id}", "PATCH", "update"),
        ("/entries/{entry_id}/move", "POST", "move"),
        ("/entries/{entry_id}/tombstone", "POST", "tombstone"),
    ]:
        endpoint(base + suffix, method, operation)

    async def browse(request: Request) -> Response:
        async def action() -> Response:
            current = await session(request, html=True)
            await _empty_body(request)
            query = _query(request, _SEARCH | _PAGE)
            query = {key: value for key, value in query.items() if key in _PAGE or value.strip()}
            filters, size, cursor = _page_args(query)
            target = available()
            catalog = await run_in_threadpool(target.get_catalog, current.actor)
            refs = await run_in_threadpool(target.references, current.actor)
            if filters:
                page = await run_in_threadpool(target.search, current.actor, filters, size, cursor)
            else:
                page = await run_in_threadpool(target.browse_roots, current.actor, size, cursor)
            items = page["items"]
            next_url = None
            if page["next_cursor"]:
                next_url = "/catalog?" + urlencode({**query, "cursor": page["next_cursor"]})
            return _render(
                "catalog_index.html",
                catalog=catalog,
                refs=refs,
                items=items,
                filters=filters,
                next_url=next_url,
            )

        return await dispatch(request, action, html=True)

    async def entry_page(request: Request) -> Response:
        async def action() -> Response:
            current = await session(request, html=True)
            await _empty_body(request)
            query = _query(
                request,
                {"parent_entry_id", "instrument_id"}
                if request.url.path.endswith("/new")
                else set(),
            )
            target = available()
            catalog = await run_in_threadpool(target.get_catalog, current.actor)
            refs = await run_in_threadpool(target.references, current.actor)
            csrf = await run_in_threadpool(identity_service.csrf_token, current)
            if request.url.path.endswith("/new"):
                parent = (
                    await run_in_threadpool(
                        target.get_entry, current.actor, _uuid(query["parent_entry_id"])
                    )
                    if query.get("parent_entry_id")
                    else None
                )
                kind = {None: "song", "song": "version", "version": "fragment"}.get(
                    parent["type"] if parent else None
                )
                if kind is None or (parent and parent["state"] != "active"):
                    raise _failure(409, "conflict")
                selected = parent["instrument_id"] if parent else query.get("instrument_id", "")
                if selected and selected not in {str(item["id"]) for item in refs["instruments"]}:
                    raise _failure()
                return _render(
                    "catalog_edit.html",
                    catalog=catalog,
                    refs=refs,
                    csrf=csrf,
                    entry=None,
                    parent=parent,
                    kind=kind,
                    selected=selected,
                )
            entry_id = _uuid(request.path_params["entry_id"])
            entry = await run_in_threadpool(target.get_entry, current.actor, entry_id)
            if request.url.path.endswith("/edit"):
                if entry["state"] != "active":
                    raise _failure(409, "conflict")
                return _render(
                    "catalog_edit.html",
                    catalog=catalog,
                    refs=refs,
                    csrf=csrf,
                    entry=entry,
                    parent=None,
                    kind=entry["type"],
                    selected=entry["instrument_id"],
                )
            ancestors = await run_in_threadpool(target.ancestors, current.actor, entry_id)
            children = await run_in_threadpool(target.children, current.actor, entry_id, 100, None)
            return _render(
                "catalog_entry.html",
                catalog=catalog,
                entry=entry,
                csrf=csrf,
                ancestors=ancestors["items"],
                children=children["items"],
                more_children=children["next_cursor"] is not None,
            )

        return await dispatch(request, action, html=True)

    def form_endpoint(path: str, operation: str) -> None:
        async def handle(request: Request) -> Response:
            async def action() -> Response:
                current = await session(request)
                _provenance(request, expected_origin)
                fields = await _payload(request, form=True)
                if request.headers.getlist("x-csrf-token") or not await run_in_threadpool(
                    identity_service.validate_csrf, current, fields.get("csrf", "")
                ):
                    raise _failure(403, "forbidden")
                target = available()
                catalog = await run_in_threadpool(target.get_catalog, current.actor)
                expected_catalog = (
                    _uuid(str(catalog["id"])),
                    _version(fields.get("expected_catalog_version")),
                )
                entry_id = (
                    _uuid(request.path_params["entry_id"])
                    if "entry_id" in request.path_params
                    else None
                )
                entry = (
                    await run_in_threadpool(target.get_entry, current.actor, entry_id)
                    if entry_id is not None
                    else None
                )
                values = _form_values(fields, operation, entry)
                if operation == "create":
                    result = await run_in_threadpool(
                        target.create, current.actor, expected_catalog, values
                    )
                else:
                    assert entry_id is not None
                    result = await run_in_threadpool(
                        getattr(target, operation),
                        current.actor,
                        entry_id,
                        expected_catalog,
                        values,
                    )
                return RedirectResponse(
                    "/catalog/entries/" + str(result["entry"]["id"]), status_code=303
                )

            return await dispatch(request, action, html=True)

        app.add_api_route(
            path,
            handle,
            methods=["POST"],
            status_code=303,
            operation_id="catalog_form_" + operation,
            response_class=RedirectResponse,
            openapi_extra={"security": [{"CatalogSession": []}]},
        )

    app.add_api_route(
        "/catalog", browse, methods=["GET"], operation_id="catalogPage", response_class=HTMLResponse
    )
    app.add_api_route(
        "/catalog/entries/new",
        entry_page,
        methods=["GET"],
        operation_id="catalogCreateForm",
        response_class=HTMLResponse,
    )
    app.add_api_route(
        "/catalog/entries/{entry_id}/edit",
        entry_page,
        methods=["GET"],
        operation_id="catalogEditForm",
        response_class=HTMLResponse,
    )
    app.add_api_route(
        "/catalog/entries/{entry_id}",
        entry_page,
        methods=["GET"],
        operation_id="catalogEntryPage",
        response_class=HTMLResponse,
    )
    form_endpoint("/catalog/entries", "create")
    form_endpoint("/catalog/entries/{entry_id}/edit", "update")
    form_endpoint("/catalog/entries/{entry_id}/move", "move")
    form_endpoint("/catalog/entries/{entry_id}/tombstone", "tombstone")
