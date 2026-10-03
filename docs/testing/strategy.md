# First-Increment Test Strategy

- **Status:** Approved by the human owner on 2026-09-30
- **Applies to:** GitHub Issue #4 (`MVP-01`) and the first increment defined in
  `docs/project/product-definition.md`
- **Architecture baseline:** `docs/project/architecture.md` and accepted
  ADR-001 through ADR-007
- **Security baseline:** `docs/project/security-review.md`
- **Last updated:** 2026-09-30

## 1. Purpose and release rule

This strategy defines the evidence required before first-increment production
code can be considered correct enough to merge or deploy. It covers the web
client, versioned HTTP API, modular-monolith application, PostgreSQL data and
RLS, Google OIDC/server sessions, non-production GCP delivery, and operational
controls. It is a test design, not evidence that any control already works.

No affected production implementation starts until its requirements and design
are explicit, its issue-level tests have been designed and independently
reviewed, and every applicable pre-implementation security gate is cleared.
Passing tests never overrides an open human approval, security finding, failed
review, or known defect. A release candidate cannot advance while a required
check is skipped, flaky, silently retried to green, or run against a materially
different environment without a documented and approved reason.

## 2. Scope

### 2.1 In scope

- Google OIDC for allowlisted users, internal identities and tenants,
  PostgreSQL-backed browser sessions, logout, CSRF, browser security headers,
  and output encoding;
- personal catalogs for guitar and piano, a user-facing Yousician definition,
  validated content hierarchy, search/navigation, characteristics, tags, and
  goals;
- calendar sessions, practice records, immutable content snapshots, optional
  typed statistics, and calendar-to-history/content-to-history navigation;
- module and database ownership rules, PostgreSQL migrations and constraints,
  fail-closed tenant context, authorization, RLS, dormant sharing foundations,
  and inaccessible dormant media foundations;
- `/api/v1` contracts, server-rendered web flows, health/readiness behavior,
  structured privacy-safe telemetry, bounded resource use, and basic
  accessibility and performance;
- immutable artifact creation, non-production GCP delivery, and the separately
  gated production-readiness, backup, restore, rollback, and operational checks.

### 2.2 Explicitly deferred

Media behavior, account-deletion behavior, offline synchronization, Android,
Telegram, sharing activation, community contribution, automated imports,
additional user-facing sources, recommendations, advanced analytics,
microservices, event brokers, dedicated search infrastructure, transcoding and
multi-region deployment are not first-increment test targets.

Tests do verify that media repositories, command adapters and routes are absent,
that the runtime role cannot access dormant media tables, and that sharing
cannot be activated. Songsterr appears only as a structurally different source-
policy contract fixture. Deferred feature suites must be designed and reviewed
when those features are scoped; placeholder passing tests are not substitutes.

## 3. Quality risks and priorities

Priority is based on impact, likelihood and ability of a lower-level check to
miss the failure.

| Priority | Risk | Required primary evidence |
| --- | --- | --- |
| P0 | Cross-tenant disclosure or mutation through direct access, joins, children, search/counts, guessed IDs, stale pooled context or role bypass | PostgreSQL integration tests with two tenants, real RLS/roles and adversarial requests |
| P0 | Authentication/session takeover through invalid OIDC, login CSRF, fixation, replay, unsafe redirect, expiry or incomplete logout | Provider-boundary tests, application integration tests and browser security journeys |
| P0 | Stored/reflected XSS, CSRF or mass assignment through user/source fields | Browser and HTTP negative tests generated from the authorization matrix |
| P0 | Confirmed practice history loses meaning after catalog or definition evolution | Domain properties plus migration/integration and end-to-end history journeys |
| P1 | Incorrect hierarchy, statistic type, time-zone/local-date or lifecycle behavior | Domain examples and generative/property tests with persistence checks |
| P1 | Migration, deployment, rollback or restore loses/corrupts data | Empty/upgrade migration tests and isolated non-production operational exercises |
| P1 | Secrets, notes, statistics, tokens or identifiers leak into telemetry | Canary-data integration and non-production telemetry inspection |
| P1 | Contract changes break current or planned clients | Checked OpenAPI compatibility and consumer-facing contract tests |
| P2 | Slow/unbounded calendar, search or history behavior | Query-plan/bound tests and representative non-production load checks |
| P2 | Web flows exclude keyboard or assistive-technology users | Automated accessibility checks plus focused manual keyboard/semantic review |

P0 failures block merge. P1 failures block the affected issue unless the human
owner accepts a documented security or operational risk through the applicable
process. P2 failures block when an approved acceptance threshold is missed; an
unapproved threshold cannot be waived by the implementation author.

## 4. Test levels and responsibilities

### 4.1 Domain example and property tests

Fast deterministic tests exercise domain rules without HTTP or cloud adapters.
They cover:

- allowed and forbidden Yousician trees; same catalog/source/instrument ancestry;
- a structurally different Songsterr definition through the same policy contract;
- source-definition versions, required metadata and practiceable node rules;
- statistic kinds, units, enum domains, absence of values and invalid values;
- session/record lifecycle state machines and optimistic versions;
- UTC instants, IANA zones, local dates, DST gaps/folds and date boundaries;
- immutable snapshot construction and rendering after live catalog evolution;
- idempotency-key scope and same-key/same-payload versus same-key/different-
  payload behavior.

Property generators must constrain inputs enough to reach valid and invalid
states intentionally, record reproducible seeds on failure, and retain minimized
counterexamples in CI output. Example tests remain for named business cases so
properties do not obscure product meaning.

### 4.2 Application/use-case tests

Use public application ports with in-memory fakes only where database behavior
is irrelevant. Verify command/query orchestration, allowed state transitions,
explicit transaction rollback, owner-port calls, immutable `ActorContext`,
stable errors, ETag/`If-Match`, pagination bounds and idempotency decisions.

Fakes must not be used as evidence for SQL constraints, repository scoping,
transactions, isolation, migrations, locking, RLS, pooled connections or query
performance. Every authorization decision is also exercised through the real
repository and HTTP boundary.

### 4.3 PostgreSQL integration and isolation tests

These tests use a supported PostgreSQL version with the production migrations,
runtime role, migration role, grants, `FORCE ROW LEVEL SECURITY`, transaction-
local context and connection-pool behavior. SQLite and owner/superuser
connections cannot satisfy this layer.

For every private resource/action in the approved authorization matrix, create
Tenant A and Tenant B data and verify:

1. allowed create/read/update/list/search/count behavior for the owner;
2. denial without revealing existence for another tenant's direct or guessed ID;
3. denial through parent/child endpoints, ancestry filters, joins and cursors;
4. rejection of client-supplied tenant/owner/visibility fields and immutable
   ownership changes;
5. failure when tenant context is absent, malformed, set outside a transaction,
   or stale after a pooled connection is reused for another tenant;
6. runtime-role inability to alter policy, set privileged context, bypass RLS,
   access migration ownership, activate sharing, or access dormant media tables;
7. background-job/worker entry either constructs validated transaction-local
   tenant context through the approved mechanism or fails closed before querying;
   if no worker exists, composition/API checks prove its absence and adding one
   activates this test gate;
8. rollback of every participating module when a cross-module workflow fails.

Cross-tenant non-enumeration compares an existing foreign-tenant resource with a
same-shaped nonexistent identifier. Stable status and error schema, permitted
headers/redirects, list counts, cursor behavior and response-size class must be
equivalent; bounded timing distributions are compared where the endpoint's work
could reveal existence. The oracle is applied through HTTP/browser paths and
owner public ports/repositories rather than checking only a status code.

Tests must query through both repository/public-port and HTTP paths. Direct SQL
is used only to arrange fixtures with the test/migration role or to assert policy
effects that application APIs cannot observe. A failing context setup must fail
closed before domain queries execute.

### 4.4 Migration and data-evolution tests

For each migration series:

- create an empty database, migrate to head and validate schemas, owners, grants,
  constraints, indexes and policies;
- start from every supported release/fixture, migrate forward, run invariants
  and application smoke tests, and verify identifiers and history;
- test expansion with the old compatible application, migration/backfill and the
  new application before any contract step;
- inject interruption/failure at documented points and prove retry or forward
  repair is safe; exercise rollback only where the migration declares it safe;
- verify catalog rename/restructure/definition change/tombstone does not rewrite
  historical snapshots or invalidate statistic interpretation;
- detect a module migration touching another schema unless its reviewed coupling
  exception is registered.

A checked manifest names every supported starting schema/application fixture.
CI fails when a manifest entry has no upgrade case or when a migration changes
the manifest without review; “every supported release” is never inferred from
whichever fixtures happen to exist.

Schema snapshots alone are insufficient. Migration evidence includes data
fixtures, before/after invariant checks, role/policy checks and the exact source
and container/database versions.

### 4.5 Architecture tests

Automated checks fail for:

- imports of another module outside its `.public` package;
- application/domain imports of delivery or infrastructure adapters;
- repository mappings or ordinary migrations outside the owning schema;
- dependency cycles or forbidden reverse edges;
- shared domain ORM models or generic repositories exposing multiple modules;
- privileged public ports that omit validated `ActorContext`;
- runtime composition that registers file/upload/blob/media storage behavior;
- any route or OpenAPI operation outside the reviewed first-increment allowlist,
  including generically named file/upload endpoints; and
- runtime database privileges on dormant media objects, established from catalog
  inspection rather than class/file naming.

Runtime negative HTTP tests exercise plausible file, upload, blob and media paths
and methods against the fully composed application, including catch-all/dynamic
handlers and middleware. They must produce the same bounded unknown-route/method
behavior as unrelated nonexistent paths and cause no authorization, persistence,
object-storage, signed-URL or other feature side effect.

Public-port contract suites instantiate each implementation and prove required
context, authorization and transaction behavior cannot be omitted.

### 4.6 HTTP API and contract tests

The checked/generated OpenAPI document is compared on every change. Tests cover
the approved `/api/v1` resources, JSON and content types, ISO-8601 timestamps,
stable error codes, cursor pagination, filter bounds, ETags/`If-Match`,
idempotency and rejection of unknown or immutable security-sensitive fields.

Breaking changes require a new major path and human approval. The compatibility
check treats removal, incompatible type/format changes, newly required inputs,
changed security requirements, narrowed enums and changed response semantics as
breaking. Additive changes still require a reviewed consumer example and tests.
The server-rendered web client is the first consumer. Android and Telegram
consumer suites are created only when those clients enter scope.

Malformed JSON, duplicate/ambiguous values, unsupported methods/media types,
oversized fields, pagination abuse, injection strings, encoded path variants,
stale cursors and unauthorized resources receive bounded, non-sensitive errors.

### 4.7 Identity, session and browser-security tests

OIDC tests use a deterministic fake provider boundary and cryptographic fixtures;
one separately controlled non-production smoke test may use Google's real
provider without placing credentials or tokens in recorded artifacts. Fake-
provider tests cannot prove deployed Google consent-screen, client-ID or exact
redirect configuration, so reviewed environment/configuration assertions are
mandatory before exposure even when a live-provider smoke is unavailable. Cover:

- state, nonce and PKCE generation, binding, one-use behavior and expiry;
- issuer, audience, signature, algorithm, subject and time-claim validation,
  including key rotation and provider/network errors;
- exact redirect allowlists, error redirects, login CSRF and replay;
- allowlisted provisioning/invitation atomicity, simultaneous consumption,
  issuer/subject uniqueness and refusal to identify/link by email;
- opaque session entropy and digest-only persistence, rotation on login,
  fixation resistance, independent revocation, 7-day idle/30-day absolute
  expiry and logout invalidation;
- host-only `Secure`, `HttpOnly`, `SameSite=Lax` cookie attributes and the final
  approved name/path/domain;
- CSRF token binding/rotation, origin/content-type rules, same-site and cross-
  site state-changing requests;
- the SEC-05 decision in Issue #6 (`MVP-03`) classifying every first-increment
  destructive action and verifying reauthentication wherever required. Account
  deletion is absent and adding it activates a new reauthentication design and
  tests; Android bearer-token lifecycle and mobile redirect interception remain
  deferred until that client is scoped;
- framework escaping, CSP and approved security headers, plus stored/reflected
  probes in names, notes, tags, goals, metadata and validation errors.

Sensitive values must be synthetic, unique canaries. Failure output, screenshots,
HTTP archives and traces are scanned before retention and must not contain live
tokens, cookie values, invitation secrets or provider credentials.

### 4.8 Server-rendered browser journeys

Browser tests run the real application against PostgreSQL and cover:

1. allowlisted sign-in to authenticated home and logout;
2. create and find a guitar/piano Yousician song, version and fragment;
3. assign a characteristic and maintain private tags/goals;
4. choose an IANA time zone, navigate to a local day, create/edit a session and
   observe idempotent/stale-write behavior;
5. add multiple practice records with duration, notes, no statistics and typed
   statistics;
6. **calendar to history:** day -> sessions -> records -> captured statistics;
7. **content to history:** content -> all authorized historical records;
8. rename/restructure/tombstone live catalog data and confirm both history
   journeys still show the original immutable snapshot;
9. render accessible empty, validation, authorization and concurrency states.

Journeys validate user-visible outcomes and persisted state, not CSS selectors
alone. Stable roles/labels or explicit test identifiers are used. Tests do not
stub application ports; only the external OIDC boundary is replaced. At least
one two-tenant browser/API scenario proves that navigation and existence signals
do not cross tenants.

### 4.9 Accessibility tests

Each new page runs automated semantic/color/name checks and focused keyboard
tests for logical focus order, visible focus, form labels/instructions/errors,
heading/landmark structure, table/list semantics and status/error announcement.
The two history journeys receive manual keyboard and one screen-reader smoke
review before first production promotion. Automated tooling does not constitute
complete accessibility evidence; manual results name the browser, assistive
technology/version, reviewer and limitations.

### 4.10 Performance and abuse-resistance tests

Until the owner approves a different target, the architecture's proposed p95
API latency under 500 ms is planning input, not a silently accepted SLO. Issue-
level tests always enforce deterministic query/request/pagination bounds.
Non-production load tests use representative catalog/history sizes and mixed
calendar, search, history and write traffic, reporting p50/p95/p99 latency,
error rate, throughput, database connections, CPU/memory and slow queries.

Adversarial cases cover oversized inputs, deep/invalid hierarchy, expensive
filters, cursor cycling, repeated login, write bursts, concurrent stale writes,
idempotency replays and per-IP/account/tenant limit separation. Tests verify
timeouts, backpressure and safe `429`/bounded errors without cross-tenant keys.
Final thresholds and capacity assumptions must be approved before public
exposure under SEC-11.

### 4.11 Delivery, observability and recovery tests

Non-production evidence covers:

- immutable action references, minimal workflow permissions, restricted WIF
  claims, least-privilege service accounts and negative IAM cases;
- locked/hashed dependencies, secret/source/dependency/image/IaC scans, SBOM,
  artifact signature/attestation and promotion of the identical digest;
- single-execution migration job, compatible rollout, failed migration,
  application rollback and forward database repair;
- `/live` process and `/ready` dependency semantics during healthy, starting,
  database-failed and draining states;
- metrics, error reporting and alert delivery for latency, error, saturation,
  migration and backup conditions;
- allowlist-based structured telemetry and keyed pseudonyms, with canary secrets,
  tokens, signed-looking URLs, notes, statistic values, object names and PII-like
  text asserted absent from logs, traces and error payloads;
- isolated backup/PITR restoration, application invariant verification and
  teardown. Production retention and deletion reconciliation remain gated by
  SEC-02 and SEC-08.

Operational exercises identify operator, environment, source revision, artifact
digest, timestamps, expected/actual outcome and follow-up. A runbook existing on
disk without an observed exercise is not recovery evidence.

Every telemetry absence check first emits a benign unique sentinel and observes
it in each enabled sink (application logs, traces, error reporting, alert
payloads and uploaded CI artifacts where applicable). Only then may it assert
that paired sensitive canaries are absent. Evidence records bounded polling and
flush timeouts, inspected time window, revision/digest, sink/query and ingestion
lag. A missing sentinel, timed-out flush or uninspected enabled sink makes the
test inconclusive and failing rather than “clean.”

## 5. Fixtures and test data

### 5.1 Canonical source fixtures

The fixture set is versioned with tests and intentionally small:

- Yousician definition v1 declares `song -> version -> fragment`, requires
  `level` on version, marks selected nodes practiceable, defines at least one of
  each statistic kind used by the product, and supplies guitar/piano cases;
- Yousician definition v2 changes display metadata and one statistic definition
  version so preservation of v1 history can be proved;
- Songsterr contract fixture uses a different node vocabulary/parent graph and
  no Yousician-only assumptions; it is never exposed as a first-increment user
  integration;
- invalid definitions include unknown type, forbidden parent/child pair,
  cross-instrument ancestry, missing required metadata, bad enum/unit and
  incompatible definition evolution.

### 5.2 Tenant and history fixtures

Every integration suite can create two personal tenants with deliberately
similar names and disjoint UUIDs. Each has a catalog, entries, customizations,
sessions on DST and date-boundary cases, records with/without statistics and a
tombstoned entry. IDs are generated, never sequence-assumed. A third no-context
case exists for fail-closed tests.

All test accounts, issuer/subject values, notes and telemetry canaries are
synthetic and recognizable. Production data, copied production backups and real
Google tokens are prohibited in developer and CI tests.

### 5.3 Isolation and cleanup

- Unit/property tests share no mutable global state and control clock/randomness.
- PostgreSQL tests use a database/schema isolation approach proven compatible
  with role/RLS behavior; each test begins from known migrations and rolls back
  or destroys its data without masking committed-transaction behavior.
- Browser tests use unique users/tenants and idempotency keys per test and may
  run in parallel only after collision tests pass.
- Cloud tests use isolated non-production resources labelled with run/revision
  and bounded TTL cleanup. Cleanup failure is visible and alerts; it is not
  swallowed in teardown.

## 6. Requirements and security traceability

The GitHub issue remains the workflow unit. Its work record links detailed test
cases and evidence. The matrix below states the minimum suite, not every case.

| Requirement / risk | Owning backlog issue(s) | Minimum evidence |
| --- | --- | --- |
| Reviewed first-increment strategy | #4 / MVP-01 | This strategy, independent review and human approval |
| Tenant/RLS mechanism; SEC-01 | #5 / MVP-02, #9 / MVP-06 | Reviewed design; real-role PostgreSQL adversarial suite; pool/missing/job context and bypass cases; security re-review |
| OIDC/session lifecycle; SEC-05 | #6 / MVP-03, #10 / MVP-07 | Reviewed protocol/reauth decisions; identity/session unit, integration and browser negative tests; security re-review |
| CSRF/XSS/browser policy; SEC-06 | #7 / MVP-04, #10-#15 / MVP-07-MVP-12 | Reviewed controls; header, origin, token, encoding and stored/reflected browser tests |
| Deny-by-default authorization; SEC-07 | #8 / MVP-05, #10-#15 / MVP-07-MVP-12 | Complete action matrix; generated HTTP/DB IDOR, child, join, count, non-enumeration and mass-assignment tests |
| Module/data boundaries and dormant media | #9 / MVP-06 | Architecture/port tests; migration ownership; composition/API allowlist; runtime privilege inspection |
| Multi-user identity and Google login | #10 / MVP-07 | Atomic provisioning, issuer/subject mapping, invitation concurrency, logout/expiry and two-user isolation |
| Instruments, Yousician catalog, extensible sources and search | #11 / MVP-08 | Definition/hierarchy properties, Yousician journey, Songsterr policy fixture, bounded filter/search and evolution tests |
| Characteristics, private tags and goals | #12 / MVP-09 | Scope validation, ownership/mass-assignment, API/browser and cross-tenant tests |
| Calendar sessions | #13 / MVP-10 | Time-zone/DST/local-date properties, lifecycle, concurrency, idempotency and daily browser journey |
| Practice records, snapshots and statistics | #14 / MVP-11 | Typed/optional statistic properties, transaction rollback, immutable snapshot/evolution and tombstone tests |
| Both history directions | #15 / MVP-12 | Named end-to-end journeys; bounded queries; changed/tombstoned catalog; list/count/join isolation |
| Supply chain; SEC-09 | #16 / MVP-13, #18 / MVP-15 | WIF/IAM negatives, scans, SBOM, attestation/digest verification and vulnerability disposition |
| Telemetry privacy; SEC-10 | #17 / MVP-14, #18 / MVP-15 | Positive-control canary redaction across all sinks, pseudonym/access/retention review and production evidence |
| Abuse/resource bounds; SEC-11 | #11, #13, #15, #17, #18 / MVP-08, MVP-10, MVP-12, MVP-14, MVP-15 | Bound/limit/idempotency tests, representative load and alert evidence |
| Privacy/deletion/backup policy; SEC-02 and SEC-08 | #18 / MVP-15 | Human-approved inventory/policy; restore/deletion reconciliation and security review before real data |
| Production deployment/recovery | #18 / MVP-15 | Approved topology/operator/cost/SLO/RPO/RTO; smoke, isolation, restore, rollback and promoted-digest evidence |
| Media security; SEC-03 | Deferred | Absence/denial tests now; full threat model and abuse suite before media implementation |
| Telegram security; SEC-04 | Deferred | No endpoint/linking behavior now; full authenticity/replay/linking suite when scoped |
| Email minimization; SEC-12 | #10 / MVP-07 | Scope/request/storage tests proving email is neither requested nor persisted |

Product requirements not repeated row-by-row are covered through their owning
vertical slice and the two end-to-end journeys. Before implementation, each
issue refines this matrix into named tests for its clarified acceptance criteria.
Any requirement with no test or justified manual evidence is a design gap and
blocks that issue.

### 6.1 Exhaustive first-increment requirement traceability

The stable IDs below are local test-requirement identifiers derived from the
numbered product-definition sections. They prevent broad feature rows from
hiding an unverified requirement. “Design assertion” means a reviewed static or
architecture/composition check; it is not a claim based only on prose.

| ID / product area | Disposition and owner | Named verification |
| --- | --- | --- |
| R-02-IDENTITY — Google login, internal ID independent of email, provider seam, multi-user private preferences/data | In scope: #6/#10 (MVP-03/MVP-07) | OIDC/session suite; issuer/subject and no-email persistence; provider-port contract; two-tenant journeys |
| R-03-INSTRUMENT — guitar/piano and extensible instrument reference data | In scope: #11 (MVP-08) | seeded-reference migration checks; catalog/property cases for both instruments; unknown/incompatible instrument negatives |
| R-04-SOURCE — source-neutral content, source-specific shape/metadata, at least one source, future source without redesign | In scope: #11 (MVP-08) | Yousician v1/v2 suites; different Songsterr policy fixture; no source-specific practice columns architecture check |
| R-05-CATALOG — personal catalog, private customization, shared/catalog/history separation | In scope foundations: #9/#11/#12 (MVP-06/MVP-08/MVP-09); sharing UI deferred | schema/port ownership checks; dormant grant denial; two-tenant catalog/customization journeys |
| R-06-SESSIONS — local calendar days, 1-many sessions, multiple items, duration/notes/statistics | In scope: #13/#14 (MVP-10/MVP-11) | DST/local-date/session lifecycle properties; multi-record browser journey; typed/optional fields |
| R-06-MEDIA — optional audio/video | Deferred by approved first increment | API/OpenAPI/composition allowlist and DB privilege denial; SEC-03 suite required before activation |
| R-07-HISTORY-CALENDAR — date to sessions to records/statistics | In scope: #15 (MVP-12) | named calendar-to-history PostgreSQL/browser journey |
| R-07-HISTORY-CONTENT — content to all records and record back to associated content | In scope: #14/#15 (MVP-11/MVP-12) | content-to-history journey plus record-detail live-content link and authorized missing/tombstone states |
| R-07-HISTORY-EVOLUTION — history remains meaningful after catalog changes | In scope: #14/#15 (MVP-11/MVP-12) | immutable snapshot, definition version, rename/restructure/tombstone migration and browser cases |
| R-08-STATS — extensible typed/optional, source/instrument/content appropriate statistics | In scope: #14 (MVP-11) | all supported kinds, absent value, invalid kind/unit/enum and preserved-version properties |
| R-09-CHAR — configurable characteristics scoped by source/instrument/type | In scope: #12 (MVP-09) | scope/assignment properties, seeded guitar examples and cross-scope/cross-tenant negatives |
| R-10-MEDIA-LIFECYCLE — storage/access/limits/deletion/processing | Deferred | dormant absence/denial now; SEC-03 design/security review before implementation |
| R-11-SECURITY — Google auth, server authorization, tenant isolation, token/session/secrets/HTTPS | In scope: #5-#10/#16-#18 (MVP-02-MVP-07/MVP-13-MVP-15) | SEC-01/05/06/07/09/10/11 suites; HTTPS-only environment/config assertion; Secret Manager/IAM and secret-scan negatives |
| R-12-PRIVACY — ownership, export/deletion/retention/location | Foundations and production gate: #9/#18 (MVP-06/MVP-15); behavior deferred | ownership/isolation checks; human-approved inventory/policy and restore reconciliation; no deletion UI/route assertion |
| R-13-CLIENTS — web first, client-neutral backend/API; Android/Telegram later | Web/API in scope: #9-#15 (MVP-06-MVP-12); other clients deferred | module/API boundary tests and OpenAPI compatibility; no mobile/Telegram endpoint assertion |
| R-14-OFFLINE — explicitly evaluated but not implemented | Deferred under ADR-006 | design assertion plus no sync queue/conflict API/composition behavior |
| R-15-SEARCH — content text, source, instrument, type/versions/items; history discovery | In scope: #11/#15 (MVP-08/MVP-12) | independent filters and combinations, ancestry navigation, bounded pagination and two-tenant non-enumeration |
| R-16-INTEGRITY — migrations, catalog/stat evolution/deletion and preserved history | In scope: #9/#11/#14/#15 (MVP-06/MVP-08/MVP-11/MVP-12) | supported-fixture manifest, forward/failure migration, constraints and evolution/tombstone suites |
| R-17-RELIABILITY — backups, recovery, accidental deletion and data-loss expectations | Deployment gate: #17/#18 (MVP-14/MVP-15) | approved RPO/RTO; isolated backup/PITR restore, rollback and invariant exercises |
| R-18-OPS — logs, errors, metrics, health/readiness, monitoring, alerts, correlation IDs | In scope: #9/#17/#18 (MVP-06/MVP-14/MVP-15) | correlation propagation; health failure states; sentinel-controlled sink/redaction, metric and alert exercises |
| R-19-DELIVERY — dev/test and production, CI/CD, configuration, secrets, migrations, permissions, IaC | In scope/gated: #9/#16/#18 (MVP-06/MVP-13/MVP-15) | config schema/startup negatives; CI/IAM/WIF/provenance tests; migration job; isolated environment assertions |
| R-20-SECURE — isolation/protection | In scope | P0 isolation/auth/browser suites and independent security evidence review |
| R-20-RELIABLE — confirmed records not silently lost | In scope | transaction failure/retry/idempotency, migration, history and restore evidence |
| R-20-MAINTAIN — clear architecture/tests/decisions | In scope | architecture boundary suite, migration ownership and required work/review records |
| R-20-EXTEND — users/instruments/sources/content/stats/clients without redesign | In-scope seams only | provider/source/public-port contracts, guitar/piano and Songsterr fixture; deferred clients remain unimplemented |
| R-20-SCALE — multiple users, no enterprise target | In scope | two-tenant isolation and representative bounded load; no enterprise/multi-region claim |
| R-20-PORTABLE — avoid unnecessary lock-in | Architecture assertion | domain/application tests without GCP imports; storage/cloud adapters kept at boundary |
| R-20-PERF — responsive with approved target | In scope/gated: #11/#15/#17/#18 (MVP-08/MVP-12/MVP-14/MVP-15) | deterministic query bounds plus representative p50/p95/p99 load against owner-approved target |
| R-21-TECH — Python backend, GCP preference, approved technology constraints | In scope | dependency/configuration manifest review and architecture checks; exception requires ADR/human approval |
| R-23-MVP — auth, users, instruments, catalog/source, calendar/session/record/stats/characteristics/history/security/tests/cloud/monitoring | In scope across #4-#18 (MVP-01-MVP-15) | completion of mapped rows and both named end-to-end journeys |

### 6.2 Architecture-invariant traceability

| ID / invariant | Owner | Named verification |
| --- | --- | --- |
| A-MODULE — only `.public` cross-module imports, approved dependency edges, no cycles/shared domain ORM | #9 / MVP-06 | import/dependency and repository-mapping architecture tests |
| A-DATA — schema/migration ownership and reviewed cross-schema exceptions | #9 / MVP-06 | migration static checks, coupling-register check and PostgreSQL catalog assertions |
| A-ACTOR — identity infrastructure alone constructs immutable, provenanced `ActorContext` | #10 / MVP-07 | construction/import restrictions plus HTTP/application forgery negatives |
| A-TENANT — non-null tenant IDs, scoped repositories, transaction context and forced RLS | #5/#9 / MVP-02/MVP-06 | real-role PostgreSQL matrix including pool, worker and bypass cases |
| A-CATALOG — versioned definitions, constrained JSON, same-boundary ancestry and practiceable nodes | #11 / MVP-08 | definition/hierarchy property and constraint tests |
| A-HISTORY — stable catalog reference plus immutable versioned snapshot/statistics | #14/#15 / MVP-11/MVP-12 | evolution/tombstone/migration and both history journeys |
| A-API — `/api/v1`, stable IDs/errors, pagination, ETags, idempotency and compatible OpenAPI | #9-#15 / MVP-06-MVP-12 | API contract/compatibility and consumer-flow tests |
| A-WEB — server-rendered progressive web client using approved session/browser controls | #10-#15 / MVP-07-MVP-12 | browser security and end-to-end/accessibility journeys |
| A-DORMANT — sharing/media/account deletion/offline behavior unreachable | #9/#11/#18 / MVP-06/MVP-08/MVP-15 | route/OpenAPI/composition allowlist, policy/role denial and absence assertions |
| A-OPS — correlation-aware telemetry, health/readiness, immutable delivery and recovery | #9/#16-#18 / MVP-06/MVP-13-MVP-15 | correlation/health tests; provenance, alert, rollback and restore exercises |

## 7. Execution environments and pipeline gates

| Stage | Runs | Merge/deployment rule |
| --- | --- | --- |
| Developer | Affected formatting/lint/type checks, unit/property, application and focused PostgreSQL tests | Required before review; exact commands recorded in the issue/PR |
| Pull request | Full deterministic unit/property, application, architecture, PostgreSQL/RLS, migration, API compatibility and browser suites; security/static/dependency/secret checks | All required checks pass once without hidden retries; flaky tests fail the build and are triaged |
| Main/nightly | Expanded generators, supported-upgrade matrix, accessibility scan and representative load/security cases | Regression opens a blocking issue and prevents promotion of affected digest |
| Non-production release | Artifact/provenance verification, migrations, smoke/E2E, IAM negatives, telemetry/alert, rollback and restore exercises as scheduled | Required evidence reviewed before production-readiness gate |
| Production promotion | Same-digest verification, migration preconditions, smoke, authorization/isolation probes that cannot expose another tenant, health/alerts and rollback readiness | Only after #18 approvals and security review; destructive/adversarial cases stay in isolated environments |

Test selection may optimize unchanged areas only from a reviewed dependency map;
the full required suite still runs before promotion. Network-dependent checks
distinguish product failure from a documented environment outage, but an outage
does not convert missing evidence into a pass.

## 8. Evidence, reporting and retention

Each work record and PR records:

- requirement/design revision, commit SHA and artifact digest when applicable;
- exact command, environment, PostgreSQL/browser/tool versions and configuration
  profile, excluding secrets;
- pass/fail/skip counts, property seed/counterexample, performance dataset and
  operational exercise timestamps;
- links to sanitized logs, reports, screenshots/traces and manual-review notes;
- reviewer identity and disposition of every failure, flake, skip and known gap;
- applicable security finding status and unresolved risk/question.

CI artifacts use the shortest retention that still supports review, audit and
incident diagnosis; the final duration and storage location are approved with
SEC-09/SEC-10. Raw tokens, cookies, authorization headers, invitations, signed
URLs, notes, statistic values and production personal data are never retained.
Sanitization occurs before upload, and a canary scan fails the job if prohibited
data appears.

A quarantined flaky test has an owner, linked issue, scope/risk statement and
expiry; its requirement remains blocked or is covered by an explicitly reviewed
alternative. Tests are not deleted or weakened merely to make CI pass.

## 9. Issue-level test-design and review workflow

For every implementation issue:

1. Clarify acceptance criteria and map them to requirements, architecture
   invariants and security findings.
2. Write named positive, boundary, negative, authorization, failure/retry and
   evolution cases before production implementation.
3. Identify the lowest trustworthy test layer for each case and the cases that
   must cross HTTP, PostgreSQL, browser or cloud boundaries.
4. Define fixtures, oracles, concurrency/clock controls, cleanup, environment and
   evidence, including how false positives and sensitive artifacts are avoided.
5. Obtain independent test-design review from someone other than the author;
   resolve findings or record the blocking human/security decision.
6. Implement production behavior against the approved design, preserve failing
   tests and review evidence, then obtain independent code review.

The independent reviewer checks completeness, adversarial depth, fidelity of
test doubles, tenant/privacy safety, nondeterminism, observability of failures,
and whether tests could pass while the requirement is broken. Review is not a
rubber stamp and passing code written before an unreviewed test design does not
retroactively satisfy the gate.

## 10. Entry and exit criteria

### Strategy approval entry

- first-increment product definition and architecture are approved;
- security findings and their gates are known;
- the implementation backlog and Issue #4 exist;
- this document maps every in-scope slice and applicable finding to evidence.

### Issue implementation entry

- issue requirements are unambiguous and linked to approved architecture;
- externally visible API changes have human approval;
- applicable pre-implementation security findings are cleared and re-reviewed;
- named tests, fixtures and evidence are independently reviewed;
- unresolved decisions are explicitly blocking rather than guessed.

### Merge exit

- approved tests and all affected repository checks pass with no hidden failure,
  skip or flake;
- manual evidence is attached where automation cannot establish the claim;
- independent code review is complete;
- work record lists changes, files, evidence, unresolved risks/questions and
  security-review status;
- documentation, OpenAPI and migrations match implemented behavior.

### First-increment production exit

- Issues #4 through #18 meet their gates and the two end-to-end journeys pass;
- SEC-01, SEC-02, SEC-05 through SEC-11 and all applicable deployment findings
  are closed with evidence or explicitly accepted by the authorized human owner
  using the documented risk process;
- the named operator accepts alerts/runbooks and approved SLO/RPO/RTO/cost;
- the promoted digest has provenance, migration, smoke, isolation, load,
  rollback and restore evidence from the approved environments;
- no deferred route/behavior is exposed and no unresolved P0/P1 defect remains.

## 11. Known approvals and open decisions

This strategy does not decide the exact test libraries, supported PostgreSQL and
browser version matrix, final cookie name/domain, authorization actions, RLS
mechanism, CSP, rate limits, production topology, retention periods, performance
thresholds or recovery objectives. Their owning issues and human/security gates
must decide them before affected implementation or deployment.

Independent review passed after its findings were resolved, and the human owner
approved this strategy on 2026-09-30. Approval authorizes issue-level test design
to proceed; it does not close a security finding, prove implementation
correctness, accept risk, or authorize production deployment.
