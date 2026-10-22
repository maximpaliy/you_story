# Independent test-design review — Issue #6

- Date: 2026-10-22
- Reviewer: independent test-design reviewer
- Material: auth-session-contract.md, test-design.md (including AUTH6-23–26),
  proposed ADR-011, approved ADR-007/008/009 and testing strategy, AGENTS.md
- Verdict: pass after focused design remediation; material ADR-011 amendments
  still require owner disposition and reconciliation before implementation

This reviews the proposed test design, not executable tests or running
application behavior. No application, browser or database suite was run for this
review. SEC-05 implementation evidence remains open.

## Findings and dispositions

| ID | Initial severity | Finding | Disposition |
| --- | --- | --- | --- |
| TDR6-01 | High | AUTH6-22 could not prove hard 24-hour retention/bounded growth with traffic-only cleanup; crashed claimed rows lacked a precise fate. | Resolved at design level. Section 8 states lazy deletion eligibility rather than a wall-clock erasure promise, expires pending/claimed authority independently, clears persisted verifier at claim, fixes deletion cutoffs and 100-row per-table cleanup budgets, and caps admitted transaction/counter storage. Revised AUTH6-22 tests idle periods, claim crash, exact cutoff, fresh rows, large backlog, capacity boundaries and concurrent admission/reservation reconciliation. |
| TDR6-02 | High | New AEAD verifier storage lacked dedicated integrity/substitution tests. | Resolved. AUTH6-24 adds a valid-decrypt control, ciphertext/tag/nonce tampering, transaction/client associated-data substitution, wrong/missing/unknown key and malformed envelope. Failures precede exchange, leave claims consumed with no stored verifier, and grant no bootstrap/session authority or secret leakage. |
| TDR6-03 | Medium | Rate-limit consumption/order and exact window oracles were underspecified. | Resolved. Section 8 defines DB-aligned half-open windows, per-scope limits/order, stop-on-denial, saturation, invitation-attempt semantics, final-transaction issuance rollback and exact Retry-After. Revised AUTH6-18 covers boundary equality, scopes, replica races, denial side effects, unverified identity isolation and separate capacity503 behavior. |

## Additional focused checks

AUTH6-23 now distinguishes single-state replay from overlapping flows sharing a
binder: barriers hold T1 after claim, reject T2 during authoritative claimed or
successful windows, test lost-cookie delivery and stale finalization, preserve
independent browsers and require no account switch if an authenticated session
appears. This supplies a testable oracle for the new binder serialization rule.

AUTH6-25 distinguishes pre-validation callback control-state writes from identity,
session or catalog authority. HEAD must not dispatch callback; failed validation
cannot bootstrap/issue/ensure. Ordinary product GET nonmutation assertions should
be read as no domain mutation or provisioning, not denial of the separately
specified successful session last_seen touch.

The fixture/layer design exercises owner public ports, production HTTP/browser
controls, real app_runtime functions and exact control-table ACL inventories.
AUTH6-01–26 cover provider claims/PKCE/JWKS negatives, invitation and bootstrap
atomicity, separate catalog readiness, expiry equality, session issuance caps,
revocation/touch races, authenticated CSRF derivation and leakage detection.
Independent mutations and positive scanner/crypto controls prevent trivial or
masked passing evidence. No further blocking test-design finding was identified
in the focused re-review.

## Final focused amendment review

AUTH6-26 supplies a concrete oracle for the signed browser-binding envelope:
nonce/issued/expiry/version/MAC integrity, canonical encoding, size bound,
cross-domain cookie/proof substitution, expiry equality and no extension through
re-render/start. Positive repeated-render and fresh-expired-binder controls
address recovery of the original expiry without a new persistence table.
The signed expiry is distinct from the cookie's browser-enforced Max-Age;
server validation never trusts an unsigned timestamp. No new test-design blocker
was found in this addition.

Section 10 now names the runtime wrapper boundary. The AUTH6-21 extension checks
wrapper/overload ACL reconciliation, denial of internal bootstrap/capacity/
cleanup helpers and least-result return fields using secret canaries. This
provides an explicit test-design oracle for the narrower finish_web_login
transaction orchestration; it does not waive verification of actual SQL
signatures, safe search paths or runtime privilege catalogs at implementation.

## Remaining gates and implementation evidence

Pass is conditional on the reviewed policy oracle, including explicit lazy
retention semantics and admission caps; it does not accept privacy risks or
approve material changes to ADR-008/009. Owner approval, architecture/security
review and accepted-ADR reconciliation remain separate gates. Exact function/
table/column ACL inventories, indexed plans, capacity reservation invariants,
lock order and bounded work require implementation evidence under MVP-06/07.

The implementing suites must record current source/fixture revision, intended
and nonzero executed counts, pass/fail/skip, role/tool versions, runner exit
status and sanitized persisted-state/race outcomes. Designed cases are not
executed cases. No implementation or deployment authorization is granted here.
