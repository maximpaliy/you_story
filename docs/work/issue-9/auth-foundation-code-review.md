# Independent code review — Issue #9 authentication database delta

- Date: 2026-10-22
- Reviewer: `/root/architecture_review`, independent of implementation authors
- Status: **final scoped code-review pass** for the implemented database foundation; independent security disposition remains separately recorded
- Scope: additive identity migration 005, migration registration/runner, runtime readiness and architecture/artifact boundaries

## Static review

Reviewed the full initial 005 SQL against accepted ADR-008/011, the approved
Issue #6 contract and the independently reviewed authentication-foundation
design. No new blocking architecture or non-security correctness finding was
identified in this initial source review. The following properties are explicit
in the reviewed implementation and require the corresponding executable evidence:

- Original migrations 000–004 are unchanged. Revision 005 alters only identity-owned objects, adds exactly two control-plane tables and leaves old session values intact. Nullable external-identity/CSRF columns cause incomplete legacy sessions to fail resolution rather than gain a fabricated association. Same-schema composite linkage constrains identity/user agreement.
- Admission-kind metadata stays inside the existing invitation table. Unknown allowlisted subjects do not require precreated identity authority, an eighth exception table, a caller allowlisted boolean or an exposed admission-management function. Identity/session/invitation writes occur inside the protected finish unit.
- Start, claim and finish serialize control-plane state and sample authoritative time after the auth-control lock. Claim returns one verifier and clears the stored copy; terminal states cannot reopen. Finish rechecks original binding/status/expiry and active identity linkage before authority changes.
- Invitation-attempt consumption precedes the inner issuance subtransaction; ordinary downstream failure rolls back authority and issuance-budget changes while retaining the attempt. Known identities do not consume supplied invitations. Generic result paths disclose no identity tuple.
- The seven fixed runtime wrappers plus the separately reviewed ready transition have exact EXECUTE grants; private clock/digest/lock/cleanup/consume helpers are not runtime-callable. Safe fixed search paths and schema-qualified identity data references preserve the privileged boundary.
- Session issuance, active-session counting/oldest eviction, resolve/touch, revocation and ready targeting use the approved linked lifecycle shape. Ready marking does not touch catalog tables or create a public digest-ready API. Future public actor/session matching and typed catalog success remain Issue #10 obligations.
- Capacity reservations include protected rows correctly; cleanup is bounded and invoked only from the IP limiter stages, so downstream start/claim/finish calls cannot repeat the batch in one auth operation. No resolver, health or domain-request cleanup/provisioning path is introduced.
- The manifest registers 005 separately. The runner validates an exact revision identifier rather than assuming owner names are unique; owner-based validation can still match either separately reviewed identity revision. Existing checksum and ledger-prefix guards remain intact.
- Readiness checks direct table and column privilege on all seven control-plane objects, actual runtime-role restrictions and the exact migration ledger. No HTTP route, ActorContext issuer, product repository or execution root is added.

## Internal failure representation review

The reviewed concrete SQL result discriminants are an internal representation,
not a changed public HTTP contract. Start distinguishes ok/invalid/in_progress/
unavailable; finish distinguishes ok/invalid/limited/unavailable. All invalid
identity eligibility/status/expiry combinations must retain the same invalid
result with NULL authority fields. Only limited includes its window end; no
private scope/key/count or identity-existence detail is allowed. In-progress is
the approved binder lifecycle conflict; unavailable is the bounded capacity/store
failure. These distinctions allow Issue #10 to implement its approved
409/429/503 behavior without interpreting exception text. Exact result-shape
and failure controls must be tested directly rather than normalized to `[]`.

## Required final evidence

No destructive PostgreSQL suite was run by this reviewer concurrently with the
implementation agents. The independent test-evidence review currently records
required concurrency/mutation/raw-result/cleanup/capacity gaps; those findings
are not waived by this static pass. Final approval requires the frozen source,
independent security/test dispositions, canonical lint/type/architecture/OpenAPI/
PostgreSQL checks, exact seven-table/function/ACL catalog evidence, additive
upgrade/failure evidence and actual built-wheel reconciliation.

SEC-05 HTTP/provider/browser/cryptographic evidence and ADR-008 catalog
orchestration/ActorContext evidence remain explicitly outside this delta. A
successful database-only review cannot close those gates or establish complete
Issue #9 acceptance by itself.

## Final static re-review of clock and lock corrections

2026-10-22: **static code review passes for SQL 005 fingerprint
`4cad83d3b26ad8dab1abbb2666c21ed1a6db7c088cec844745009d55c91e04bc`**.
Final execution/evidence approval is still pending; this does not waive any open
test-evidence finding or the independent security review.

Re-read the complete revised SQL and the current runner/manifest/readiness diff.
Counter consumption now locks its selected counter or capacity row, samples time
after the wait and restarts window selection if the fixed window changed. Start,
claim and finish recheck original authority deadlines after relevant row/capacity
waits. Finish locks candidate sessions before final issuance time and rechecks
both transaction and new-admission expiry after the issuance-counter operation.
Resolve, revoke and ready marking explicitly lock identity/user/tenant/session
rows in a consistent order, re-sample time and recheck original session linkage,
active states, revocation and deadlines. These changes close the previously
identified stale-clock possibility without a caller time input or broader grant.

Idle, absolute and cleanup intervals use fixed seconds (604800, 2592000 and
86400), preserving the reviewed elapsed-time semantics across non-UTC connection
time zones and daylight-saving changes. The shipped clock helper remains the
owner-only real-clock wrapper. No test clock override is granted to runtime.

The readiness diff denies every direct table privilege and every column-level
SELECT/INSERT/UPDATE/REFERENCES grant on all seven exact control-plane tables;
no direct private-data grant or new route was added. Exact-revision migration
validation correctly distinguishes 001_identity from 005_identity despite their
shared module owner. An independent `git diff --exit-code` check confirms all
000–004 migration artifacts remain unchanged; `git diff --check` passed.

No new static code blocker was found. The implementation owner reports 28
migration tests passed without skips and the new head catalog fixture written;
that is owner execution evidence, not an independent rerun. Authentication
concurrency/mutation suites, the frozen technical-SQL registry, canonical checks
and rebuilt-wheel checks must still pass before final implementation approval.
No destructive PostgreSQL test was run by this reviewer during shared fixture use.

## Completion-scope clarification

The architecture review's scope/dependency reconciliation applies here. Issue
#9 supplies the complete then-present database foundation and may advance after
its own reviewed adversarial, migration, security/code and canonical checks pass.
Issue #10's browser/OIDC/crypto, ActorContext issuer and login-only catalog
orchestration are not prerequisites to #9; the approved backlog orders #9 before
#10. Their pending evidence keeps global SEC-01/SEC-05 and later feature exposure
gated without creating a circular issue dependency. This clarification changes
no production code, required #9 database test or security acceptance threshold.


## Final scoped code-review disposition

**Pass for the implemented Issue #9 database foundation.** No outstanding
code-review finding remains. This disposition covers the unchanged final SQL
005 fingerprint `4cad83d3b26ad8dab1abbb2666c21ed1a6db7c088cec844745009d55c91e04bc`
and the reviewed migration, readiness and artifact changes. It supersedes the
rolling evidence-pending status above; earlier findings remain as review history.

The coordinator reports the final serial canonical run passed: **217 tests,
0 failed, 0 skipped in 43.17s**, including 98 authentication-database,
28 migration and 16 runtime PostgreSQL cases. Ruff lint and formatting
(118 files), strict mypy (38 source files), architecture, exact OpenAPI, wheel
build and exact artifact checks passed. The coordinator also reports that the
fresh installed 005 wheel ran under actual Uvicorn with only the runtime DSN:
`/live` 200, `/ready` 200 and `/login` 404; the process was then stopped. One
upstream Starlette/httpx deprecation warning was not suppressed. These are
coordinator execution results, not an independent destructive-database rerun by
this reviewer.

Independently re-ran the final source/composition checker and actual built-wheel
checker: both passed. Independently verified the SQL fingerprint above and wheel
SHA-256 `2443d184372667f43b24aab0925b519daa17213d4242e7bffb18bd6c816a39cf`.
The independent test-evidence review records remediation of its concurrency,
mutation, raw-result, cleanup, capacity and equality-boundary findings. Security
findings and their closure remain in the separate security review, not inferred
from this code-review pass.

With its own independent security disposition and owner review, Issue #9 is
ready to advance under the approved database-foundation acceptance boundary.
Issue #10 browser/provider/crypto, ActorContext and catalog-orchestration evidence
is cumulative future-slice work, not a reverse prerequisite for #9. Global
SEC-01/SEC-05 and authentication/product exposure remain separately gated; no
login route, product behavior or deployment is authorized by this review.
