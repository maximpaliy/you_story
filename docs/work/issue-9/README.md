# Issue #9 — Executable modular-monolith/database foundation

Issue: https://github.com/maximpaliy/you_story/issues/9

Status: **in progress, partial implementation**. This work does not close #9,
SEC-01, SEC-05 or SEC-07 and does not unblock the dependent feature issues.

## Changes

The approved foundation subset supplies the FastAPI health-only application,
validated runtime configuration, UUID/UTC primitives, opaque immutable actor
contract without an issuer, pooled tenant-context transactions, owner-organized
PostgreSQL migrations and role/ACL/RLS controls. The initial schemas retain
identity, personal catalog/owner-grant, entry, practice snapshot and dormant
media identifiers. Runtime has no direct authentication-control-plane or media
privileges. There are no product repositories or authenticated routes.

The source/wheel/composition gates reject private cross-module imports,
forbidden dependency edges, mappings outside the owner schema, unregistered SQL,
production actor issuance, new execution roots, media adapters and hidden HTTP
routes. Exact migration hashes and parsed SQL changes require review; a migration
revision commits its DDL and ledger row together. The runtime's readiness check
uses the exact checksum ledger and real runtime identity/privileges.

Design and independent reviews:

- [Design and exact schema](design.md)
- [Test design](test-design.md)
- [Architecture review](architecture-review.md)
- [Security review](security-review.md)
- [Test-design review](test-design-review.md)
- [Code review](code-review.md)
- [Verification evidence](verification.md)

The implementation is in `src/you_story/`, PostgreSQL and mutation tests in
`tests/`, development checks in `tools/`, and CI in `.github/workflows/checks.yml`.
The root README documents reproducible local setup and verification.

## Remaining acceptance gates

Issue #6 still lacks the approved authentication/session lifecycle and its
security/test-design reviews. This foundation deliberately implements no
identity lookup, invitation redemption, session create/resolve/revoke or
privileged authentication function; it grants none of their runtime EXECUTE
privileges. ADR-008/TD-11 requires their functional, concurrency,
non-enumeration and rollback evidence in #9, so the issue remains incomplete.

There is no production ActorContext issuer, private repository or
catalog-provisioning public command/identity-ready transition. The complete
query-shape registry, actor provenance, application authorization,
non-enumeration and provisioning fault/race matrix must accompany those later
approved implementations. Simple test-only SQL probes cannot replace that
matrix. The then-present schema and runtime controls receive their own real
PostgreSQL tests without claiming product behavior is implemented.

Independent security/code review of the restricted subset passed, with 112
tests and all canonical checks passing. These reviews do not close the full issue. Deployed owner/runtime credential separation belongs
to #16; cloud, privacy, operational and production gates remain unchanged. No
real user data or production resource is used.
