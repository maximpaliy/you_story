# Independent test-design review — Issue #9 authentication database delta

- Date: 2026-10-22
- Reviewer: independent `test_review` agent, not the delta design author
- Baseline: accepted ADR-011/current ADR-008; owner-approved Issue #6 AUTH6
  contract/test design; merged foundation at `ce4b102`
- Material: auth-foundation-design.md and auth-foundation-test-design.md
- Disposition: pass after two oracle clarifications were resolved; actual
  implementation evidence and independent security/code review remain required

## Findings

1. **Session-cap eviction and issuance-rate denial must be independent cases.**
   The eleventh issuance within the same user fixed window is denied by the
   issuance budget, so it cannot prove the oldest active session is revoked by
   the ten-session cap. Arrange ten valid older sessions independently or cross
   a rate window, prove eviction's deterministic `(created_at,id)` ordering and
   keep the same-window eleventh denial as a separate no-authority-write test.
   **Resolved:** A10 now explicitly separates owner-arranged prior sessions or
   second-window issuance from same-window rate denial.
2. **Real-clock expiry equality needs an explicit trustworthy oracle.** Setting
   a fixture deadline to its current clock and later calling a wrapper proves
   expiry after the deadline, not equality with the wrapper's later microsecond
   clock. Define how exact equality detects an accidental non-strict comparison:
   use fixture-only semantic expression replay or transactionally restored
   function clock substitution, with actual-clock before/after and lock-wait
   integration cases. No production clock override/test bypass may be installed.
   **Resolved:** the design permits only a private owner-only `_auth_now()`
   real-clock helper, with fixture-only replacement and required definition
   restoration/catalog assertion. Runtime EXECUTE is denied, no caller time or
   GUC override exists, and actual-clock/lock-wait cases remain mandatory.

## Assessment

A01–A14 cover the relevant DB-only slice with real `app_runtime` calls and exact
catalog reconciliation. Particularly important are seven-table/overload/ACL/
least-result inventory, populated `004_media` upgrade without checksum rewrite
or legacy-session revival, committed one-shot claim with erased ciphertext,
inner finish rollback while retaining failed invitation-attempt budget, distinct
user issuance budget rollback, protected admission reservations and bounded
cleanup, and active linked session/revocation/ready targeting.

Every required denial needs an allowed positive baseline, persisted row
postconditions and result-shape assertions. Concurrency uses independent
connections and observed lock barriers. Removing a single binder, expiry,
linkage, atomicity, reservation or callable-audience guard must make the relevant
case fail while other layers remain intact. Repeated calls to otherwise serial
functions are not race evidence. A failing SQL exception alone does not prove
that invitation, identity, session and budget writes rolled back.

The exact existing 000–004 catalog/checksums remain the supported populated
upgrade oracle. 005 DDL/ledger failure injection must prove no half-created
wrapper or accidentally executable helper survives, retry reaches the exact
reviewed head, and the runtime can neither migrate nor read control tables.
Owner/superuser fixture setup is never runtime-isolation evidence.

No provider, browser, HTTP login, crypto or production ActorContext issuer is
implemented by this delta. Tests prove absence of those registered surfaces;
they do not claim AUTH6 provider/CSRF/OIDC/AEAD/browser cases passed. Catalog
ensure/login-only orchestration and complete ADR-008 provisioning evidence stay
open. SEC-05 cannot close from this database test design or its eventual pass.

## Re-review conclusion

The revised design resolves both identified false-pass risks and may proceed to
implementation within this DB-only scope. A01–A14 must actually execute; exact
DDL/body/ACL fingerprints and positive/mutation controls must be independently
reviewed, rather than refreshed until green. Reports must distinguish actual
production-body clock behavior from fixture-substituted equality oracles.

No implementation tests were run for this design review. Final evidence must
record nonzero intended/executed case counts, zero required skips, real runtime
role and sanitized persistent-state/race outcomes, plus all remaining catalog/
ActorContext/HTTP/provider/browser gates. This review does not close SEC-01 or
SEC-05 and does not authorize exposing authentication routes.

## Safe failure-result refinement re-review

The refined start/finish discriminants fit this pass: exact success fields appear
only on `ok`; all invalid identity/invitation/linkage states share `invalid` and
NULL fields; `limited` carries only its denying window end and `unavailable` no
private capacity metadata. Tests must assert raw discriminants, not collapse all
failures to an empty result. Normal failed finish must commit its outer attempt
counter while rolling back the inner authority/issuance unit; infrastructure
abort is separately fail-closed and cannot promise counter persistence.
