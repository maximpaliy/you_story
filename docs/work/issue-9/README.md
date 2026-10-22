# Issue #9 — Executable modular-monolith/database foundation

Issue: https://github.com/maximpaliy/you_story/issues/9

Status: **database foundation ready for owner review**. The ADR-011 follow-up
passes 217 tests and independent reviews. Issue #9 remains open pending review
and merge; global SEC-01, SEC-05 and SEC-07 feature gates remain open.

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

## ADR-011 authentication foundation follow-up

The earlier #6-design blocker was based on stale local documentation. Issue #6
and ADR-011 are approved; its seven-table exception supersedes the initial
five-table assumptions. The original design/reviews above remain historical
records of PR #24, not current authentication approval status.

This owner-requested follow-up implements the database boundary through an
additive `005_identity` revision. Existing migrations and stored identities are
preserved; legacy sessions missing new linkage/CSRF fields fail closed. The
runtime retains zero direct control-table access; only exact reviewed functions
can start/claim/finalize login, resolve/revoke sessions, consume bounded counters,
and perform the internal session-derived ready transition. No HTTP auth route,
production actor issuer, cryptographic/provider adapter or catalog ensure command
is registered here.

- [Authentication database design](auth-foundation-design.md)
- [Authentication test design](auth-foundation-test-design.md)
- [Architecture review](auth-foundation-architecture-review.md)
- [Security review](auth-foundation-security-review.md)
- [Test-design review](auth-foundation-test-design-review.md)
- [Implementation code review](auth-foundation-code-review.md)
- [Test evidence review](auth-foundation-test-evidence-review.md)
- [Delta verification evidence](auth-foundation-verification.md)

## Remaining acceptance gates

Implementation, final verification and independent security/code/test reviews
passed for this delta: 217 tests, zero failures/skips, all canonical checks and
installed-wheel smoke passed. The initial 112-test result remains historical
PR #24 evidence; current results are recorded in the delta verification file.
The reviewed scope reconciliation permits #9 completion after owner review;
#10 integration is a later feature gate, not a reverse prerequisite for #9.

#10 owns OIDC validation, signed browser binding, digest/AEAD/HKDF adapters,
HTTP/cookie/CSRF handling, trusted ActorContext issuance, and login-only catalog
ensure/conditional-ready orchestration. Its full production query-site registry,
application authorization, browser/non-enumeration, and provisioning fault/race
matrix must accompany those implementations. The database tests here cannot
substitute for those public-port/browser journeys or close SEC-05.

SEC-01 remains open for cumulative runtime and catalog-provisioning evidence.
Deployed owner/runtime credential separation belongs to #16; cloud, privacy,
operational and production gates remain unchanged. No real user data or
production resources are used.
