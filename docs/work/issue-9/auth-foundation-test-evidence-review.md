# Independent test evidence review — Issue #9 authentication database delta

- Date: 2026-10-22
- Reviewer: independent `test_review` agent, not the test implementation author
- Baseline: reviewed A01–A14 in auth-foundation-test-design.md
- Disposition: pass for the scoped authentication database foundation after
  remediation and coordinator-reported final canonical execution
- Execution: this reviewer performed read-only test/source review, avoiding
  destructive PostgreSQL execution concurrent with implementation/root agents

## Coverage and trustworthy oracles

The probes call only the reviewed fixed wrapper allowlist using real
`app_runtime` credentials. Positive issuance checks linked identity/session rows,
exact digest/CSRF storage, equal initial timestamps and fixed 2592000-second
absolute lifetime. Failure probes inspect persisted claims, erased ciphertext,
invitation consumption, authority rows and both budget categories. Fault triggers
after each authority phase verify atomic rollback while preserving the committed
claim and outer invitation-attempt count. Raw start/finish result checks now
separately assert invalid/in_progress/limited/unavailable and NULL authority
fields, rather than accepting every failure as an empty result.

Concurrency tests observe independent caller PIDs actually waiting on the auth
advisory lock before release. Separate row-lock barriers test stale clock samples
across claim/finish/resolve/revoke/ready waits, including real-clock deadline
crossing. Both resolver-before-revoke and revoke-before-resolver orders hold the
first runtime transaction until the second PID is observed blocked behind it.
Exact equality probes use the reviewed owner-only fixture clock substitution;
the helper's original definition is restored and asserted exactly. Production
clock behavior and fixture-substituted boundary behavior are distinct evidence.
Non-UTC/DST probes verify durations cannot change with session timezone.

Capacity probes fill actual 100000 transaction and 200000 physical counter rows;
N-1 concurrent admission has exactly one winner and full admission cannot block
valid-session resolution. Cleanup releases counter capacity for re-admission.
Mixed 80-delete/20-expire work proves the combined 100-row budget, fresh-row
preservation, no second cleanup in later stages, and reservation counts 84/85
that release only deleted rows. Ordinary session resolution preserves control
transactions and counters. Oldest-session eviction is tested independently from
the same-window issuance limit, so rate denial cannot mask eviction behavior.

Behavioral mutation controls independently break claim/finalizer binder,
claim expiry/status/one-shot state, active-user/revocation/absolute/legacy-CSRF
session guards, admission reservation conservation, durable failed-attempt
budget and failed-finish atomicity. They call the altered function, then prove
the original outcome/state oracle rejects it; changing only a fingerprint is not
substituted for behavioral proof. Each mutated function definition is restored
and checked. Positive allowed calls and rejected baselines prevent an
always-failing oracle from passing.

## Schema/migration and unchanged-surface reconciliation

Database-agent tests preserve populated 004 user/tenant/external/invitation/
session values across 005; new legacy linkage fields stay NULL and runtime
resolution returns no fields without touch. Every real 005 interruption phase
checks the original full 004 catalog before retry. Exact auth catalog golden
includes signatures/results/owner/security/search paths/ACLs/bodies; runtime
inventory rejects unknown overloads, PUBLIC/helper execution and direct control
access. That golden is independently reviewed implementation evidence, not
accepted merely because regeneration makes tests green.

Root-owned baseline checks cover unchanged health-only routes/OpenAPI, artifact
composition, readiness privilege failure and original pool/RLS/architecture
mutations. The auth delta has no Python login/provider/browser adapter or logging
sink; its safe least-result/error contracts do not establish future HTTP/provider
redaction success. No OIDC/AEAD/HKDF/browser or production ActorContext-issuer
case is claimed by these DB probes.

## Findings and dispositions

The rolling findings on unobserved races, collapsed failure categories, missing
behavioral mutants, incomplete mixed cleanup, counter N-1/release and clock
restoration have been resolved in the final reviewed test source. The finalizer
binder gap found by security review has a direct regression and independent
mutation test. Both revoke/resolve orders now have controlled observed waits.

The final A12 cleanup-equality finding is resolved by
`test_cleanup_eligibility_is_inclusive_at_exact_retention_deadline`: the fixed
clock deletes equality-eligible transaction/counter rows, retains +1 microsecond
controls and fresh rows, then deletes the controls after that microsecond. Both
reservation counts match actual rows at each step. The counter fixture isolates
the cleanup comparison; separate producer tests establish DB-aligned windows.
The author reported this focused case passed once (0.46s); root retains the final
canonical execution record.

The coordinator reported the final canonical result: **217 passed, 0 failed,
0 skipped in 43.17s**, including 98 authentication database cases, 28 migration
cases and 16 runtime PostgreSQL cases. Lint/format (118 files), strict mypy
(38 source files), architecture/OpenAPI, wheel build and artifact checks passed.
The installed 005 wheel served `/live` 200 and `/ready` 200 while `/login` was
404 under actual Uvicorn with only the runtime credential; that process was
stopped. One upstream Starlette/httpx warning was not suppressed.

These execution results were supplied by the coordinator, who ran the canonical
checks serially on the dedicated disposable database; this reviewer did not
independently execute destructive tests. The review contribution is source,
oracle, coverage, mutation and boundary assessment plus remediation verification.
Exact command/environment/revision details are retained in the work verification
record. A test-source review is never substituted for the reported actual run.

## Scope limit

SEC-05 and catalog/ActorContext/login orchestration remain open. This review
approves the scoped DB-only test coverage and recorded execution evidence; it cannot close those later gates or authorize
HTTP authentication exposure. Independent security/code review remains required.
