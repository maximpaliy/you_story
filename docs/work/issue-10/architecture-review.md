# Independent architecture review — Issue #10

- Date: 2026-10-25
- Reviewer: independent architecture-review agent, separate from the design author
- Baseline: main `ca99acd466c529b49ba69a296771f77f065ed736`, merged PR #25;
  Issue #9 is closed
- Material: current Issue #10 design/HTTP/OpenAPI/test documents; actual
  `005_identity.sql`; Issue #9 auth-foundation design and architecture/code
  reviews; accepted ADR-005/007/008/009/011; Issue #6 contract and accepted
  Issue #8 authentication/profile subset
- Verdict: **pass after remediation for the current implementation design**
- Scope: design-level integration and proposed HTTP/OpenAPI parity. No new
  production implementation, dependency selection or runtime evidence is approved

## Baseline correction and superseded review history

The initially supplied checkout lacked the already merged Issue #9 authentication
foundation. Earlier rolling review conclusions incorrectly treated that database
work as missing and suggested new additive DDL, a nonempty-session migration
preflight refusal, permanently unconsumed allowlist rows and a new locking plan.
Those recommendations and their earlier pass are superseded by this current-main
review. They are not implementation instructions or approved amendments.

Current Issue #10 design reuses the reviewed and implemented revision 005 without
changing its bytes, function signatures, privileges, admission semantics, clocks
or locking. Issue #10 integration is not a reverse prerequisite for closed #9.
Its prior 217-test evidence remains attributed to #9, never reported as tests
executed for this issue. Cumulative feature/security gates remain open.

## Findings and disposition

### AR10-01 — Preallowlist and legacy session representation (resolved)

Revision 005 already defines nullable `admission_kind` (`bearer`/`allowlist`) and
`permitted_subject` in owner-controlled invitation storage. The current design
preserves its exact behavior: legacy NULL kind is bearer; a matching subject
allowlist admission is one-shot and consumed atomically with new identity/session
creation; known active identities ignore admission. An explicit invitation digest
selects only bearer admission, so an invalid supplied bearer cannot fall back to
subject allowlisting. Without a supplied digest, finish may select the bound
unconsumed/unexpired subject admission. Its synthetic undistributed digest is not
an independently redeemable bearer. No runtime admission setter, caller bypass
boolean, new control table or permanent allowlist redesign is introduced.

Existing nullable external-identity/CSRF session fields are preserved. Incomplete
legacy sessions fail resolution without touch; no empty-table requirement,
identity fabrication, session deletion/backfill or rewritten migration is planned.
The prior stale-checkout storage recommendation is withdrawn.

### AR10-02 — Exact HTTP artifact and new API approval (resolved at design level)

The candidate exists and its exact nine-path method inventory matches the
concrete HTTP proposal: seven new operations plus the two existing health
operations. Focused JSON assertions verified that `/live`, `/ready`, and shared
Health/ErrorDetail/ErrorEnvelope schemas remain unchanged from the active
contract. OwnProfile is a closed user UUID/tenant UUID/provisioning enum object;
form schemas are closed and private queries/logout use the session-cookie scheme.
Callback bounds, duplicate rejection, state plus code-XOR-error requirements and
no-body policy are explicit. Every declared callback error status
400/409/429/500/503 uses generic HTML, matching the corrected prose. Unsupported
methods remain JSON framework errors without callback dispatch. OpenAPI
limitations are supplemented by descriptions/vendor extensions and required
implementation tests; the candidate alone does not enforce browser policy.

The new JSON profile URI/schema and concrete response/error/redirect choices
remain subject to owner approval under AGENTS.md. Existing lifecycle/cookie/
seven-table authentication approval does not require another owner decision.
No new SQL approval is requested because existing 005 is reused unchanged.

### AR10-03 — Current foundation wrapper integration (resolved in design)

The design now preserves exact runtime wrapper signatures/results and
`search_path=pg_catalog,identity`, owner-only helpers and zero direct runtime
control-table/sequence access. The coarse shared auth-control advisory lock and
post-wait refreshed database clock remain authoritative; no alternative lock
hierarchy or transaction-start timestamp replaces them. Provider/network calls
occur outside those transactions.

Cleanup runs once through the IP-start/IP-callback limiter stage, processing at
most 100 total transaction rows across its expiry/erasure/deletion candidate
classes and at most 100 counters; downstream wrappers do not repeat that batch.
Typed adapters commit normal finish denials so permitted outer attempt budgets
survive, while all inner identity/admission/session/issuance-success writes roll
back. Infrastructure abort is distinguished from a normal denial.

## Architecture assessment

- Identity owns OIDC, cryptography, session validation and the sole production
  ActorContext issuer. Typed validated resolver/finalization evidence supplies
  authority. Delivery/shared/domain code and client user/tenant/session/provenance
  fields cannot construct authority; public ports reject forged contexts.
  Exact source/wheel issuance and public-port checks remain implementation work.
- Composition invokes catalog through its public port after identity commit.
  Catalog ensure uses actor-derived explicit predicates and ordinary tenant
  context plus FORCE RLS, atomically creating the personal catalog/grant pair.
  Identity never queries catalog tables or imports its private implementation.
- The identity public ready command requires validated immutable actor plus
  private session evidence, verifies matching user/tenant linkage, and invokes
  existing `mark_catalog_ready(session_digest)` only after typed catalog success.
  There is no public digest-ready command or caller-selected ready target/state.
  The SQL wrapper independently revalidates active linkage.
- Failed catalog/ready work preserves the committed active session and pending
  readiness; a later login retries idempotently. Normal profile, middleware,
  resolver, health and worker paths never reconcile provisioning.
- Minimal profile uses the already resolved tuple, without a new privileged
  SELECT/result widening, provider-attribute persistence or profile-name column.
  Session UUID and secret/digest fields remain private adapter evidence.
- Fixed destination mapping preserves approved enum binding while calendar/
  catalog features remain absent. Their current bounded 404 behavior is explicit
  in the concrete contract presented for owner disposition.
- Stored-canary nonselection is distinguished from a shipped stored-text sink.
  Actual autoescaping controls remain tested without inventing provider-name
  persistence or claiming absent notes/tags/history rendering coverage.
- No worker, provider selector, linking, email identity, media, deletion, profile
  mutation, session administration, admission admin or retry endpoint is added.

## Final gate and evidence limits

No architecture blocker remains for presenting the concrete HTTP contract to
the owner. Current-main design re-review supersedes all earlier stale-baseline
conclusions. Independent security/test-design verdicts remain separately required.
After API approval, implementation must still receive exact adapter/provenance,
catalog SQL-site, dependency, source/wheel and cumulative runtime evidence review.
A discovered SQL defect requires a separately reviewed additive fix, never edits
to applied 000–005 or an implied redesign from this document.

No application, browser, provider or PostgreSQL tests ran during this document
review. Existing #9 results are prior evidence only. This pass does not grant
human API approval, complete Issue #10, accept a security risk, close cumulative
SEC-01/05/06/07 feature evidence, or authorize deployment or real-user data.

## Subsequent owner clarification (recorded by implementation lead)

After the review above, the owner chose to retain the opaque user_id and keep
tenant_id internal. The candidate now returns exactly user_id and
provisioning_state. Earlier references to a tenant UUID or a three-field public
profile describe the previous proposal. This records the owner clarification,
not a new independent review or approval of the broader HTTP contract.
