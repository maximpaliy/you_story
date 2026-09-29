# GitHub Issue #1 — Project definition

## Current status

The owner answered the five requirements questions on 2026-09-26. The accepted
Issue #1 body and owner clarifications are synchronized to
`docs/project/product-definition.md`.

The owner approved the modular-monolith choice on 2026-09-27, conditional on
defined function and database-object boundaries. ADR-005 and the architecture's
ownership matrix now define those boundaries, including catalog, practice
session and user management as possible future services. The owner approved
ADR-005 on 2026-09-27, completing the boundary condition. The owner subsequently
approved ADR-002 and ADR-003, then ADR-004 while relying on the documented GCP
expertise, on 2026-09-27. Privacy, identity, media and production decisions
remain wholly or partly pending at their documented feature/deployment gates.

On 2026-09-29 the owner excluded media support, account-deletion behavior and
offline capabilities from the first increment unless their later addition would
require database migration. ADR-006 initially recorded both possible
interpretations; the owner then confirmed that ordinary additive migrations are
allowed when stable foundations prevent disruptive ownership, identifier or
existing-data changes. ADR-006 is accepted; deferred behavior is not exposed.

The owner approved the recommended Google OIDC/web-session defaults on
2026-09-29 and chose not to collect email in the first increment. ADR-007 records
allowlisted first login, issuer/subject identity, PostgreSQL-backed server
sessions and reversible policy defaults. First-increment architecture is now
approved; deferred feature and production gates remain open.

Independent architecture review passed the original foundation and ADR-005 with
no remaining blocking or material findings. Independent security review issued
a conditional pass for ADR-005 with no new finding IDs while preserving all
applicable implementation and deployment gates. No security risk was accepted
by the architecture approval.

## Requirements disposition

1. The stray `de to` text is removed; the intended item is `personal tags`.
2. The MVP manually manages Yousician and Songsterr catalogs. Yousician is the
   initial source; Songsterr validates multi-source support. Automated import is
   not planned.
3. Catalogs are personal in the MVP. The initial storage shape includes dormant
   sharing primitives so future sharing does not require a database upgrade or
   backward-incompatible ownership change.
4. Account deletion provisionally uses de-identification through a non-login
   principal. The independent security review correctly notes that this must not
   be claimed as true anonymization until the final privacy policy and evidence
   close SEC-02 and SEC-08.
5. The MVP supports adding songs and recording sessions against Yousician's
   `Song → Version → Fragment` structure, while validated source definitions
   allow Songsterr and future sources to use different structures.
6. The first increment excludes media, account deletion and offline behavior
   unless their later addition would require database migrations. Ordinary
   additive migrations are allowed; stable foundations must prevent disruptive
   ownership, identifier or existing-data changes.
7. Google OIDC uses allowlisted issuer/subject identities and application-owned
   user IDs. Email is not requested or stored. Web sessions use the approved
   ADR-007 defaults.

## Architecture and review evidence

- `docs/project/architecture.md` answers all 17 mandated architecture questions
  and covers the web, Android, and Telegram client boundaries.
- ADR-001 selects a Python/FastAPI modular monolith with PostgreSQL and REST.
- ADR-002 is accepted and defines validated source-neutral catalog trees and
  immutable history.
  Node types are declared by versioned source definitions rather than by each
  personal catalog.
- ADR-003 is accepted and defines tenant isolation and dormant future-sharing
  primitives.
- ADR-004 is accepted and defines the managed GCP runtime and private-media
  boundary; its explicit production and media-policy gates remain pending.
- ADR-005 defines enforceable function, database-schema, table and migration
  ownership for identity/user, catalog, practice/session, media and reporting.
- ADR-006 is accepted and defers media, account deletion and offline capabilities
  from the first increment while allowing ordinary additive migrations.
- ADR-007 is accepted and defines Google OIDC plus server-side web sessions
  without collecting email.
- The architecture defines an evidence-triggered strangler path from the
  modular monolith to independently owned services without changing the public
  client API during extraction.
- The independent architecture review passed, with three advisory follow-ups.
- The independent security review records twelve findings; SEC-12 is closed by
  ADR-007 and eleven remain open at their stated implementation or deployment
  gates.

## Human decision requested

First-increment architecture is approved through ADR-007. Privacy, media and
production decisions remain gates for their deferred feature or deployment
stage. No approval accepts or waives any security/privacy risk or production
cost.

First-increment test design and independent test review are now the next phase.
Production implementation remains unauthorized until that design is approved
and all applicable first-increment security prerequisites are complete.

## Remaining pre-deployment decisions

The final deletion/retention/export policy, media policy and region, production
operator, production cost envelope, and proposed service/recovery objectives
remain separate human approval gates before real user data or deployment.

## Completion evidence

- **Changed:** synchronized approved requirements, proposed foundation
  architecture and seven ADRs, and recorded independent architecture/security
  reviews.
- **Verified:** public issue source, YAML/document formatting, complete answers
  to the 17 architecture questions, independent architecture review, and
  independent security threat-model review.
- **Unresolved:** eleven open security findings at their stated gates;
  test design/review; deferred-feature and pre-deployment
  privacy, media, operations, and cost decisions.
- **Security review:** conditional pass; no risks accepted.
- **Production implementation:** not started or authorized.
