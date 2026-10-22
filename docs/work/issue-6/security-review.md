# Independent security review — Issue #6

- Review date: 2026-10-22
- Reviewer: independent security-review agent
- Material: auth-session-contract.md (including signed binder and section 10),
  test-design.md through AUTH6-26 and proposed ADR-011,
  compared with approved ADR-007/008/009 and AGENTS.md
- Verdict: pass after remediation for the proposed authentication/session design;
  owner approval and accepted-ADR reconciliation remain required

This is independent document review, not authentication implementation evidence.
No application tests were run and no security risk is accepted. SEC-05 remains
open for MVP-07 implementation and independent security/code review.

## Findings and dispositions

### SR6-01 — Competing claimed flows can replace the browser session

Severity: Medium. Disposition: resolved in design.

The initial contract superseded only pending transactions. A claimed T1 awaiting
Google could overlap a newly started T2 under the same binder. Both callbacks
could have arrived without a session cookie and issue credentials for different
subjects. Inspecting each request's cookie could not detect another in-flight
response, permitting last-response session replacement.

Section 2 now serializes start, claim and finalization on the binder. An unexpired
claimed or succeeded transaction prevents a second start; only pending flows may
be superseded. Finalization rechecks binding authority and original deadline
inside the mandatory identity/session transaction. A stale claimed flow cannot
commit identity/session writes after expiry. Successful binding remains consumed
even if the cookie response is lost. AUTH6-23 explicitly exercises claimed and
succeeded-before-delivery races, stale finalization, failed-flow retry and an
independent browser. Implementation must prove these conditions with real
database barriers; a cookie check alone is insufficient.

### SR6-02 — Optional identity/session transaction boundary

Severity: clarification required. Disposition: resolved.

The earlier wording said bootstrap/session writes were atomic "when possible"
while requiring rollback of consumed invitations on failure. Section 5 now makes
bootstrap/resolution, necessary invitation consumption, session creation,
issuance-limit consumption and successful transaction finalization one mandatory
database transaction. The prior claim commits independently and remains consumed
on failure; bounded failure terminalization cannot reopen it. Catalog provisioning
correctly remains a separate tenant-context transaction under ADR-008, preserving
pending state and the active session on catalog failure.

## Focused reassessment

- Browser binding and pre-auth proof are separate from OAuth state, nonce and
  PKCE. New session bearer issuance defeats fixation; active-account switching,
  linking and unvalidated subject authority are excluded.
- OIDC uses fixed HTTPS endpoints, exact client/redirect settings, PKCE S256,
  strict issuer/audience/azp/claim/time checks, bounded key refresh and no
  token-directed key URLs. Token exchange ambiguity requires a fresh flow.
- AUTH6-24 now checks AEAD corruption, wrong keys and transaction/client AAD
  substitution. Claim returns then clears persisted verifier ciphertext;
  a crashed claimed flow cannot retrieve/reuse it through another function.
- Session lookup/touch, deadlines, cap enforcement and logout have explicit
  atomic conditions. Disabled state cannot be revived, revoked sessions cannot
  be touched back into validity and cookies do not extend absolute lifetime.
- HKDF CSRF derivation uses the high-entropy session bearer with distinct
  session UUID salt and fixed context; it retains digest-only persistence and
  hidden-field delivery. It is explicitly an amendment to ADR-009, not a false
  claim that its output is an independent OS-CSPRNG draw.
- Seven-table control-plane expansion remains narrow: no direct runtime/PUBLIC
  table access, safe owner-function boundaries, minimal return shapes and exact
  role/inventory tests. Authentication callback GET is a bounded reviewed
  exception, not permission for product GET mutations; AUTH6-25 distinguishes
  pre-validation counters/claim/cleanup from identity/session authority.
- Revised rate-limit order, fixed-window boundary behavior, trusted key
  derivation, generic errors, lazy indexed cleanup and hard admission caps give
  testable abuse/storage bounds. No exact wall-clock deletion promise is made
  during zero traffic. Admission/capacity state and bounded cleanup require real
  database implementation evidence rather than a claimed passing design test.

No additional blocking security design finding was identified in this revision.

## Final focused reassessment — signed binder and function boundary

The signed canonical login-cookie envelope makes original binder expiry
recoverable on later form rendering without trusting a browser-provided unsigned
timestamp or introducing another persistence table. Its nonce remains the binder
identity; issued/expiry/version are authenticated, the cookie and hidden proof
have distinct HMAC domain labels, and fresh proofs/transactions cannot renew
original expiry. DB-time validation, strict encoding/size and AUTH6-26's tamper,
cross-domain substitution, equality and no-renewal cases preserve the prior
one-authoritative-flow reasoning. The cookie is an anti-CSRF/login binding, not a
product session credential. No new security blocker was identified.

Section 10 now supplies a finite named wrapper inventory with constrained typed
inputs and least-result outputs. finish_web_login is the sole runtime-callable
identity/session finalizer; low-level bootstrap helpers, cleanup and capacity
mutators are private. AUTH6-21 tests hidden helpers/overloads as well as direct
table/sequence denial and result canaries. Exact SQL overload signatures and
ACLs remain implementation artifacts to reconcile against this reviewed boundary,
not permission for arbitrary security-definer functions. Existing context and
catalog-readiness functions remain their separate reviewed contracts.

The pass-after-remediation verdict is unchanged. These additions need inclusion
in the accepted ADR-011 amendment and its accepted-ADR reconciliation; they do
not remove owner approval or runtime evidence gates.

## Remaining approval and implementation gates

1. Owner must approve ADR-011's explicit amendments: five-to-seven control-table
   manifest, callback GET exception and HKDF generation rule. Then reconcile the
   exact accepted ADR-008/009 statements and manifests; proposed text alone does
   not authorize bypassing their current requirements.
2. Separate architecture and test-design reviews remain independent completion
   requirements. Success here does not mark their findings resolved by proxy.
3. MVP-07 must implement AUTH6-01–26 and the revised rate/retention oracles under
   production-equivalent browser, proxy, crypto and PostgreSQL configuration.
   Evidence must prove binding serialization, deadline/disabled-state guards,
   atomic invitation/session issuance, function ACLs, cap reconciliation,
   no secret leakage and no revocation resurrection.
4. Required operational keys/provider configuration must be injected securely;
   fail-closed behavior is retained if absent. No live credentials were requested
   or used for this document review.

With owner disposition, accepted-ADR reconciliation and the other design reviews,
Issue #6 may complete its design scope. SEC-05 stays open for implementation
evidence; no production deployment approval follows from closing the design issue.
