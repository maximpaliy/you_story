# Issue #9 foundation test design

Status: independent test-design review passed for the restricted foundation
subset; architecture and security design reviews also passed. Deferred cases
below remain blocking Issue #9/SEC-01 completion.
Design: [design.md](design.md); authoritative tenant matrix:
[Issue #5 test design](../issue-5/test-design.md).
All fixtures are synthetic and all destructive cases use a disposable database.

## Named suites and trustworthy oracles

| Suite | Positive and negative cases | Oracle |
| --- | --- | --- |
| F-01 Configuration/primitives | runtime-only DSN, invalid/wrong-role/missing settings, UUID round-trip, UTC-aware time, forbidden owner configuration in HTTP process | validated settings and role catalog checks; secrets excluded from repr/errors |
| F-02 HTTP | live without DB; ready at head; unavailable DB, wrong role, absent/old schema, bounded timeout; unknown route/method, validation and unexpected errors; server-generated correlation UUID even for attacker-supplied headers | actual ASGI requests, exact safe envelope/status/headers and checked generated OpenAPI; fake DB only for deterministic error injection, real PostgreSQL ready success/failure also required |
| F-03 Architecture | public-only permitted edges, no cycles, no delivery/persistence in domain/application, owner-only mappings and migrations, no media adapters/routes/repositories, no worker/executable/callback | parse full packaged/source import and registration inventory; mutation fixtures introduce each forbidden shape and must fail |
| F-04 Migration | empty-to-head; checked bootstrap-to-head supported fixture; replay; failure in each real revision before/after DDL/version mark; retry | direct owner authentication, PostgreSQL catalogs and applied-version state; failed revision absent, retry produces exact head inventory |
| F-05 Roles/ACL | runtime own-tenant success, owner isolation, PUBLIC/default ACLs, no object creation/TEMP, no direct/transitive owner reach or ALTER/GRANT/policy bypass, control-plane and media denial | reconnect as app_runtime; effective privilege queries plus attempted commands; catalog assertions for exact ACLs and function search paths |
| F-06 Parser/context | valid UUID, missing/empty/whitespace/malformed/multiple values; setup mismatch; context set first and read back before query | real parser and transaction statement capture; direct empty-table scans need not evaluate parser, UoW preflight always does |
| F-07 Tenant matrix | every then-present private table: A create/read/update/delete/list/count versus B and missing context, WITH CHECK rejection, local composite-child and ancestry mismatch; dormant media denied even for own tenant | app_runtime direct/test probe statements with explicit predicates, independent predicate-free RLS probes and catalog constraints; post-failure privileged fixture verifies both tenants unchanged |
| F-08 Pool/transactions | commit, domain/database exception, cancellation, setup/reset failure, closed use; A to B to no context same backend; injected session stale setting and open/failed transaction; nested same actor success/different actor failure; concurrent randomized tenants over small pool | PID and statement capture, deterministic fault injection, connection-retirement assertion and complete postconditions; record failing seed |
| F-09 SQL/provenance | scoped test probe passes; removed/wrong predicate, wrong alias and unanchored equality fail expression oracle; context construction/issuance and delivery forgery negatives | SQLAlchemy expression tree or PostgreSQL AST and actual bind provenance before execution; regex or RLS rewritten EXPLAIN is insufficient |
| F-10 Inventory/mutations | extra table/control-plane exception, weakened USING/WITH CHECK, wrong owner/grant, ID-only local child relation, foreign-schema mapping/migration, media registration, unregistered process/root | mechanical manifest-to-catalog/package reconciliation; mutate each control independently and require failure even while other layers remain intact |
| F-11 Telemetry | missing/invalid/mismatch/cleanup failure, database error, secret/tenant/content sentinels | positive sentinel first establishes enabled capture; safe category/correlation/role/operation present, prohibited raw SQL/token/content/UUID absent; reset failure emits safe retirement signal |

Each private table/action has an executable registered case; a new table without
coverage fails reconciliation. Tables denied entirely to runtime are tested for
ACL denial instead of falsely claiming own-tenant DML. Test-probe SQL is clearly
separated from production repository inventory and never imported by the app.
Every declared mutation has a positive baseline: a detector that rejects all
input is not acceptable. Migration ownership parsing may fail closed on complex
unknown statements; it cannot silently approve them.

## Required SQL and composition gate

The private-operation production statement registry is empty and a mutation
adding an unregistered repository/private SQL site must fail. This subset has no
production private SQL execution or production ActorContext issuer. If any
production repository is introduced, TD-03 and TD-10 become mandatory in
full for its emitted shapes: all private aliases, child/join/count/page/bulk
branches, CTE/subquery/union/loaders and write/upsert variants, with a checked
statement-site registry and actor-bind provenance. A test-only simple probe
cannot establish that coverage. Foundation checks must assert the actual absence
of unregistered repositories and raw SQL call sites.

Build/import the packaged artifact and reconcile executable registrations,
container commands, CLI/module entry points and migration callbacks with the
HTTP/schema-migration-only manifest. Mutations add differently named workers,
consumers, scheduled tasks and callbacks so name-based absence checks cannot
pass. No HTTP product operation may be registered; a media operation mutation
must fail generated OpenAPI and registration checks.

## Bootstrap/lifecycle gate and honest gaps

ADR-008/TD-11 requires identity lookup/invited bootstrap/session functions,
non-enumeration, concurrent consumption and provisioning evidence in Issue #9.
Issue #6 still blocks session/authentication implementation. This subset tests
exact five-table control-plane shape, tenant-private user_preference, three-table
global-reference inventory and total runtime control-plane denial, but does not
implement, grant or claim functional evidence for unapproved bootstrap/session
functions. No placeholder passing tests represent that missing behavior.

The evidence record must list TD-11 functional cases, catalog-provisioning public
command/ready transition and their fault/concurrency/HTTP cases as unimplemented
and blocking Issue #9/SEC-01 completion. Likewise full product authorization,
query-shape, non-enumeration and browser journeys remain their approved later
slices; current health-only HTTP checks prove their absence, not their success.
SEC-05/SEC-07 are not closed by foundation schema tests.

## Environments and evidence

Use supported pinned PostgreSQL with actual `app_owner` and `app_runtime`,
production migrations and a bounded one-connection test pool. Owner setup results
are never isolation evidence. Cluster-local administration provisions the
throwaway database/roles only; runtime checks authenticate directly as runtime.
No credential values, raw invitation/session tokens or DSNs enter reports.

CI must fail when required PostgreSQL configuration is unavailable; a unit-only
command may remain useful locally but cannot claim the integration gate passed.
Record command, commit, PostgreSQL and tool versions, role, pool settings,
pass/fail/skip counts, minimized seed and sanitized artifact references. Required
cases cannot be silently skipped or retried to green. Security and independent
code review assess the final evidence and its gaps before any completion claim.

## Exact storage integrity controls

The design's initial column/constraint proposal is the schema oracle and is
reconciled column-by-column, FK-by-FK, trigger-by-trigger and ACL-by-ACL with the
checked implementation manifest and real catalogs before schema code can pass.
F-07 attempts existing-row tenant/id mutation, catalog owner-grant tenant/role/
catalog mutation, entry source-definition rebinding and snapshot UPDATE/DELETE.
All fail without mutation; positive controls prove permitted mutable metadata
can change. F-10 removes each immutability trigger/ACL restriction and removes
source/version from the parent composite key; detector must fail even when RLS
remains intact. Global definition UPDATE/DELETE is denied to runtime.

The exact technical exception is foundation.schema_revision(version PK, checksum),
owned by app_owner with runtime SELECT only. F-04/F-05 reject other foundation
objects/privileges, altered/unknown/missing ledger checksum or revision, and
runtime ledger writes. F-02 readiness succeeds only at exact packaged head
004_media, including all predecessor checksums. The declared supported upgrade
point is 000_security; no nonexistent deployed release upgrade is claimed.
