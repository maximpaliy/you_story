# Independent architecture review — Issue #6

- Date: 2026-10-22
- Reviewer: independent architecture-review agent
- Materials: auth-session-contract.md, test-design.md, proposed ADR-011 and
  approved ADR-007/008/009; AGENTS.md
- Verdict: pass after remediation at design level; ADR-011 owner approval and
  implementation evidence remain separate gates

This reviews design only. It neither reports executed authentication tests nor
supplies owner approval of ADR-011's material amendments.

## Findings and dispositions

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| AR6-01 | Medium | A crash after login-transaction claim could leave claimed state and persisted verifier ciphertext without a specified terminal/cleanup path. | Resolved. Claim returns and immediately clears the persisted ciphertext. Original deadline governs claim/finalization independently of cleanup; expired claimed rows never reopen. Section 8 specifies lazy deletion eligibility, bounded indexed batches and admission caps; revised AUTH6-22 covers crash, equality expiry, backlog and capacity races. |
| AR6-02 | Medium | The GET callback exception required all auth-state changes after OIDC validation although claim/counters necessarily precede validation. | Resolved. Section 4 and ADR-011 distinguish bounded pre-validation claim/counter/terminalization/cleanup from authority changes after valid binding/claim and OIDC. AUTH6-25 checks denied callbacks cannot bootstrap, issue sessions or invoke catalog provisioning. |
| AR6-03 | Medium | Original binder expiry could not be recovered from a random-only cookie on repeated login-form renders. | Resolved. Section 2 now defines a signed fixed-schema envelope with random nonce, original issued/expiry timestamps, canonical encoding and a separate HMAC domain. GET/start/callback verify original expiry without another table or prior hidden proof. AUTH6-26 covers repeated rendering, shortened remaining lifetime, tampering, domain confusion and expiry equality. |

## Architectural assessment

The explicit five-to-seven control-plane amendment is appropriate: anonymous
login transactions are not overloaded onto linked sessions, direct runtime table
access stays denied, and named narrow owner-function inventory tests preserve
ADR-008's least-result boundary. Actual SQL function signatures and ACL manifests
must reconcile in implementation; descriptions do not grant generic privileged
access.

Identity/bootstrap/invitation/session issuance and successful login finalization
now share a mandatory atomic identity transaction. Catalog readiness remains a
separate actor-scoped module transaction and cannot revive disabled accounts or
run from ordinary requests. Binder start/claim/finalize serialization prevents
overlapping claimed callbacks from issuing competing sessions in one binding.

The proposed HKDF CSRF derivation explains and narrowly amends ADR-009's
otherwise unrecoverable independent-random-token/digest-only rendering contract.
It retains high-entropy session input, domain separation, hidden-field delivery,
digest comparison and invalidation, without reversible session storage. It is a
material crypto amendment requiring owner disposition after independent review,
not an unannounced exception or a new authentication technology.

No Android/Telegram, linking, destructive action, admin-session UI, worker or
additional service design is needed now. Runtime cryptographic implementation,
OIDC library behavior, SQL atomicity, role isolation, logs and browser evidence
remain later implementation/security/code review gates. SEC-05 remains open for
that evidence even after a design pass.

## Final focused re-review

The signed binder envelope closes the last representation gap without granting
product access or adding an eighth control table. Cookie metadata is integrity
protected; binder digest derives from the random nonce, so serialization changes
cannot create an alternative identity for one binding. Re-rendering does not
renew the authoritative lifetime.

Section 10 now names the external privileged wrappers and least-result inputs/
outputs, confines finish/bootstrap/session finalization to the atomic owner
wrapper, and removes runtime execution of internal bootstrap/capacity/cleanup
helpers. Exact SQL overloads, ACLs, safe search paths and result shapes must be
reconciled mechanically during implementation. This resolves the earlier
nonblocking function-inventory precision point at design level.

No further architecture blocker was found in this focused re-review. The lead
must preserve proposed status until owner disposition of ADR-011's explicit
seven-table control-plane and GET/CSRF amendments, then reconcile the accepted
ADR-008/009 text and manifests. No credentials, running endpoints, SQL migrations
or executable authentication tests were produced by this review.
