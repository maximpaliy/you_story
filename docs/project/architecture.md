# Foundation Architecture

- **Status:** Proposed with partial human approval. The modular-monolith choice,
  module/database ownership boundaries, extensible catalog/history model, and
  tenant/future-sharing, authorization/RLS, and ADR-004 managed GCP/private-media
  architecture below are approved. ADR-006's staged first-increment scope and
  ADR-007's web identity/session architecture are also approved; first-increment
  architecture is complete while deferred feature and deployment decisions
  remain open. The foundation and later ADR additions passed independent
  architecture review; independent security review conditionally passed with
  open findings.
- **Scope:** Foundation design for GitHub Issue #1. This is not authorization to
  implement or deploy.
- **Requirements baseline:** `docs/project/product-definition.md`, including the
  owner clarifications through 2026-09-29.

## 1. Architectural goals and boundaries

Build a modular monolith with one authoritative HTTP API and relational
database. The MVP web application is the first client; Android and Telegram use
the same application services and versioned API later. The design optimizes for
strong tenant isolation, durable history, and modest operations rather than
premature distributed services.

The backend is Python with FastAPI, SQLAlchemy and PostgreSQL. It is divided
into modules (`identity`, `catalog`, `practice`, `media`, `reporting`) whose
domain and application layers do not import HTTP or GCP adapters. Transactions
may span modules in one database. Modules communicate through typed in-process
interfaces; no event broker is introduced for the MVP.

The web client uses server-rendered HTML with progressive enhancement so the
initial client remains within the approved Python technology constraint. A
REST/JSON API under `/api/v1` is the durable client boundary. A future Kotlin
Android client calls that API. A future Telegram adapter receives verified
webhooks and calls the same application services; it does not access the
database directly.

### Module and database ownership boundaries

The monolith is one deployable process, but it is not one undifferentiated code
or data layer. Each module owns its use cases, domain objects, repository
interfaces, tables, migrations and invariants. Only the owning module may read
or write its tables. Other modules call its typed application interface using
opaque identifiers. HTTP handlers orchestrate use cases but contain no domain
or persistence logic.

PostgreSQL uses a schema per module. Migration files are organized by owner and
may create or alter objects only in that schema, except for an explicitly
reviewed cross-module constraint. An owner-provided read model remains in the
owner schema and is exposed through the owner's public interface; it is not
permission for callers to issue cross-schema queries.

| Module / possible future service | Owns functions and behavior | Owns database objects | Allowed dependencies |
| --- | --- | --- | --- |
| `identity` / user management | Google identity mapping, users, tenants, sessions, preferences, account state and actor/tenant context | `identity.user`, `identity.external_identity`, `identity.tenant`, `identity.login_session`, `identity.user_preference` | No domain-module dependency; publishes authenticated actor/tenant context |
| `catalog` / catalog management | Sources, instruments, source definitions, catalogs, entries, hierarchy validation, characteristics, tags/goals and catalog grants | `catalog.source`, `catalog.instrument`, `catalog.source_definition`, `catalog.catalog`, `catalog.catalog_grant`, `catalog.entry`, `catalog.characteristic_definition`, `catalog.entry_characteristic`, `catalog.user_entry_customization` | Every privileged port accepts validated `ActorContext`; does not read identity tables |
| `practice` / session management | Practice-session lifecycle, practice records, content snapshots, statistics and calendar/history queries | `practice.session`, `practice.record`, `practice.content_snapshot`, `practice.statistic_value` | Accepts validated `ActorContext` and calls catalog's public query/validation ports; stores a stable catalog-entry ID plus its own immutable snapshot |
| `media` | Upload intent/finalize, attachment authorization, metadata lifecycle and object-key allocation | `media.upload_intent`, `media.attachment` plus objects in its private bucket namespace | Accepts validated `ActorContext` and calls practice's record-authorization port; never reads practice tables |
| `reporting` | Read-only aggregations and projections for history/statistics views | `reporting.*` projections only when measurement justifies persistence; otherwise no tables | Consumes owner-provided queries or versioned events; never becomes a second writer of domain data |

“Owns” is an architectural rule, not merely a folder convention. Shared ORM
models, a generic repository that exposes every table, and direct imports of
another module's domain or persistence packages are prohibited. Common code is
limited to technical primitives such as UUID/time types, transaction plumbing,
telemetry and validated actor context; it contains no catalog, session or user
business rules.

Each module has `<module>.public` for immutable request/response contracts and
port protocols; `<module>.application`, `<module>.domain` and
`<module>.infrastructure` are private. Delivery adapters and other modules may
import only `<module>.public`. The initial public ports are:

- identity: `ActorContextProvider`, `UserAccountCommands` and
  `UserProfileQueries`;
- catalog: `CatalogCommands`, `CatalogQueries` and `CatalogEntryValidator`;
- practice: `PracticeSessionCommands`, `PracticeHistoryQueries` and
  `PracticeRecordAuthorization`;
- media: `MediaCommands` and `MediaQueries`; and
- reporting: `ReportQueries` only.

Allowed domain edges are `practice -> catalog`, `media -> practice`, and
`reporting ->` owner query ports or versioned events. Delivery adapters may call
any public port. `ActorContextProvider` is called only by the authenticated
delivery/orchestration boundary, which passes an immutable `ActorContext` to
each privileged port; raw tenant UUIDs never confer authority. Catalog,
practice, media and reporting do not call identity persistence. No reverse edge
or cycle is allowed.

Architecture tests fail when a module imports another module outside its
`.public` package, application/domain code imports delivery code, a repository
maps a table outside its module schema, a migration changes another schema
without a registered exception, or dependency analysis finds a cycle. Contract
tests instantiate every public port against its owning module and verify that
tenant context and authorization cannot be omitted.

Cross-module workflows may use one database transaction while the modules are
co-deployed, but the application service must make the participating interfaces
and rollback semantics explicit. The referencing module owns any cross-schema
foreign key in its migration. The constraint requires approval from both module
owners and architecture review, is entered in a coupling register with its
purpose and removal condition, and never permits direct ORM navigation or
cross-schema querying. References between private resources include
`tenant_id + id` and use a tenant-consistent composite constraint where a
database constraint is retained; an ID-only relationship cannot establish
authorization. The constraint cannot be the only enforcement of a business
invariant. Stable UUID references, authorization at the owner interface and
snapshots allow it to be removed during extraction without changing public IDs
or history.

`ActorContext` can be constructed only by identity infrastructure after session
or token validation and contains provenance plus the internal actor and tenant;
request deserialization cannot construct it. Each owning use case still checks
the requested action and object. If extracted later, a service revalidates
authenticated user/service claims and does not trust forwarded context fields.

Persisted reporting projections are reporting-owned private resources: every
row has non-null `tenant_id`, RLS and fail-closed context; only a least-privilege
projector may write them. Their public query contracts define authorization,
freshness and revocation behavior. Deletion, export, backup, restore and
reconciliation cover projections just like source records.

Account deletion is an explicit idempotent orchestration: identity revokes login
access first; catalog, practice, media and reporting then execute their approved
deletion or de-identification actions and return durable evidence; identity
finalizes only after all owners succeed. Retry, partial failure, reconciliation
and post-restore reapplication remain required by SEC-02 and SEC-08 before this
workflow or production deployment.

## 2. Context, trust boundaries, and request flow

```text
Browser ---- Google OIDC ----> Google
   | HTTPS/session cookie
Android ---- Google OIDC ----> Google
   | HTTPS/bearer token
Telegram --> verified webhook ----|
                                  v
                         Cloud Run application
                         API + web + modules
                           |              |
                    private SQL      signed media URLs
                           |              |
                     Cloud SQL       Cloud Storage
```

Untrusted boundaries are every client, identity token, webhook, request field,
and uploaded/downloaded object. The application is the policy-enforcement
point. Cloud SQL and private Storage buckets are never client-addressable except
through short-lived, operation-specific signed media URLs.

## 3. Domain and persistence model

All mutable records use opaque UUIDs, timestamps, and an optimistic concurrency
version. PostgreSQL foreign keys, uniqueness constraints and transactions
enforce invariants; application validation provides useful errors. Times are
stored as UTC instants, with the user's IANA time zone captured for calendar
grouping.

### Identity and tenancy

- `User` is the internal identity and owns a `Tenant` (one personal tenant in
  the MVP). `ExternalIdentity(provider, subject, user_id)` maps Google's stable
  `sub`, never email, to the internal user.
- Every private aggregate carries a non-null `tenant_id`. Repository interfaces
  require tenant context and queries include it. PostgreSQL row-level security
  is enabled as defense in depth, with transaction-local tenant context; the
  runtime database role cannot bypass RLS.
- `Catalog(owner_tenant_id, visibility)` and `CatalogGrant(catalog_id,
  grantee_tenant_id, role)` exist from the first schema. MVP policy permits only
  `personal` visibility and an owning grant. Later shared catalogs activate
  existing visibility/grant semantics rather than changing storage shape.

### Source-neutral catalog

- `Source` identifies Yousician, Songsterr, or a future manually managed source.
  `Instrument` is reference data (initially guitar and piano).
- `CatalogEntry` represents an addressable content node with `catalog_id`,
  `source_id`, `source_definition_version`, `instrument_id`, optional
  `parent_entry_id`, stable `entry_type`, display name, sibling order, lifecycle
  state, and a constrained JSON metadata document. A
  same-catalog/source/instrument parent constraint prevents trees crossing
  boundaries.
- `SourceDefinition` is versioned configuration describing permitted node types,
  parent/child relationships, required typed fields, and statistic definitions.
  It is validated by source-specific policy code. JSON is an extension seam,
  not an unvalidated substitute for common columns.
- Here, **typed node** means that every entry carries an `entry_type`
  discriminator column whose meaning and allowed position are declared by the
  versioned `SourceDefinition` for that entry's source. Types belong to a source
  definition—not to an individual user's `Catalog`—and may additionally be
  constrained by instrument. For example, the Yousician definition declares
  `song`, `version`, and `fragment`, permits `song -> version -> fragment`, and
  requires `level` metadata on `version`. A Songsterr definition may declare a
  different vocabulary and parent/child graph. Persisted entries retain the
  definition version used to validate them so later definition changes do not
  silently reinterpret existing content.
- Yousician policy permits `song -> version -> fragment`; version requires
  `level`. Songsterr has an independently defined minimal hierarchy used in
  contract tests. Practice may target any node declared practiceable.
- `CharacteristicDefinition` is scoped by source/instrument/entry type;
  `EntryCharacteristic` and private `UserEntryCustomization` hold assignments,
  tags, goals, and user metadata separately from source catalog data.

### Practice and immutable history

- `PracticeSession(tenant_id, started_at, ended_at, local_date, time_zone,
  notes, status)` contains one or more `PracticeRecord` rows.
- A record references its live `CatalogEntry` when present, but also contains an
  immutable `ContentSnapshot` (source key/name, instrument, ancestor path,
  entry type/name and schema version). Catalog edits never rewrite snapshots.
- A record owns duration, notes, and zero or more typed `StatisticValue` rows.
  Each value records definition key/version, value kind (`integer`, `decimal`,
  `boolean`, `text`, `duration`, or `enum`), normalized value/unit, and display
  label. Validation occurs against the source definition current when recorded;
  the captured definition/version preserves interpretation.
- Catalog deletion is a tombstone while referenced; hard deletion is allowed
  only when no history or retention obligation exists. Account deletion is
  provisionally an auditable workflow that revokes identities, deletes media
  and direct identifiers, and replaces ownership with a non-login anonymized
  principal while retaining snapshots. This is **not approved for production**;
  the final erasure/retention/export policy is a deployment gate.
- Account-deletion behavior is not exposed in the first increment. ADR-006
  retains stable identities, account state and immutable history needed by the
  later lifecycle workflow; it does not claim that retained data is anonymous or
  activate the provisional workflow.

## 4. API and clients

First-increment REST resources expose catalogs, entries, sessions, records and
statistics. Media-intent resources are added only when the deferred media
feature and its security gates are approved. OpenAPI is generated and checked
into the review workflow.
Breaking changes require a new major path and human approval; additive changes
remain backward compatible. Cursor pagination, bounded filters, idempotency keys
on session creation (and later media creation), stable error codes,
ETags/`If-Match`, and ISO-8601
timestamps are part of the contract. MVP search uses indexed PostgreSQL
case-insensitive text plus tenant, source, instrument, type and ancestry
filters—no search service.

The web client uses an opaque, host-only `HttpOnly`, `Secure`, `SameSite=Lax`
cookie and a PostgreSQL-backed server session that stores only a one-way digest
of the bearer token. Sessions rotate at login, permit
independently revocable device/browser sessions, expire after 7 idle days or 30
absolute days, and require CSRF tokens for state changes. Android later uses
Authorization Code + PKCE and short-lived bearer tokens validated by the API.
Telegram accounts are not
implicitly trusted: an authenticated web flow issues a short-lived, one-use
linking code, after which the verified Telegram user ID maps to an internal
identity; webhook signatures/secret path, replay resistance and rate limits are
required. Offline writes and conflict synchronization are deliberately deferred;
Android can add a read cache without changing the API.

## 5. Authentication, authorization, and privacy

Google OpenID Connect uses Authorization Code flow with PKCE,
exact redirect URI allowlists, state, nonce, issuer/audience/signature/expiry
validation, and scopes `openid profile`; email is not requested or stored. An
allowlisted `(issuer, subject)` or a high-entropy, short-lived, single-use
invitation maps to an application-generated user UUID. Invitation consumption
and first-login creation of the user, personal tenant and external identity are
atomic and replay-safe. Email never identifies or links accounts. Provider
adapters preserve future identity-provider extensibility, and additional
providers require an explicit authenticated linking flow.

Every use case derives the user and tenant from validated server-side identity;
tenant IDs supplied by clients are ignored or rejected. Object authorization
checks ownership/grants for both parent and child resources. Signed URLs are
short lived, bind one object and operation, and follow an authorized media-intent
request. Logs exclude tokens, signed URLs, notes, statistic values and object
names. Secrets live in Secret Manager and service accounts have least privilege.
Administrative access, migration roles and runtime roles are separate and
audited.

Before implementation, an independent security specialist must threat-model
OIDC/session/token handling, CSRF, Telegram linking/webhooks, tenant/RLS rules,
IDOR, upload/download abuse, signed URLs, anonymization, secrets, IAM and supply
chain. Findings live in `docs/project/security-review.md` and linked GitHub
issues; severity, owner, due date, evidence, resolution, and any human-approved
exception/expiry must be recorded. Critical/high open findings block relevant
implementation or deployment.

## 6. Media

Media behavior is deferred from the first increment. ADR-006
retain the approved `media` schema ownership and stable `upload_intent` and
`attachment` metadata foundations so later support does not require an ownership
or identifier retrofit. No upload/download route, signed URL, worker or media
command is exposed until the media policy and SEC-03 gate are approved. The
first-increment runtime database role has no privileges on the dormant `media`
schema, and no media repository or command adapter is registered.

Metadata (`tenant_id`, record, object key, MIME type, size, checksum, state and
retention state) is relational; bytes use a private, uniform-access Cloud
Storage bucket. Upload is a two-step intent/finalize flow: authorize and reserve
an unpredictable key, issue a short-lived signed upload URL constrained by
content type/size, then verify object metadata/checksum before attachment.
Downloads require authorization and a short-lived signed GET URL. Objects are
quarantined until validation/malware policy succeeds.

Exact audio/video allowlists, size/duration limits, scanning/transcoding,
retention and regional placement remain human/security approval decisions.
Lifecycle jobs reconcile orphan uploads and deletion requests. Bucket
versioning/retention must align with the final privacy policy; it must not make
promised erasure impossible.

## 7. GCP deployment and operations

Use separate GCP projects for production and non-production, provisioned by
reviewed infrastructure as code. GitHub Actions runs checks, builds an immutable
container, produces dependency/SBOM and vulnerability evidence, uses Workload
Identity Federation (no service-account keys), and promotes the same digest.
Cloud Run hosts the stateless application; Cloud SQL for PostgreSQL uses private
connectivity, HA in production subject to cost approval, encryption and
automated backups/PITR; Cloud Storage holds media; Secret Manager holds secrets;
Artifact Registry holds images. Database migrations run as a dedicated,
single-execution release job before compatible application rollout and must be
expand/migrate/contract with tested rollback/forward recovery.

Structured JSON logs include request/correlation ID, route, status, latency and
non-PII actor/tenant pseudonyms. Cloud Monitoring/Error Reporting provide
latency/error/saturation metrics, migration and backup alerts, `/live` process
health and `/ready` dependency health. Audit logs cover IAM and data-plane
administration. Initial proposed objectives are p95 API latency under 500 ms
(excluding media transfer), 99.5% monthly availability, database RPO <= 24 hours
and RTO <= 8 hours. These are planning targets pending owner approval and load/
restore validation.

Daily automated database backups and PITR are enabled; restore drills occur at
least quarterly into an isolated project. Media protection uses versioning or a
backup copy only after reconciling erasure policy. Runbooks cover application
rollback, forward database repair, credential revocation, tenant-isolation
incident, media exposure and restore. Alerts route to an explicitly named
operator; deployment cannot precede identifying that operator.

## 8. Extensibility versus deliberate simplicity

Extension seams created now are provider identities, source policies and
versioned definitions, generic content trees, typed statistics, catalog grants,
instrument reference data, client-neutral application services, versioned REST,
and storage adapters. Each has an immediate requirement or prevents a known
backward-incompatible change.

Deferred are microservices, event buses, CQRS/event sourcing, GraphQL, search
clusters, automated catalog imports, sharing UI/moderation, offline mutation
sync, recommendations, transcoding pipelines, and multi-region deployment.
Adding a source means registering a definition/policy and tests, not adding
source columns to practice history. A source needing behavior the tree cannot
faithfully express triggers an ADR rather than progressively weakening JSON
validation.

Media behavior, account deletion and offline capabilities are also deferred from
the first increment under ADR-006. Stable foundations prevent disruptive later
changes, ordinary additive migrations remain allowed, and no speculative sync,
processing or deletion infrastructure is implemented.

### Future transition to services

Microservices are an extraction option, not the default target. Extraction is
justified only by measured needs such as independent scaling, availability or
release cadence; a clear team-ownership boundary; or isolation of a materially
different workload. Module size alone is not a sufficient reason. A new ADR and
independent architecture/security review are required before the first split.

The modular monolith must preserve the following seams so extraction remains
incremental rather than a rewrite:

- each module owns its domain model and persistence access; other modules use
  typed application interfaces and never query its tables directly;
- identifiers are opaque and stable across module boundaries, while API and
  source-definition contracts are versioned and compatibility-tested;
- cross-module calls and transaction boundaries are inventoried, and domain
  events describe completed business facts without committing the MVP to a
  broker;
- authentication produces a stable internal actor/tenant context, but every
  extracted service performs its own authorization rather than trusting a
  caller-supplied tenant ID; and
- logs, metrics and traces carry correlation identifiers that can later cross
  process boundaries.

The preferred migration is a strangler sequence:

1. Select one low-coupling boundary from production evidence. Media processing
   or reporting is likely safer than identity, catalog or practice, but the
   evidence at that time decides.
2. Make the module's synchronous contract explicit and add consumer/contract,
   authorization, failure and idempotency tests while it is still in-process.
3. Remove cross-module table access. Give the candidate exclusive ownership of
   its tables, initially in the same PostgreSQL instance if useful; shared
   reference data is accessed by API or replicated from versioned events.
4. Add a transactional outbox and idempotent consumers before introducing
   asynchronous delivery. Define ordering, deduplication, retry, dead-letter,
   replay, schema-version and retention behavior.
5. Deploy the extracted service behind an internal authenticated endpoint and
   route only the owning module's interface through it. Preserve the public
   `/api/v1` contract through the existing application/API gateway so clients do
   not change during extraction.
6. Move owned data with an expand/backfill/verify/cutover process. Prefer a
   single writer during transition; if temporary dual writes are unavoidable,
   specify reconciliation and rollback before enabling them.
7. Compare reads using shadow traffic that cannot perform externally visible
   mutations; validate writes with controlled replay, contract and parity tests
   against an isolated or dry-run destination. After isolation, load and failure
   tests pass, enable the new writer only at the governed cutover, observe, then
   remove the old path and tables in a later backward-compatible release.

Once separate processes are introduced, local ACID transactions no longer span
the boundary. Workflows must use explicit state machines and compensating
actions or sagas, accepting documented eventual consistency; distributed
transactions are not planned. Each service ultimately owns its datastore and
migrations, runtime identity, secrets, SLOs, alerts, runbooks and deployment.
Database foreign keys cannot cross service-owned stores; affected invariants
must move to owning-service commands, versioned local projections and periodic
reconciliation with explicit repair procedures. Events must minimize personal
data and define access, encryption, retention and deletion propagation before
they are persisted or replayed.
The platform must then add service-to-service authentication/authorization,
network policy, timeouts, bounded retries with jitter, circuit breaking,
distributed tracing, per-service backup/restore and coordinated incident
response. Tenant-isolation, deletion/export and restore tests must cover every
service and replicated copy.

The principal cost of extraction is therefore operational and consistency
complexity—not moving Python classes. Until its benefit exceeds that cost, the
modules stay in one deployable application and one transaction boundary.

## 9. Test-design handoff

The independent test-design phase must derive tests before production code:

- domain/property tests for permitted content trees, snapshots, statistic types,
  time zones and state transitions;
- integration tests with PostgreSQL/RLS proving cross-tenant reads and writes
  fail, including guessed IDs, joins and child resources; dormant media tables
  deny the runtime role, and architecture tests prove no media repository,
  command adapter or route is registered in the first increment;
- source contract fixtures for Yousician and structurally different Songsterr;
- OpenAPI compatibility and consumer tests for first-increment web flows;
  Android and Telegram consumer suites accompany those deferred clients;
- first-increment OIDC/session/CSRF tests; future token, webhook/linking and
  upload-abuse suites are designed with their deferred features;
- migration upgrade/rollback tests for the initial foundations; anonymization,
  deletion and media lifecycle tests are designed before those features;
- end-to-end calendar-to-history and content-to-history journeys;
- load tests against proposed latency targets, backup restore drills, readiness,
  alert and deployment rollback tests.

No first-increment production implementation starts until its applicable
architecture and security reviews, human approvals, test design, and independent
test review are recorded. Deferred capabilities repeat those gates when scoped.

## 10. Explicit answers to the 17 architecture questions

1. Common model: catalogs contain source/instrument-qualified content nodes;
   sessions contain records targeting nodes.
2. Source variation: versioned definitions, validated typed metadata and policy
   adapters—not Yousician columns in shared history.
3. Instrument variation: reference entities qualify entries, definitions and
   characteristics; one work may have distinct entries per instrument.
4. Ownership: tenant-owned catalogs, dormant visibility/grants, separate
   customizations, and separate history.
5. History: immutable snapshots and versioned statistics survive edits and
   tombstones.
6. Statistics: typed, optional values validated against versioned definitions.
7. Authentication: Google OIDC authorization code; web server sessions, Android
   PKCE/bearer tokens, explicit Telegram account linking.
8. Isolation: mandatory tenant context, service authorization, scoped queries,
   RLS defense in depth and adversarial integration tests.
9. Media: private object storage, authorized intents, short-lived signed URLs,
   validation/quarantine and lifecycle reconciliation.
10. API: versioned REST/OpenAPI over shared application services.
11. Deployment: immutable Cloud Run container, Cloud SQL, Storage, Secret
    Manager, Artifact Registry and GitHub OIDC CI/CD in isolated projects.
12. Operations: structured telemetry, alerts, backups/PITR, restore drills and
    incident/rollback runbooks.
13. Extensibility: only the named identity/source/catalog/client seams now;
    distributed and advanced capabilities are deferred.
14. New sources/instruments: configuration plus policy/contract tests, with ADR
    review when semantics exceed the common tree.
15. Security participation: threat modeling and architecture review now,
    security test input before code, change review, and pre-deployment signoff.
16. Approval: identity flows, authorization/RLS, Telegram linking, media access
    and validation, anonymization/retention, secrets/IAM and production topology
    require independent security approval.
17. Findings: the security review and linked issues record severity, ownership,
    evidence and resolution; exceptions need explicit human approval and expiry.

## 11. Human approval requested

Human approval status for the initial architecture gate:

1. **Approved:** Python/FastAPI modular monolith, PostgreSQL and versioned
   REST/OpenAPI, with the module/data boundaries in ADR-005. The owner's boundary
   condition is complete.
2. **Approved:** Generic, validated content tree and typed/versioned statistic
   model in ADR-002.
3. **Approved:** Tenant/catalog/grant shape, including dormant shared-catalog
   capability, in ADR-003.
4. **Deferred feature/deployment gate:** ADR-002 approves immutable historical
   snapshots. Account deletion is excluded from the first increment; tombstone
   behavior and the final privacy lifecycle remain pending before that feature
   or production use.
5. **Approved:** ADR-007 defines Google OIDC, allowlisted first login, internal
   identity and PostgreSQL-backed web sessions. Email is not collected. Android
   and Telegram identity designs remain deferred until those clients are scoped.
6. **Approved:** Tenant authorization plus PostgreSQL RLS defense in depth in
   ADR-003. SEC-01 and SEC-07 remain mandatory implementation gates; this
   architecture approval does not accept their risks.
7. **Deferred feature gate:** ADR-004 approves private Cloud Storage and the
   authorized signed-URL media flow. Media behavior is excluded from the first
   increment; the exact media policy remains pending before media implementation.
8. **Partially approved:** ADR-004 approves the managed GCP service selection,
   project separation, and keyless GitHub Actions foundation. The detailed
   migration strategy, production topology/HA, operator and meaningful cost
   envelope remain pending.
9. Proposed SLO, RPO/RTO, backup/restore and observability approach.
10. **Approved:** ADR-006 excludes offline writes, media behavior and account
    deletion from the first increment, retains stable foundations, and allows
    later additive migrations. Other complexity remains deferred as described in
    section 8.

The owner must separately resolve the final deletion/retention/export policy,
media limits/region, production operator and cost envelope before deployment.
Any rejection or material change returns this document and its ADRs to design
and independent review.
