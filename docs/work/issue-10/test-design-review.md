# Independent test-design review — Issue #10

- Reviewer: independent test-review agent; not the test-design author
- Date: 2026-10-25
- Baseline: current main `ca99acd`, merged PR #25 / closed Issue #9
- Scope: `test-design.md`, `design.md`, `http-contract.md`, candidate OpenAPI,
  accepted AUTH6-01–27 / WEB-01–05 and existing #9 database foundation
- Verdict: **test-design pass after remediation and baseline reconciliation**
- Execution: documentation review only; no application/browser/database tests
  executed and no implementation evidence approved for this issue

## Findings and disposition

### TR10-01 — Match XSS oracles to the actual minimal profile — resolved

The initial draft promised stored/reflected literal text round-tripping through
an actual profile presentation source, despite the minimal profile selecting no
names/provider text. Revised WEB-03 seeds stored control/preference/provider
canaries and asserts absence from actual pages/JSON, tests reflected-input
rejection/generic errors, and separates a test-only production-template-engine
positive/mutation control from a shipped stored rendering sink. Future slices
retain their own actual stored-text rendering cases; no absent sink is reported
as exercised.

### TR10-02 — Empty-session migration guard — superseded by current main

The initial stale-checkout design proposed mandatory new session columns and an
empty-session upgrade guard. The initial review requested a specific test for
that proposal. That entire proposal is superseded, not an additional approved
requirement: merged `005_identity` already implements nullable legacy linkage,
nonmutating upgrade and fail-closed resolution of legacy sessions.

The final test design now retains the existing populated `004_media` to
`005_identity` migration tests: old rows/columns remain unchanged, new identity/
CSRF linkage remains null, and session resolution returns no authority and does
not touch those rows. No empty-table guard, extra migration, backfill, row erasure
or alternate legacy behavior is introduced. There is no unresolved TR10-02
finding against the final design.

## Focused current-baseline re-review

Reviewed #9 `auth-foundation-design.md`, `tests/auth_support.py`, the refreshed
feature design/test design and candidate HTTP contract. The final plan reuses
the existing exact 005 wrapper signatures, discriminants, owner/runtime ACLs,
shared advisory lock and post-lock refreshed database clock. The restore-checked
owner-only `_auth_now()` fixture supplies exact boundary instants; existing
real-clock lock-wait tests remain required. No transaction-start timestamp,
caller time or new clock override endpoint replaces that design.

Admission tests now match actual 005 behavior: nullable legacy kind is bearer;
subject-bound allowlist admission is one-shot and consumed with bootstrap;
failed inner issuance rolls consumption back; explicit bad bearer admission
cannot fall back to subject admission; known active identity ignores admission.
Synthetic allowlist digests cannot be redeemed independently. The former
permanent/unconsumed allowlist proposal is not retained.

The existing #9 database evidence belongs to closed #9; it is not a feature run
or a reverse prerequisite for that issue. #10 must rerun the cumulative suites
and add public-port/provider/cookie/browser/catalog integration evidence. No
prior test count is credited as execution during this design review.

Reviewed `openapi.candidate.json` path/method inventory, cookie security,
OwnProfile closed field schema, form representations and callback HTML response
inventory against `http-contract.md`. The candidate has seven new operations
plus two existing health operations. Runtime-generated OpenAPI and actual route
registration must reconcile when implemented; inspecting this candidate is not
an executed contract test or owner API approval.

## Positive assessment

The suite plan covers all AUTH6-01–27 groups and their focused remediation,
including binder serialization, immediate verifier erasure, AEAD transaction
UUID ordering, invitation-attempt versus issuance budget commit semantics,
hard-cap accounting and deadline equality. It preserves real runtime-role
PostgreSQL, direct public-port calls, raw HTTP parsing, real HTTPS browser
journeys, source/wheel checks and independent mutations as required layers.

Catalog/private SQL requires explicit actor predicates, bind provenance and
FORCE RLS independently; an empty registry, passing fixture SQL or owner
connection cannot substitute. New actor issuance and ready orchestration need
real public-port provenance/session-linkage tests. Fault/race oracles inspect
committed state and permitted side effects instead of statuses alone. Leakage
scanners require positive observed sentinels with no uninspected enabled sink.
Required suites cannot skip, retry to green or pass with zero cases.

## Remaining implementation gates

Owner approval of the concrete HTTP contract remains pending. Pin actual
provider/browser/crypto dependencies and verify their supported composition.
Review the exact typed adapters, trusted actor issuer and private catalog
statement registry; reuse existing reviewed 005 SQL without redesign. Any
newly discovered SQL defect requires its separately reviewed additive fix.
Reconcile runtime routes, emitted query shapes, function inventory and restored
fixture clocks when executing the full integration/browser suites.

No implementation code/security review or cumulative SEC-01/05/06/07 closure
follows from this document. This passes the feature test design only; #10 remains
unimplemented and open, while #9's database foundation is already merged/closed.
