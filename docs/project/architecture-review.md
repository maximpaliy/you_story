# Independent Architecture Review — GitHub Issue #1

- **Review status:** Complete
- **Review date:** 2026-09-26
- **Reviewer:** Independent architecture reviewer (not the architecture author)
- **Reviewed baseline:** `docs/project/product-definition.md`,
  `docs/project/architecture.md`, and ADRs 001–004
- **Gate recommendation:** **Approve for human architecture approval. The
  independent security review must be recorded before that decision; test design
  follows human approval. Do not begin production implementation yet.**

## 1. Review method and scope

The review traced every section of the approved product definition and the five
owner clarifications into the proposed architecture, then assessed internal
coherence, data evolution, client compatibility, security/privacy boundaries,
operational burden, and avoidable complexity. It also checked that the four
ADRs accurately record the material decisions and their consequences.

This is an architecture review, not the required security review, test-design
review, human approval, cost approval, or deployment approval. Those gates must
not be inferred from this recommendation.

## 2. Findings

### Blocking findings

None.

### Material findings

None. The architecture is sufficiently specific to drive test design without
silently resolving the privacy, media, cost, or operational decisions that the
product definition permits to remain open until deployment.

### Advisory findings

#### AR-1 — Make the eventual export contract explicit before deployment

- **Severity:** Advisory
- **Disposition:** Accepted as a deployment-gate follow-up
- **Observation:** The architecture correctly names the final
  deletion/retention/export policy as an unresolved deployment gate, but it does
  not yet describe the export boundary (included data, media packaging,
  authorization, delivery, and expiry).
- **Recommendation:** Once the owner sets the privacy policy, document an
  export use case and threat model it before implementation of export or
  production deployment. This does not block the MVP architecture or test
  design because detailed privacy/legal requirements are explicitly deferrable.

#### AR-2 — Keep source definitions bounded and review schema changes empirically

- **Severity:** Advisory
- **Disposition:** Covered by ADR-002 and its ADR escalation rule
- **Observation:** A generic tree plus constrained metadata is an appropriate
  compatibility seam for Yousician and the deliberately different Songsterr
  fixture. It could become a miniature schema language if definitions absorb
  arbitrary behavioral rules.
- **Recommendation:** Keep structural validation in small source policies,
  permit only documented metadata shapes and statistics, and apply ADR-002's
  escalation rule as soon as a real source cannot be represented faithfully.

#### AR-3 — Treat proposed service objectives and HA as unapproved planning data

- **Severity:** Advisory
- **Disposition:** Already identified in the architecture
- **Observation:** Cloud SQL HA, the latency/availability objectives, and the
  recovery objectives imply cost and operational commitments beyond a minimal
  personal MVP.
- **Recommendation:** Retain them as measurable proposals only. Human approval
  of the production cost envelope and evidence from load and restore tests are
  required before they become commitments.

## 3. Requirements and clarification coverage

| Requirement area | Architectural coverage | Assessment |
| --- | --- | --- |
| Personal MVP with a multi-user foundation | Internal users, one personal tenant per user, tenant-qualified private aggregates, service authorization, and RLS | Covered |
| Google authentication and provider extensibility | Stable provider subject maps to internal identity; OIDC authorization-code flows and provider adapters | Covered; security review required |
| Guitar, piano, and future instruments | Instrument reference data qualifies entries, definitions, and characteristics | Covered |
| Yousician first; Songsterr to prove multi-source behavior | Separate sources and policies, Yousician `song -> version -> fragment`, an independent Songsterr hierarchy, and source contract tests | Covered |
| Manual catalogs; no assumed automatic import | Catalog CRUD is source-neutral and automated import is explicitly deferred | Covered |
| Personal-only catalog now; future sharing without database or backward-incompatible changes | Owner, visibility, and grants are present initially while MVP policy allows only personal visibility | Covered |
| Source-specific structures | Typed trees, constrained metadata, versioned definitions, policy adapters, and an ADR escape hatch | Covered |
| Catalog, customization, and history separation | Distinct catalog entries, private customizations, sessions, and practice records | Covered |
| MVP song creation and Yousician session recording | The catalog hierarchy models song name, version name/level, and fragment name; records may target practiceable nodes | Covered |
| Calendar and bidirectional history navigation | Dated sessions contain records; records reference entries and snapshots; indexed filters support history lookup | Covered |
| History remains meaningful after catalog evolution | Immutable content snapshots, versioned statistic meaning, tombstones, and migration discipline | Covered |
| Provisional anonymization on account deletion | Non-login anonymized principal retains history while direct identifiers/media are removed | Covered provisionally; final policy and security approval remain gates |
| Extensible and optional statistics | Versioned typed definitions/values allow absence and avoid Yousician-specific history columns | Covered |
| Configurable characteristics, tags, goals, and preferences | Scoped definitions and user customization are separated from source data | Covered; detailed preference fields can remain use-case driven |
| Optional audio/video | Relational metadata plus private object storage, authorized signed-URL flow, quarantine, and lifecycle reconciliation | Covered; limits, scanning, region, and retention remain approval gates |
| Web now, Android and Telegram later | Client-neutral services and versioned REST/OpenAPI; client-specific identity and Telegram linking are considered | Covered |
| Offline explicitly evaluated | Offline mutation synchronization is deliberately deferred; read caching remains compatible | Covered |
| Search and navigation | Indexed PostgreSQL search and source/instrument/type/ancestry filters; no premature search service | Covered |
| Security and privacy | Trust boundaries, least privilege, server-side authorization, tenant isolation, secure sessions/tokens, secrets, and a defined independent security-review gate | Architecturally covered; specialist approval pending |
| Backups, recovery, observability, and operations | Backups/PITR, restore drills, health endpoints, metrics/logs/alerts, migrations, rollback and incident runbooks | Covered, subject to cost/operator approval |
| Environments, CI/CD, and GCP preference | Isolated projects, infrastructure as code, immutable artifacts, GitHub OIDC, Cloud Run/SQL/Storage/Secret Manager | Covered; production cost approval pending |
| Portability and maintainability | PostgreSQL/OCI and ports reduce unnecessary coupling; modules, ADRs, contract tests, and OpenAPI govern change | Covered |

No approved requirement is contradicted. The architecture appropriately treats
the corrupted `de to` text as removed and does not reintroduce a requirement in
its place.

## 4. Coherence and data-evolution assessment

The model has a clear separation between identity/tenancy, catalog content,
user customization, practice history, and media. A practice record's optional
live entry relationship serves navigation, while its immutable snapshot serves
historical meaning. Tombstones and versioned statistic definitions avoid
rewriting history when catalog data evolves.

The shared-catalog compatibility requirement is met without exposing sharing in
the MVP: ownership, visibility, and grants exist in the initial storage shape,
and policy prevents their premature use. Source/instrument-qualified nodes and
same-boundary parent constraints prevent invalid mixed trees. The proposed
expand/migrate/contract migration discipline is consistent with API backward
compatibility and future clients.

The ADRs are aligned with the main document:

- ADR-001 records the monolith/API boundary and rejects unjustified distributed
  infrastructure.
- ADR-002 records the extensible content model and immutable-history strategy.
- ADR-003 records tenant isolation and the initially dormant sharing shape.
- ADR-004 records the managed GCP and private-media boundary.

No material decision in those ADRs conflicts with the requirements baseline.

## 5. Complexity assessment

The design introduces more structure than a literal single-user CRUD
application, but the principal seams are justified by explicit compatibility or
security requirements:

- tenant IDs and RLS address required multi-user isolation;
- dormant grants address the explicit no-database-upgrade/no-breaking-change
  sharing requirement;
- source policies and versioned definitions address structurally different
  catalogs and statistics;
- snapshots and tombstones address durable historical meaning;
- REST/OpenAPI and client-neutral services address Android and Telegram;
- private object storage addresses user-created media safely.

The architecture avoids unjustified microservices, event brokers, event
sourcing, GraphQL, a search cluster, automated imports, offline writes,
multi-region operation, and sharing/moderation UI. Optimistic concurrency on
mutable records, idempotency on creation, and migration discipline are modest
safeguards for multi-client correctness rather than speculative platforms.

Operationally, production HA, malware handling, backup choices, alert routing,
and SLOs are the costliest elements. They are correctly held behind explicit
human/security/deployment decisions rather than silently committed. Overall
complexity is **proportionate**, provided those conditional features are not
implemented before their gates are resolved.

## 6. Gate recommendation

**Independent architecture review passes.** The proposed architecture and
ADRs 001–004 may advance to human architecture approval now that the independent
security review is recorded. Test design and its independent review follow human
approval.

Production implementation remains blocked until all workflow gates named in
the architecture are complete. In particular:

1. the human owner approves or amends the architecture and proposed ADRs;
2. an independent security review resolves all critical/high findings relevant
   to implementation;
3. tests are designed from this baseline and independently reviewed; and
4. later deployment separately resolves deletion/retention/export policy,
   media policy and region, named operator, and production cost envelope.

Any material response to AR-1 through AR-3 that changes a public contract,
storage model, trust boundary, or approved technology requires another
architecture review; purely elaborating the already identified deployment
decisions does not.

## 7. Addendum — future service-extraction path (2026-09-27)

An independent reviewer assessed the later elaboration in **Future transition
to services** and ADR-001. The evidence-triggered strangler sequence is
consistent with the reviewed modular-monolith decision and does not change the
MVP topology, public API, approved requirements, or pending human-approval gate.

The review identified one material wording issue: unconstrained shadow traffic
could duplicate mutating side effects and contradict the single-writer cutover
rule. The architecture now limits shadowing to non-mutating comparisons and
requires controlled write replay or an isolated/dry-run destination before a
governed writer cutover. No blocking or material findings remain.

This addendum approves the extraction guidance as an architecture elaboration;
it does not pre-approve microservices. Each actual extraction changes data and
trust boundaries and therefore still requires its own ADR plus independent
architecture and security reviews.

## 8. Addendum — module and data ownership boundaries (2026-09-27)

An independent reviewer assessed ADR-005 and the corresponding module/data
ownership section added in response to the owner's conditional approval of the
modular-monolith choice. The initial review found two material gaps:
cross-module function boundaries lacked concrete public ports and enforceable
dependency rules, and cross-schema constraint exceptions lacked ownership and
lifecycle governance.

The architecture now defines module public/private package topology, named
ports, permitted dependency edges, `ActorContext` provenance, CI and contract-
test assertions, owner-controlled read models, and explicit reporting-projection
rules. It also assigns cross-schema constraints to the referencing module,
requires approval by both module owners and architecture review, records purpose
and removal conditions in a coupling register, preserves tenant-consistent
references, and prohibits direct ORM navigation or cross-schema queries.

On re-review, no blocking or material findings remain. ADR-005 is internally
consistent with ADR-001, preserves one deployable monolith without speculative
distributed infrastructure, and provides enforceable catalog, practice/session,
identity/user, media and reporting boundaries suitable for later extraction.
This review does not itself grant human approval: ADR-005 remains Proposed until
the owner approves or amends it, and test design and implementation remain gated
on completion of architecture approval.

**Subsequent disposition:** The human owner approved ADR-005 on 2026-09-27,
completing the boundary condition on ADR-001. The other architecture decisions,
test-design gate and implementation gate are unchanged.

The human owner subsequently approved ADR-002 and ADR-003 on 2026-09-27. Those
approvals accept the reviewed catalog/history and tenancy/future-sharing
decisions without changing this review's advisory follow-ups, open security
findings, or implementation gates.

The human owner subsequently approved ADR-004 on 2026-09-27, relying on the
documented GCP expertise. This accepts the reviewed managed-service and
private-media architecture boundary, not the separately gated media policy,
production topology/region, operator, cost envelope, security findings, or
implementation and deployment evidence.

## 9. Addendum — staged first-increment scope (2026-09-29)

An independent reviewer assessed proposed ADR-006 and the deferral of media,
account-deletion and offline behavior from the first increment. The module
boundaries, stable identifiers, immutable snapshots and versioned API provide
appropriate foundations without implementing those deferred capabilities.

The initial draft materially narrowed the owner's “would require database
migrations” condition to disruptive migrations while allowing additive ones and
incorrectly marked that unconfirmed interpretation Accepted. ADR-006 now states
both interpretations, remains Proposed, and requests explicit owner
clarification. The review also required enforceable dormant-media isolation;
the architecture now denies the runtime database role access to the media
schema, registers no media repository/command adapter/route, and requires
negative architecture and integration tests.

No blocking or material architecture finding remains in the revised proposal.
It may proceed to human clarification, but first-increment test design remains
gated on that clarification and the web identity decision. This review does not
approve ADR-006 or any deferred feature, privacy policy, security risk or
production decision.

**Subsequent disposition:** The human owner confirmed on 2026-09-29 that ordinary
additive migrations are allowed when the initial foundations prevent disruptive
ownership, identifier or existing-data changes. ADR-006 is Accepted. Web
identity remains the only outstanding first-increment architecture approval;
deferred feature, security and deployment gates are unchanged.

## 10. Addendum — web identity and session architecture (2026-09-29)

An independent reviewer assessed ADR-007 and the first-increment identity
changes. The decision preserves application-owned UUIDs and issuer/subject
external identity, minimizes claims by omitting email, keeps provider linking
explicit, and uses the existing identity module and PostgreSQL rather than new
session infrastructure. The allowlist, timeout and concurrent-session choices
are reversible policy; changing the durable identity keys would require a new
reviewed migration decision.

No blocking or material architecture finding remains. ADR-007 completes the
human architecture decisions needed for first-increment test design. It does not
approve Android or Telegram identity, production implementation, or any deferred
feature/deployment decision.
