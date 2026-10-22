# Issue #9 executable foundation design

Status: independently reviewed restricted foundation design (architecture,
security and test-design reviews passed). Issue #9 and SEC-01 remain incomplete
under the explicit approval boundary below.
Issue: https://github.com/maximpaliy/you_story/issues/9
Baseline: accepted ADR-005, ADR-006 and ADR-008; approved Issue #4 strategy
and Issue #5 tenant-isolation test design. This document adds no product policy,
privileged tenant-data migration facility or deployment authorization.

## Scope and approval boundary

Build a FastAPI process, Python package boundaries, PostgreSQL schema/migration
foundation, runtime-role context plumbing and automated checks. Only `GET /live`
and `GET /ready` are HTTP operations. No authenticated delivery adapter, identity
provider, catalog/practice use case, worker, media repository/adapter, login,
sharing, deletion, offline command or user-facing page is registered.

Issue #6's session/OIDC lifecycle and security/test reviews remain unfinished.
ADR-010 and Issue #8's consolidated authorization defaults remain pending human
approval. Their product behavior must not be inferred from this design. In
particular the foundation must not implement or grant access to incomplete
identity-bootstrap/session functions, issue credentials, fabricate authenticated
actors, or enforce proposed Yousician/statistic defaults as accepted policy.
The five identity control-plane tables may be created with deny-all runtime ACLs;
this is a schema foundation, not completion of ADR-008 bootstrap evidence.

ADR-008 requires those functions and their evidence in Issue #9. Their omission
therefore leaves Issue #9 and SEC-01 incomplete, even if the safe foundation
checks pass. The implementation record must explicitly list that gap and the
Issue #6 dependency; it cannot rename missing cases as passed or waive them.
No human decision is needed merely to prepare this already authorized subset.

## Package and process boundaries

Use `src/you_story/` with `identity`, `catalog`, `practice`, `media`, `reporting`
modules, each separating immutable `public` contracts from `domain`,
`application` and `infrastructure`. Unimplemented public ports remain protocols
or absent; they are never permissive default adapters. Shared code contains only
UUID/UTC, configuration, correlation, transaction plumbing and immutable actor
technical contracts. No common ORM base contains domain mappings or repositories.

Cross-module imports target `.public` only. Domain edges are practice to catalog,
media to practice, reporting to owner query ports; domain/application code may
not import delivery, FastAPI, SQLAlchemy or cloud adapters. Composition is outside
modules and may import private infrastructure only for explicit wiring; it must
not circumvent the public-port rule for use-case calls. There is no ORM
relationship or direct table query into a foreign module. Shared database code
may manage transactions but never implements domain queries.

A checked composition manifest contains only HTTP and the schema-only migration
entry point. The build checks source and packaged executable/entry-point
registrations, not just a hand-maintained list. No scheduler, task consumer,
provisioning callback or generic management command is allowed.

## Database foundation

Use Python 3.12, FastAPI, SQLAlchemy 2 Core, psycopg 3, pydantic-settings,
ruff/mypy/pytest and pinned PostgreSQL 17.6. SQL migration statements are
parsed using pglast for fail-closed ownership/classification checks. Use
SQLAlchemy QueuePool with DBAPI checkout/reset hooks: rollback first, RESET
the tenant GUC outside a transaction using temporary DBAPI autocommit, then
restore connection mode. Hook failure invalidates the connection. No startup
schema mutation is permitted. Use real PostgreSQL and psycopg/SQLAlchemy. Controlled bootstrap creates the
production-named `app_owner` and `app_runtime`; migrations authenticate directly
as owner. Runtime is non-superuser, non-owner, NOINHERIT, NOCREATEDB,
NOCREATEROLE, NOREPLICATION, NOBYPASSRLS and has no direct/transitive membership
or SET ROLE path to owner. Owner is privileged over its objects but has the
same restrictive role attributes except NOINHERIT is not required. Runtime
configuration accepts only its runtime credential; migration configuration is a
separate process input and never loaded into the HTTP application.

Revoke PUBLIC database CREATE/TEMP, public-schema CREATE and all application
schema/function privileges. Revoke runtime CREATE/TEMP; grant CONNECT and only
listed object privileges. Set per-creator owner default ACLs, especially revoke
PUBLIC function EXECUTE before any function is created. No dormant media
schema/table/sequence/function grant exists for runtime.

The initial inventory is checked and intentionally small:

| Owner | Objects/category | Required foundation |
| --- | --- | --- |
| identity | user, tenant, external_identity, invitation, login_session; exact five-table control plane | UUID user/tenant IDs, active/disabled lifecycle, separate catalog_pending/ready provisioning state, unique personal tenant owner, issuer/subject uniqueness, linked session user/tenant constraints, digest-only token columns; no runtime table access and no RLS exception beyond these five |
| identity | user_preference; private | tenant-consistent UUID identity reference, no direct control-plane access |
| catalog | source, instrument, source_definition; reviewed global reference inventory | stable IDs and immutable version binding; no proposed source-specific policy or seed behavior |
| catalog | catalog, catalog_grant, entry; private | non-null tenant UUID, stable IDs, unique personal catalog and owning grant shape, personal visibility only, tenant-consistent parent/child keys, stable source/version/instrument references as opaque IDs until approved reference migrations |
| practice | session, record, content_snapshot; private | stable IDs, non-null tenant UUID, same-tenant session/record/snapshot relations, opaque live-entry UUID, immutable snapshot storage foundation, UTC times and captured date/time-zone storage shape |
| media | upload_intent, attachment; dormant private | stable IDs, tenant-consistent local links, opaque record UUID, metadata foundation only, FORCE RLS and no runtime privileges |
| reporting | no tables | no speculative projection persistence |

Do not add global reference tables beyond the exact source/instrument/
source_definition manifest, characteristic/statistic policy, source-specific
definition content or proposed ADR-010 semantics merely to fill the future schema. Later additive migrations are explicitly allowed by ADR-006. Exact
columns/constraints are recorded in the checked schema manifest before migration
implementation and independently reviewed. No cross-schema foreign key is
introduced: cross-module references are opaque UUIDs validated through future
owner public ports. Adding a constraint requires the ADR-005 coupling register
and both owners' approval/review; no implicit exception is created here.

Every private table has a non-null `tenant_id`, ENABLE and FORCE ROW LEVEL
SECURITY and one explicit policy for app_runtime with matching `USING` and
`WITH CHECK` tenant equality. The dormant media tables have the same policy
shape but no runtime table/schema grant. The only global tables are the exact three catalog reference tables above;
runtime receives SELECT only, with no policy or seed behavior assumed.
The exact table/category/owner/policy/relationship/ACL inventory is reconciled
against PostgreSQL catalogs and fails on an unclassified object.

`identity.current_tenant_id()` is owner-owned, stable, security-invoker, fixed
`search_path`, schema-qualified and explicitly executable only by runtime. It
rejects missing, empty, whitespace, malformed and multiple UUID settings with
42501, returns only a valid UUID, and never invents a tenant. It is the only
runtime identity function in this subset. No security-definer function is
registered until its still-open lifecycle gate and independent review pass.

## Context and pool lifecycle

The technical immutable ActorContext cannot be deserialized from an HTTP field.
Its production issuance boundary belongs to identity infrastructure after
validated authentication. This foundation introduces no production issuer;
synthetic integration fixtures may construct a context through a clearly
non-production fixture boundary. Tests and architecture checks prohibit delivery
or domain construction. Calling code cannot supply a raw tenant to a repository
or receive a generic execute handle from the unit of work.

The unit of work checks out an idle connection, rolls back unexpected work,
resets session tenant context before beginning, then sets the actor-derived
canonical UUID using bound `set_config(..., true)` as its first transaction
statement. It immediately reads the parser function and verifies equality before
any repository operation. Commit, exception, cancellation and setup failure all
lead to rollback/reset or connection retirement. Check-in/checkout hooks defend
against injected session-level stale context. Cleanup failure retires rather
than returns the connection and emits only safe category/operation/role and
correlation fields. Nested same-context work reuses a transaction; different
actor/context nesting fails before SQL. Closed/autocommit use is rejected.

No production tenant-backed repository is implemented or registered in this
subset, and no production ActorContext issuer exists. The production statement
registry is empty for private operations and fail-closed: introducing any private
query/repository execution site fails architecture checks until its reviewed
registry and full matrix exist. No product repository is needed here. A scoped integration
probe is test-only and demonstrates both explicit actor-bound predicates and
independent RLS. If production repositories are added, each method/action/SQL
variant/private alias must be registered and pass semantic SQL-expression
inspection plus bind-provenance tests; raw/dynamic SQL is not an escape hatch.
The absence of such repositories must be mechanically asserted, not treated as
proof that the eventual full query-shape matrix passed.

## Migrations, development and recovery

Migrations are owner-organized and classified in a checked manifest. A controlled
runner orders security/bootstrap prerequisites and module-owned schema revisions,
records applied versions, and runs each revision transactionally. The initial
supported upgrade point is the checked security/bootstrap revision followed by
the module-table revisions; an empty database also reaches the same head. Both
are tested. Failed DDL must roll back its revision and retry safely; the runner
must not mark a failed revision applied. No data backfill, all-tenant scan,
RLS weakening, runtime elevation or domain callback is accepted.

Documentation supplies one reproducible dependency sync command and one
lint/type/unit/architecture/API/PostgreSQL check command. Tests require a
throwaway database and distinguish cluster-local fixture administration from
owner migration and runtime evidence. A container/local PostgreSQL alternative
must use the identical roles, migrations and assertions. No SQLite fallback or
silent skip is allowed. CI runs the same commands and preserves sanitized
reports. Production GCP resources and credential/IAM separation evidence remain
Issue #16 responsibilities.

## HTTP and errors

`/live` proves process liveness without touching PostgreSQL. `/ready` performs a
bounded actual connected-role (not DSN username), privilege and schema-version check and returns 503 when the
database is unavailable, credentials/role are wrong, or migrations are missing.
Neither exposes hostnames, SQL, credentials, tenant identifiers or exception
text. Correlation IDs are always application-generated UUIDs, reflected in every
response including errors; arbitrary incoming correlation values are not echoed. Stable errors contain safe code/message and
correlation ID. Unexpected errors produce a generic 500. OpenAPI is generated
and checked so only the two health operations are exposed; docs/redoc routes
are disabled. The approved issue scope authorizes the health operations; no
`/api/v1` product contract is introduced.

## Completion rule

Record exact revision, PostgreSQL/tool versions, commands, counts and independent
reviews. All implemented controls need positive and mutation/negative evidence.
SEC-01 stays open until the complete ADR-008 then-present foundation/bootstrap
matrix and independent security review pass. A partial implementation must
remain explicitly in progress and cannot close Issue #9 or unblock all dependent
feature issues.

## Reviewed initial column/constraint proposal

The following is the concrete schema review input. UUID columns are PostgreSQL
`uuid`, instants `timestamptz`, versions positive `bigint`, documents `jsonb`.
Unless marked optional, columns are non-null. Mutable rows have `created_at`,
`updated_at` and positive `version`; immutable published reference/snapshot rows
have `created_at`. IDs are application-generated UUIDs with no sequence grants.
A table's UUID `id` is primary key; every private parent additionally has unique
`(tenant_id,id)` to support its same-tenant child foreign keys. No live cross-owner
foreign key exists. These are storage foundations, not permission to register
commands or complete unfinished product policies.

| Table | Columns beyond common metadata | Constraints and access |
| --- | --- | --- |
| identity.user | id, state | state active/disabled; control-plane ACL only |
| identity.tenant | id, owner_user_id, state, provisioning_state | owner_user_id unique FK identity.user; state active/disabled; provisioning_state catalog_pending/ready; unique (id,owner_user_id) for session linkage |
| identity.external_identity | id, provider, subject, user_id, state | unique (provider,subject); FK user; state active/disabled; no email column |
| identity.invitation | id, token_digest bytea, issuer, expires_at, consumed_at optional, consumed_provider optional, consumed_subject optional, consumed_user_id optional | unique digest; consumed linkage FK user; consumed fields all absent or all present; no runtime privilege or redemption function |
| identity.login_session | id, token_digest bytea, user_id, tenant_id, issued_at, last_seen_at, absolute_expires_at, revoked_at optional | unique digest; FK user; composite FK (tenant_id,user_id) to tenant(id,owner_user_id); timestamps store lifecycle evidence only, duration policy deferred to #6; no runtime privilege/functions |
| identity.user_preference | tenant_id, id, user_id, settings jsonb | tenant-private; user_id opaque owner reference without navigation/control-plane read grant; unique (tenant_id,user_id); settings object; mutable metadata and FORCE RLS |
| catalog.source | id, key, name | key unique; runtime SELECT only |
| catalog.instrument | id, key, name | key unique; runtime SELECT only |
| catalog.source_definition | id, source_id, definition_version positive bigint, definition jsonb | FK source; unique (source_id,definition_version) and (id,source_id); object document; runtime SELECT only; no seeded/proposed source-specific behavior |
| catalog.catalog | tenant_id, id, visibility | visibility personal only; unique tenant_id (one personal catalog per tenant); mutable metadata; FORCE RLS |
| catalog.catalog_grant | tenant_id, id, catalog_id, grantee_tenant_id, role | composite FK (tenant_id,catalog_id) to catalog; grantee_tenant_id=tenant_id and role=owner; unique (tenant_id,catalog_id) ensures single owning grant; no sharing activation |
| catalog.entry | tenant_id, id, catalog_id, source_id, source_definition_id, instrument_id, parent_entry_id optional, entry_type, name, metadata jsonb, lifecycle_state | composite catalog FK; FK instrument and composite (source_definition_id,source_id) to definition(id,source_id); unique (tenant_id,id,catalog_id,source_id,source_definition_id,instrument_id) for composite parent FK to same columns; parent FK includes tenant/catalog/source/definition-version/instrument; CHECK parent_entry_id differs from id; lifecycle active/tombstone; object metadata; hierarchy/source practiceability policy deferred |
| practice.session | tenant_id, id, started_at optional, ended_at optional, local_date date, time_zone text, notes text, status text | storage for UTC instants/IANA zone name; no unapproved lifecycle defaults or transition behavior; mutable metadata; FORCE RLS |
| practice.record | tenant_id, id, session_id, catalog_entry_id uuid, duration_seconds optional numeric, notes text | same-tenant session FK; catalog_entry_id opaque and stable (no catalog FK); mutable metadata; FORCE RLS |
| practice.content_snapshot | tenant_id, id, record_id, schema_version positive bigint, content jsonb | same-tenant record FK, unique (tenant_id,record_id); object content; created_at only; runtime SELECT/INSERT only, no UPDATE/DELETE, pending approved record behavior; no user-visible snapshot writer |
| media.upload_intent | tenant_id, id, record_id uuid, object_key text, content_type text, size_bytes bigint optional, checksum text optional, state text, retention_state text | object_key unique; opaque record reference; metadata only, no bucket or object adapter; FORCE RLS but runtime no schema/table privileges |
| media.attachment | tenant_id, id, upload_intent_id, record_id uuid, object_key text, content_type text, size_bytes bigint optional, checksum text optional, state text, retention_state text | same-tenant upload-intent FK; unique (tenant_id,upload_intent_id); object_key unique; opaque record reference; runtime no schema/table privileges |

Tenant/private DML grants are explicit table grants only (subject to RLS); catalog
reference grants are SELECT only. Runtime gets no blanket future-table grant.
Snapshot UPDATE/DELETE denial is a storage guard, not a substitute for immutable
historical-meaning application tests in #14. Schema checks may constrain obvious
storage integrity (positive versions, JSON objects, nonnegative size) but must
not invent source definitions, statistic eligibility, session transitions,
authentication lifecycle or media policy. The schema manifest must preserve the
proposed-versus-approved distinction and be independently reviewed before code.

All private tables install an owner-local immutable-ownership trigger rejecting
changes to `tenant_id` and `id`; catalog_grant also freezes `catalog_id`,
`grantee_tenant_id` and `role`. Identity.tenant owner_user_id and all control-plane
identity associations have no runtime mutable privilege at all. Catalog entry
`source_definition_id` and `source_id` are immutable storage bindings, enforced
by an owner-local trigger; later approved moves/definition migration cannot
silently reinterpret them. These triggers are security-invoker, fixed safe
search_path and schema-qualified, have no public/runtime callable execute grant,
and perform no privileged data traversal. Snapshot runtime UPDATE/DELETE both
fail by ACL; future lifecycle/deletion policy requires its separate review.
The per-schema trigger implementation is migration-owned within its schema.

### Technical migration ledger exception

`foundation.schema_revision(version text PRIMARY KEY, checksum text NOT NULL)` is
an explicit technical (non-domain, non-tenant) manifest entry. It is owned by
app_owner; PUBLIC has no privileges; runtime receives only foundation schema
USAGE and this table SELECT for readiness, with no writes. It stores migration
metadata only and cannot contain user/tenant rows. Revisions are `000_security`,
`001_identity`, `002_catalog`, `003_practice`, `004_media`; supported upgrade
fixture is 000_security and head is 004_media. Readiness checks the exact applied
version/checksum set against packaged migration artifacts, not just connectivity
or a greater-than version comparison. Snapshot migration additionally installs
an owner-local immutable-row trigger rejecting UPDATE/DELETE, including attempted
owner row changes; schema migration authority does not authorize history rewrites.
