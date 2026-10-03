# Proposed MVP implementation backlog

- **Status:** Approved by the human owner on 2026-09-29; issues created
- **Prepared from:** the approved first-increment scope in the project definition,
  foundation architecture, ADR-001 through ADR-007, architecture review, and
  security review
- **GitHub state:** MVP-01 through MVP-15 were created as GitHub Issues #4
  through #18 on 2026-09-30
- **Implementation state:** Test-strategy design started in Issue #4; production
  implementation is not started or authorized

## 1. Approval and authorization

The human owner approved the issue boundaries, ordering, and dependencies on
2026-09-29 and authorized creation of these items in GitHub. This approval does
**not** approve an API contract, close a security finding, authorize production
implementation before the per-issue gates pass, accept a security/privacy risk,
or approve production cost.

Each proposed issue is intentionally small enough to pass the project workflow
on its own: clarify its slice, record any necessary design, design and
independently review its tests, implement only after its gates pass, run the
checks named in the issue, obtain independent code review, and merge. Issue
bodies should link their evidence in `docs/work/<issue-number>/`.

## 2. Sequencing principles

1. Test design and the four first-increment security prerequisites precede
   affected production code.
2. The executable foundation is followed by one end-to-end identity slice and
   then by thin catalog and practice slices. API, application, persistence, and
   server-rendered web behavior ship together when a slice has user-visible
   behavior; the backlog does not create separate horizontal “build the whole
   backend” and “build the whole frontend” phases.
3. PostgreSQL, including RLS, is used for isolation and migration evidence. An
   in-memory substitute cannot satisfy those acceptance criteria.
4. Yousician is the only user-facing source required in the first increment.
   A structurally different Songsterr definition is a contract fixture that
   proves the approved extension seam, not a second product integration.
5. Production exposure is last and remains blocked on the human privacy,
   operations, cost, and security decisions identified by the approved reviews.

## 3. Proposed issues

### MVP-01 — Approve the first-increment test strategy and traceability matrix

**Outcome:** Replace the placeholder test strategy with a reviewed plan that
maps first-increment requirements, architecture invariants, and applicable
security findings to automated or manual evidence.

**Scope**

- Define unit/property, PostgreSQL integration/RLS, migration, architecture,
  API-contract, browser end-to-end, security, accessibility, performance, and
  operational test layers.
- Specify fixtures for Yousician and a structurally different Songsterr model,
  and define the calendar-to-history and content-to-history journeys.
- Define evidence retention, environments, test-data isolation, and the
  independent test-design review record.
- Trace SEC-01 and SEC-05 through SEC-11 to the issue that must close or verify
  each finding; keep deferred media-specific tests outside the first increment.

**Acceptance**

- `docs/testing/strategy.md` is complete, independently reviewed, and approved
  by the human owner.
- Every in-scope requirement and security gate has an owner and verification
  method; deferred features are clearly marked rather than silently omitted.

**Depends on:** approved architecture (complete).  
**Blocks:** all production-code issues.

---

### MVP-02 — Specify and approve fail-closed PostgreSQL tenant isolation

**Outcome:** Close the design portion of SEC-01 before any tenant-backed
repository is implemented.

**Scope**

- Specify the constrained runtime identity, controlled owner migration identity,
  test-fixture boundary and exact grants; forced RLS and owner behavior;
  transaction-local tenant context; pooling reset; missing-context failure; job
  conventions; the schema-migration boundary; and the future privileged tenant-
  data migration design gate.
- Design adversarial integration tests for reads, writes, lists, joins, child
  rows, guessed identifiers, reused connections, missing context, background
  work, and attempted role bypass.
- Require normal repository SQL to carry explicit actor-derived tenant predicates
  in addition to FORCE RLS, with independent mutation tests for both layers.
- Obtain independent security and test-design review.

**Acceptance**

- The exact mechanism and test cases are durable project documentation.
- The security review records that tenant-persistence implementation may begin;
  no finding is represented as closed until implementation evidence also passes.

**Depends on:** MVP-01.  
**Blocks:** MVP-06 and every tenant-backed feature.

---

### MVP-03 — Specify and approve web authentication/session security

**Outcome:** Resolve the pre-implementation decisions in SEC-05 for Google OIDC
and server-side sessions.

**Scope**

- Fix the session cookie name/path/domain and persistence, idle/absolute expiry,
  rotation, logout/revocation, OAuth error handling, invitation/account-linking
  behavior, and redirect allowlist.
- Design negative tests for state, nonce, PKCE, issuer/audience/signature/time
  validation, login CSRF, fixation, replay, redirect abuse, expiry, and logout.
- Preserve ADR-007's `openid profile` scope and issuer/subject identity; do not
  add email collection.
- Obtain independent security and test-design review.

**Acceptance**

- The identity/session contract is explicit, reviewed, and linked from SEC-05.
- Authentication implementation is unblocked without accepting residual risk.

**Depends on:** MVP-01.  
**Blocks:** MVP-07.

---

### MVP-04 — Specify and approve browser security controls

**Outcome:** Resolve the pre-implementation decisions in SEC-06 before web forms
or user-authored text are rendered.

**Scope**

- Define CSRF token binding/rotation, accepted state-changing content types and
  origin checks, framework escaping rules, the prohibition/review process for
  unsafe HTML, CSP, and other browser security headers.
- Design stored/reflected XSS and CSRF negative tests for names, notes, tags,
  goals, source metadata, and validation errors.
- Obtain independent security and test-design review.

**Acceptance**

- Browser controls and their automated verification are explicit and approved.
- The review records whether SEC-06 is ready for implementation evidence.

**Depends on:** MVP-01.  
**Blocks:** MVP-07 and every later web slice.

---

### MVP-05 — Approve the deny-by-default authorization matrix

**Outcome:** Resolve the pre-implementation design portion of SEC-07 for all
first-increment resources and actions.

**Scope**

- Define actions for identity/profile, personal catalogs and dormant grants,
  entries and ancestry, characteristics/customizations, sessions, records,
  snapshots/statistics, search, calendar, and both history directions.
- Require parent-scoped child resolution, immutable server-derived tenant
  ownership, constrained mutable fields, and dormant/unreachable sharing and
  media surfaces.
- Generate IDOR, cross-tenant, mass-assignment, and unauthorized count/search
  test cases, and obtain independent security and test-design review.

**Acceptance**

- Every first-increment use case has an allow/deny rule and adversarial tests.
- The review records that application authorization implementation may begin.

**Depends on:** MVP-01.  
**Blocks:** MVP-07 through MVP-12.

---

### MVP-06 — Establish the executable modular-monolith and database foundation

**Outcome:** A runnable, testable FastAPI application and PostgreSQL schema
foundation exists without exposing product behavior.

**Scope**

- Create the approved module/package boundaries, dependency rules, configuration
  loading, transaction plumbing, UUID/time primitives, and migration layout.
- Add initial identity, catalog, practice, and dormant media foundations required
  by ADR-006, including personal catalog/grant shape and stable identifiers.
- Implement reviewed database roles, grants, tenant context, forced RLS, and
  migration tests. The runtime role has no dormant-media privileges.
- Add `/live`, `/ready`, stable error envelopes, request correlation IDs,
  generated OpenAPI checks, lint/type/test commands, and CI checks.
- Prove with architecture tests that forbidden module imports/cycles,
  cross-schema mappings/migrations, registered media repositories/adapters, and
  a first-increment media route fail the build.

**Acceptance**

- The app and PostgreSQL start in the documented development/test environment;
  health and migration tests pass from an empty database and supported upgrade
  point.
- SEC-01 adversarial tests pass, including pooled-connection reuse and missing
  context, and the independent security review records the implementation
  evidence.
- No login, catalog editing, practice behavior, sharing, media behavior, account
  deletion, or offline behavior is exposed.

**Depends on:** MVP-01 and MVP-02.  
**Blocks:** MVP-07 through MVP-12 and platform integration.

---

### MVP-07 — Deliver allowlisted Google sign-in and session logout

**User value:** An invited user can sign in with Google, receive an isolated
internal account/personal tenant, view a minimal authenticated home/profile, and
log out; a non-allowlisted user cannot provision an account.

**Scope**

- Implement Authorization Code + PKCE using issuer/subject identity and
  `openid profile`, atomic invitation consumption/provisioning, opaque
  PostgreSQL-backed session tokens stored only as digests, rotation, expiry,
  revocation, and logout.
- Apply the approved CSRF, escaping, CSP, and security-header controls to the
  first server-rendered page and JSON endpoints.
- Keep provider adapters extensible but implement only Google; do not expose
  Android tokens, Telegram linking, email identity, or account deletion.

**Acceptance**

- Approved positive and negative OIDC/session/browser tests pass, including
  replay, fixation, login CSRF, redirect, expiry, logout, and stored/reflected
  input probes.
- The API derives immutable `ActorContext`; request input cannot construct or
  override it. Cross-user/session tests pass.
- Independent security and code reviews approve the evidence for this slice.

**Depends on:** MVP-03, MVP-04, MVP-05, and MVP-06.  
**Blocks:** all authenticated feature slices.

---

### MVP-08 — Deliver a searchable personal Yousician catalog

**User value:** An authenticated user can create, edit, browse, and find their
own guitar or piano Yousician songs, versions, and fragments through the web UI
and `/api/v1`.

**Scope**

- Seed guitar/piano reference data and versioned Yousician definitions; validate
  `song -> version -> fragment`, required version level, ancestry, lifecycle,
  practiceable nodes, and constrained metadata.
- Add personal catalog/entry commands and navigation/search by text, source,
  instrument, type, and ancestry with cursor/request bounds, ETags/`If-Match`,
  stable errors, and approved additive API contract.
- Add a structurally different Songsterr definition as a policy/contract test
  fixture only; no Songsterr user workflow or automated import.
- Keep sharing grants dormant and reject attempts to activate non-personal
  visibility.

**Acceptance**

- API, PostgreSQL/RLS, migration, browser journey, hierarchy/property, search,
  optimistic-concurrency, and cross-tenant/IDOR tests pass.
- Catalog modifications never allow owner/tenant/visibility mass assignment.
- OpenAPI compatibility, independent security review of applicable evidence,
  and independent code review pass.

**Depends on:** MVP-07.  
**Blocks:** MVP-09 and MVP-10.

---

### MVP-09 — Deliver configurable characteristics and personal catalog details

**User value:** A user can define source/instrument/type-appropriate content
characteristics, assign them to catalog entries, and maintain private tags and
goals without affecting another user.

**Scope**

- Add characteristic definitions and assignments with scope validation.
- Add private user-entry customization for tags, goals, and supported personal
  metadata through the web UI and `/api/v1`.
- Include the initial guitar examples as data, not universal hard-coded fields.

**Acceptance**

- Scope/property, API-contract, browser, persistence, optimistic-concurrency,
  mass-assignment, and cross-tenant tests pass.
- Changes to personal customizations cannot mutate shared/source catalog fields
  or another tenant's view.
- Independent security and code reviews pass.

**Depends on:** MVP-08.  
**Blocks:** none; may proceed in parallel with MVP-10 after MVP-08.

---

### MVP-10 — Deliver calendar session creation and daily navigation

**User value:** A user can navigate calendar days, create a draft practice
session for a local date/time zone, add notes, edit it safely, and view that
day's sessions.

**Scope**

- Implement the approved session lifecycle with UTC instants plus captured IANA
  time zone/local date, bounded daily listing, status transitions, ETags, and
  idempotent creation scoped to tenant + operation + payload.
- Provide the `/api/v1` contract and server-rendered calendar/day/session flow.
- Do not add records, statistics, media, offline synchronization, or analytics.

**Acceptance**

- Time-zone/DST property cases, state transitions, idempotency conflicts/replay,
  API contract, browser journey, and PostgreSQL/RLS cross-tenant tests pass.
- A session cannot be read or changed by guessed ID, child route, changed tenant
  input, or stale version.
- Independent security and code reviews pass.

**Depends on:** MVP-07 and MVP-08.  
**Blocks:** MVP-11.

---

### MVP-11 — Record practice with immutable content snapshots and statistics

**User value:** Within a session, a user can select a practiceable catalog node
and record duration, notes, and zero or more valid statistics; the record keeps
its original meaning after later catalog edits.

**Scope**

- Add record creation/editing under an authorized session and catalog entry,
  copying the approved immutable source/instrument/ancestor/type/name snapshot.
- Validate optional integer, decimal, boolean, text, duration, and enum values
  against the captured source-definition/statistic versions.
- Render record details and navigation to the live content when available;
  implement referenced-entry tombstones without exposing hard-delete or account-
  deletion workflows.
- Exclude attachments and all media routes/adapters.

**Acceptance**

- Snapshot immutability/evolution, typed-statistic/property, tombstone,
  transaction rollback, API-contract, browser, and cross-tenant parent/child/
  guessed-ID tests pass.
- Zero statistics is valid; unsupported or meaningless values are rejected.
- Historical rendering survives catalog rename/restructure/tombstone fixtures.
- Independent security and code reviews pass.

**Depends on:** MVP-10.  
**Blocks:** MVP-12.

---

### MVP-12 — Deliver calendar-to-history and content-to-history journeys

**User value:** A user can review all sessions and practiced items for a day and
all historical records for a selected catalog entry, with navigation among day,
session, record, and content views.

**Scope**

- Add bounded, cursor-paginated history queries and server-rendered views using
  practice-owned snapshots and owner public interfaces only.
- Preserve tenant/source/instrument/content filters needed by the approved MVP;
  use indexed PostgreSQL queries rather than a search service or persisted
  reporting projection unless measurement proves one is required.
- Complete the two named end-to-end user journeys and accessible empty/error
  states.

**Acceptance**

- Calendar-to-history and content-to-history browser journeys pass against
  PostgreSQL, including changed/tombstoned catalog metadata.
- Authorization tests cover lists, counts, joins, filters, pagination cursors,
  guessed IDs, and children across two tenants without leaking existence.
- Query bounds and the approved performance test pass; accessibility,
  OpenAPI-compatibility, independent security, and code reviews pass.

**Depends on:** MVP-11.  
**Blocks:** MVP-15.

---

### MVP-13 — Provision the reviewed non-production GCP delivery path

**Outcome:** The same immutable application artifact can be safely promoted to
an isolated non-production Cloud Run/Cloud SQL environment, but not production.

**Scope**

- Provision the approved non-production GCP services with reviewed IaC, private
  database connectivity, Secret Manager, Artifact Registry, least-privilege
  service accounts, and a dedicated single-execution migration job.
- Add GitHub Actions with immutable action references, minimal permissions,
  restricted Workload Identity Federation claims, locked/hashed dependencies,
  source/dependency/image/IaC/secret scanning, SBOM and artifact attestation,
  digest-preserving promotion, and vulnerability disposition rules.
- Exercise expand/migrate/contract and application rollback/forward-repair in
  non-production. Do not provision media behavior or a production environment.

**Acceptance**

- CI proves provenance and deploys a reviewed digest to non-production without
  long-lived cloud keys; negative WIF/IAM and runtime-media-permission tests pass.
- Migration failure and application rollback exercises preserve the database;
  evidence identifies revision, digest, and environment.
- SEC-09 receives independent security evidence review for this environment.

**Depends on:** MVP-01, MVP-02, and MVP-06.  
**Blocks:** MVP-15; may proceed in parallel with feature slices after MVP-06.

---

### MVP-14 — Add privacy-safe observability and operational verification

**Outcome:** Operators can diagnose the non-production application without
logging sensitive user content, and can verify readiness, alerts, and recovery.

**Scope**

- Implement the approved allowlisted structured telemetry fields, keyed/
  rotatable actor/tenant pseudonyms, centralized redaction, metrics, error
  reporting, readiness dependency checks, and non-production alerts.
- Define request, pagination, timeout, concurrency, and per-account/IP/tenant
  limits for exposed first-increment operations; test safe errors and tenant-
  scoped idempotency.
- Document and exercise application rollback, credential revocation, tenant-
  isolation incident, database backup/restore, and migration failure runbooks in
  an isolated non-production target.
- Seed canary secrets, tokens, notes, statistics, and identifiers and prove that
  they do not reach logs/traces/errors.

**Acceptance**

- Health, telemetry-redaction, alert, abuse/exhaustion, load, rollback, backup,
  and restore checks produce reviewable evidence.
- SEC-10 and the implemented portion of SEC-11 receive independent security
  review; production retention/deletion and operator decisions remain open.

**Depends on:** MVP-07 and MVP-13.  
**Blocks:** MVP-15.

---

### MVP-15 — Approve and execute the production-readiness gate

**Outcome:** After explicit human decisions, the reviewed MVP artifact is either
promoted to production with evidence or the issue remains blocked without
weakening a gate.

**Scope**

- Obtain human approval for deletion/export/retention and all data locations and
  copies (SEC-02 and SEC-08), the named operator, cost envelope, production
  topology/HA, SLO, RPO/RTO, backup/PITR, and alert routing.
- Complete production-applicable SEC-09 through SEC-11 controls, vulnerability
  disposition, restore/deletion reconciliation, load validation, deployment and
  rollback rehearsal, and independent security review.
- Provision production only after approvals, promote the already verified digest,
  run smoke/authorization checks, and record the release and recovery evidence.
- Keep media, account-deletion behavior, offline functionality, Android,
  Telegram, sharing activation, imports, recommendations, advanced analytics,
  and community features out of scope.

**Acceptance**

- Every applicable deployment blocker is closed with evidence or explicitly
  accepted by the human owner with rationale, compensating controls, affected
  data/environment, approver, and expiry/review date.
- The production operator accepts the runbooks and alerts; restore, rollback,
  isolation, smoke, and performance objectives pass for the promoted digest.
- The work record states unresolved risks and does not describe provisional
  de-identification as anonymization.

**Depends on:** MVP-12, MVP-13, and MVP-14.  
**Blocks:** declaring the first-increment MVP complete or using real user data.

## 4. Dependency graph and suggested merge order

```text
Approved architecture
        |
      MVP-01  Test strategy + independent review
       / | \
      /  |  +--------------------+
     v   v                       v
 MVP-02 MVP-03                 MVP-04
   RLS   auth design        browser design
     \     |                    /
      \    +------ MVP-05 -----+
       v        authorization
      MVP-06  executable/database foundation
       |  \
       |   +--------------------------> MVP-13 non-prod delivery
       v                                  |
      MVP-07  sign-in/session ------------+--> MVP-14 operations
       |
      MVP-08  personal Yousician catalog
       |  \
       |   +--> MVP-09 characteristics/customization
       v
      MVP-10  calendar sessions
       |
      MVP-11  practice records/snapshots/statistics
       |
      MVP-12  both history journeys
       |                     MVP-13 ---- MVP-14
       +-------------------------\---------/
                                  v
                                MVP-15 production gate
```

Suggested merge train:

1. MVP-01.
2. MVP-02, MVP-03, MVP-04, and MVP-05 may be designed/reviewed in parallel.
3. MVP-06, then MVP-07, then MVP-08.
4. MVP-09 and MVP-10 may proceed independently after MVP-08; MVP-10 does not
   depend on characteristics/customizations.
5. MVP-11, then MVP-12.
6. MVP-13 may proceed after MVP-06 while product slices continue; MVP-14 starts
   after identity and non-production delivery exist.
7. MVP-15 is last and cannot be time-boxed around unresolved human/security
   gates.

## 5. Explicitly excluded from this backlog

No issue should be created yet for media upload/download or processing, account-
deletion behavior, offline operation/synchronization, Android, Telegram,
additional user-facing sources, sharing/community contribution, automated
imports, recommendations, advanced analytics, microservices, event brokers,
GraphQL, dedicated search infrastructure, multi-region deployment, or
transcoding. Their approved extension seams are verified only where the first
increment requires that evidence.

Media metadata foundations are part of MVP-06 solely because ADR-006 requires
stable ownership and identifiers; the issue explicitly proves the runtime role,
repository/adapters, and routes cannot activate media. Production privacy and
retention decisions are included only because they gate use of real identity,
practice, telemetry, and backup data even when account-deletion UI and media are
absent.

## 6. Issue-creation rules

The owner approved this proposal on 2026-09-29. Issues #4 through #18 were
created from the approved definitions on 2026-09-30. For future backlog changes:

1. Create the issues in dependency order with the text above, replacing MVP IDs
   with assigned GitHub numbers and adding GitHub dependency links.
2. Create `docs/work/<issue-number>/status.yaml` from the template when work on
   each issue starts; do not pre-create implementation artifacts for the whole
   backlog.
3. Apply labels for `test-design`, `security`, `platform`, or `feature` as
   appropriate, plus a common first-increment milestone if the repository uses
   those workflow objects.
4. Record human approval and any requested boundary changes in this document
   before issue creation. Material architecture, API, privacy, security-risk, or
   production-cost decisions return to their existing approval gates.
