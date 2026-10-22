# Independent security review — Issue #9 authentication database foundation

- Date: 2026-10-22
- Reviewer: independent security-review agent, separate from design and code authors
- Baseline: accepted ADR-011 and reconciled ADR-008/009; approved Issue #6
  auth-session-contract and AUTH6-01 through AUTH6-27 design
- Material: auth-foundation-design.md and auth-foundation-test-design.md
- Preimplementation verdict: pass after the clarifications below

## Scope and authority

Issue #6's design gate is now approved. The old foundation review's statement
that it blocks authentication database implementation is historical and must not
be repeated as current status. This review permits only the approved database
foundation delta: seven explicit control tables, exact narrow wrappers and
schema/role/atomicity evidence. It does not close SEC-05, validate OIDC claims,
implement browser/cryptographic protocols, issue ActorContext from HTTP, approve
catalog provisioning, add workers, or authorize deployment/real user data.

The DB wrappers trust verified identity inputs supplied only by future trusted
identity infrastructure. Canonical issuer/subject syntax checks are defense in
depth, not provider validation. A compromised runtime credential able to invoke
finish with arbitrary validated-claim arguments remains outside the promised
DB isolation boundary, as in ADR-008. No client may directly choose those
arguments or obtain generic SQL execution. Future #10 implementation must prove
the OIDC/session/provenance boundary before exposing behavior.

## Findings and resolved design clarifications

### ASF-S01 — Failure budgets and internal rate outcomes

The first draft's generic zero-row finish failure could not distinguish the
approved 429 limit denial from capacity 503. Raising a SQL exception to encode
that outcome would also roll back the invitation-attempt budget that must remain
consumed on ordinary failed eligibility. This was a design blocker.

The revised design consumes the invitation-attempt budget outside an inner
exception subtransaction. Identity/invitation/user-issuance/session/finalization
writes all occur inside that inner atomic unit and roll back together. Ordinary
denials return normally, preserving the outer budget when the caller commits;
infrastructure transaction aborts fail closed and promise no persisted budget.
Known active identities ignore the supplied invitation and consume no invitation
budget. An issuance-limit increment remains inside the rollback boundary.

The wrapper result contract now carries only coarse approved outcome categories:
start returns ok/invalid/in_progress/unavailable; finish returns
ok/invalid/limited/unavailable. Successful authority fields are unchanged and
present only on ok. Every private identity/invitation/linkage denial produces
the identical invalid shape with all authority fields NULL. Only limited returns
the denying public window end needed for Retry-After; it exposes no count,
subject/key, scope, identity metadata or private failure reason.

Security accepts this as an implementation refinement of the already approved
generic failures and public 409/429/503 behavior, not permission to broaden the
privileged success payload or distinguish private account existence. Exact
catalog result-shape and normal-return/commit tests are required. A caller that
rolls back ordinary generic failure would not satisfy this contract.

### ASF-S02 — Unknown-subject preallowlist storage

The approved contract permits controlled issuer/subject admission while keeping
an exact seven-table control-plane exception. An eighth allowlist table or
nullable live external-identity linkage would violate that boundary.

The concrete design instead adds nullable admission metadata to invitation.
Owner-only allowlist rows bind a canonical issuer and bounded ASCII subject;
their opaque random digest is never distributed as a bearer. A partial unique
index prevents competing unused admissions. Unknown-subject finalization may
select and consume only the exact unexpired subject-bound admission, atomically
with its identity/session creation. Legacy NULL admission_kind means bearer,
without backfill. Known identities need neither path. Runtime has no direct
access, allowlist boolean or admission-management function. This representation
preserves the approved trust boundary; exact constraints, wrong-subject/expiry,
rollback and competing-admission tests are mandatory.

## Security requirements retained in implementation

1. Only additive 005_identity changes are authorized; original reviewed SQL and
   checksums remain unchanged. Nullable new session identity/CSRF fields make
   legacy rows invalid and untouchable by resolver, without reinterpreting or
   backfilling existing authority. Seven control tables remain owner-owned,
   no-RLS explicit exceptions with no PUBLIC/runtime table or sequence grants.
2. Exactly seven external auth wrappers, separately reviewed mark_catalog_ready
   and existing invoker context parser are callable. Helpers have no runtime or
   PUBLIC EXECUTE; overloads, argument/result shapes, fixed search paths,
   SECURITY DEFINER ownership and effective ACLs must reconcile exactly.
3. start/claim/finish/fail/limiter/session/ready mutations serialize on the same
   bounded transaction-scoped advisory lock. clock_timestamp is sampled after
   blocking acquisition, so a transaction begun before expiry cannot finish
   after it. No network operation occurs under this lock. All expiry equality
   cases deny. No caller-time or test clock input is installed.
4. A bound claim is one-shot, clears persisted verifier immediately and is never
   reopened. Start cannot supersede an unexpired claimed/succeeded binder.
   Duplicate UUID/state insertion rolls back prior invalidation/reservation.
   Finalization rechecks claimed binding and original unextended deadline.
5. Identity triple, necessary invitation consumption, issuance counter, new
   linked session and successful transaction status commit atomically. Disabled
   identity/user/tenant never becomes active/ready. Session UUID/digest conflicts
   must not leave bootstrap-only authority or consume a user issuance budget.
6. Resolver/touch validates exact external/user/tenant links and nonnull CSRF,
   active states, revocation and zero-skew absolute/idle deadlines. Touch is
   monotonic without extending absolute expiry. Revoke cannot race a session
   back into validity. The active cap and deterministic oldest revocation are
   inside the same serialized issuance transaction.
7. Rate windows/caps are fixed DB rules, counts saturate N+1, and denied earlier
   stages do not consume later budgets. Reserved capacity scopes cannot be
   caller-selected. Atomic reservations reconcile with actual physical rows:
   100000 transactions and 200000 counter-table rows including the two reserved
   rows. Cleanup runs once through IP-start/IP-callback limiter scopes, deletes
   at most 100 eligible rows per table using indexes and never evicts live work.
   Normal session/ready/health calls perform no cleanup or provisioning.
8. mark_catalog_ready(session_digest) derives its target only from a valid active
   linked session and permits only conditional pending-to-ready, idempotent at
   ready. This narrow signature is accepted; it cannot prove catalog success.
   Its only future caller is trusted login orchestration after the separate
   catalog public-port transaction succeeds. No target/state setter, middleware
   retry or arbitrary-request provisioning is permitted.
9. Exact function/table/SQL-site catalogs and independent mutations must detect
   missing binder/expiry/active/revocation guards, widened outputs/grants,
   duplicate verifier retrieval, legacy resolution, partial authority commits,
   missing caps/reservations and incorrectly rolled-back attempt counters.
   Test doubles/owner successes cannot establish runtime isolation evidence.

## Remaining evidence gate

This is a design review, not evidence that the functions work. Implementation
requires independent code/security reassessment against actual PostgreSQL
app_runtime, additive migration/recovery cases, bounded concurrent races,
clock-after-lock checks and privacy/result-shape oracles. The original RLS/pool/
architecture/API checks remain mandatory. Any new overload, authority input,
result field, helper privilege, control table, process or externally exposed
route requires renewed review.

No risk is accepted. SEC-01 completion still needs all applicable then-present
foundation evidence and catalog-provisioning boundary disposition; SEC-05's
provider/crypto/browser and trusted ActorContext evidence remains #10. Deployed
owner/runtime credential separation remains #16.

## Initial implementation findings

### ASF-S03 — Deadline sampled before later row-lock wait

Open; blocks implementation acceptance. The initial 005 implementation samples
_auth_now after the common advisory lock, but claim/finish subsequently acquire
row locks, and resolver/revoke/ready statements can wait on target row locks.
A controlled fixture connection can hold such a row across an authority deadline;
the waiter then continues with its earlier sampled time. Acquiring the advisory
lock does not prove that all subsequent row locking is nonblocking.

Required fix: acquire the relevant authoritative row locks in a consistent order,
then refresh DB clock and re-evaluate the original transaction/session deadlines
and active/revoked/linkage predicates before granting/touching authority. Add
row-lock barriers that cross original claim/finalization and session deadlines,
not only a wait on the advisory lock. No caller/test-time override is permitted.

### ASF-S04 — Caller timezone changes fixed lifetime arithmetic

Open; blocks implementation acceptance. SECURITY DEFINER does not reset the
caller's TimeZone. Adding interval '7 days' or '30 days' to timestamptz in a zone
with daylight transitions can differ from the approved UTC duration. Current
function search_path configuration alone does not fix this parameter.

Required fix: explicitly fix function timezone to UTC, or use reviewed fixed
second duration arithmetic throughout. Catalog configuration and tests must
prove that non-UTC caller timezone does not extend or shorten idle/absolute
session lifetime, login expiry or retention windows. UTC DB authority must not
depend on the caller remembering to set connection timezone.

## Issue #10 CSRF integration limit

resolve_web_session deliberately returns no stored csrf_digest and no raw token.
This review does not authorize broadening its least-result contract or granting
a direct control-table read for browser rendering. Issue #10 must prove the
approved HKDF/session-bearer/session-UUID verification and persisted-digest
semantics through its trusted identity/browser boundary, or return any needed
privileged contract change to independent review. No raw CSRF generation,
comparison, hidden-field rendering, cookie, OIDC or provider behavior has been
executed or certified by this database-only work.

## ASF-S03/ASF-S04 code remediation review

Reinspection of 005 confirms that claim resamples after its transaction row
lock; finish resamples and rechecks original claim/admission authority after
identity/admission/session locks and again after the private counter wait.
Resolver, revoke and ready first capture linkage, lock identity/user/tenant/
session rows in a consistent order, then resample time and re-evaluate exact
captured links, active/revoked state and deadlines. Counter consumption resamples
after counter/capacity locking and retries the correct aligned window when the
wait crosses a boundary. The start path also rechecks binding expiry after
capacity/pending-row waits and rolls back invalidation on expiry.

Seven-day idle, 30-day absolute and 24-hour retention arithmetic now uses fixed
604800/2592000/86400-second intervals instead of calendar days. This removes the
caller's timezone/DST influence while preserving DB-time authority.

Both findings are code-remediated; final closure requires the actual observed
row-lock-wait and fixed-DST non-UTC tests and final aggregate evidence below.
The implementation agent reports those focused cases passing. This reviewer
inspected the row-wait harness: it observes a real independent runtime PID
blocked by a fixture row lock, advances past the DB deadline before release and
checks denial, rather than assuming thread creation implies overlap. Fixed
known DST dates make the timezone oracle independent of the execution date.

## Final code and evidence disposition — 2026-10-23

**Pass: Issue #9 authentication database foundation.** ASF-S01/S02 are resolved
in the reviewed design and implementation; ASF-S03/S04 are resolved in code and
executed evidence. No unresolved security finding remains in this implemented
DB-foundation scope.

The final independently inspected 005 SQL SHA256 is
`4cad83d3b26ad8dab1abbb2666c21ed1a6db7c088cec844745009d55c91e04bc`.
The seven external auth wrappers, separately targeted mark-ready function and
five non-runtime helper signatures remain finite and catalog-checked; original
000..004 artifacts remain unchanged. Readiness now rejects effective direct
privileges on any of the seven control-plane tables, including column-only
privilege leakage, without reading private contents or widening access.

The coordinator reports the final canonical `make check` pass: **217 tests
passed, zero failed, zero skipped in 43.17 seconds**, including 98 auth cases,
28 migration cases and 16 runtime PostgreSQL cases. Lint/format (118 files),
strict mypy (38 source files), architecture/composition, unchanged generated
OpenAPI, wheel build and exact packaged-artifact checks all pass. The installed
wheel was separately imported from its installation and run under actual
uvicorn with runtime-only configuration: /live 200, /ready 200 and /login 404.
The process was stopped. Wheel SHA256:
`2443d184372667f43b24aab0925b519daa17213d4242e7bffb18bd6c816a39cf`.
One upstream Starlette/httpx deprecation warning was not suppressed. The reported
uv cache warning was separately checked not to add artifacts to package inventory.
These counts are the coordinator's recorded final run; this reviewer inspected
code, test oracles and the SQL hash without concurrently rerunning destructive
shared-database tests.

The reviewed evidence includes observed independent-backend advisory and row
blocking, expiry after row waits for claim/finish/resolve/revoke/ready, fixed
known DST instants under non-UTC caller zones, one-shot claim and separate
finalization binder defenses, invitation/issuance rollback boundaries and fault
injection at each authority phase. Behavioral SQL mutants independently weaken
claim binder/expiry/status/reset, finalizer binder, session active/revocation/
expiry/legacy guards, capacity reservation, failed-attempt retention and partial
bootstrap atomicity; their negative oracles detect those changes. Capacity
admission uses actual row populations, reconciles protected reservations,
releases/re-admits capacity and preserves existing-session resolution. Mixed
cleanup work obeys the combined 100-row bound and exact 24-hour equality cutoff,
with one-microsecond and fresh-row controls. Fixture-only function changes assert
restoration; no production bypass/clock argument/helper privilege was added.

### Scope completion and remaining external gates

This supersedes the earlier historical missing-DB-function blocker: the approved
ADR-011 seven-table/function foundation and its then-present DB evidence are now
implemented and reviewed. Security review identifies **no remaining #9 database
foundation blocker**. Issue #9's DB work may proceed through its normal human PR
review; it need not wait on the #10 behavior it is intended to enable.

This is the SEC-01 **foundation implementation evidence pass**, not global
SEC-01 or SEC-05 closure. Issue #10 must still implement/prove OIDC, crypto,
browser/cookie/CSRF behavior, trusted ActorContext issuance, application
use-case authorization, explicit tenant-scoped repository SQL and login-only
catalog provisioning/ready orchestration. Those are later integration gates,
not evidence silently supplied by these DB tests or a circular prerequisite for
merging the foundation. Issue #16 still owns deployed owner/runtime credential
separation. No production exposure, real-user-data approval or risk acceptance
is granted.
