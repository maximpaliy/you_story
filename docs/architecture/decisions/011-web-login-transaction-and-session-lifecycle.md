# ADR-011: Durable web login and session lifecycle

- Status: Accepted — owner approved 2026-10-22
- Related issue: #6 / MVP-03
- Baseline: accepted ADR-007/008/009 and Issue #6 cookie decision

## Context

A concurrent/replayed OIDC callback must not exchange a code or issue a session
twice. A browser cookie alone cannot establish durable one-shot consumption.
The existing five control tables have no anonymous login transaction identity;
linked login sessions must not be overloaded as anonymous sessions.
ADR-009's stable independent random CSRF token cannot be recovered from its
stored digest for rendering later pages. These gaps require explicit proposals,
not silent changes to already accepted isolation or cryptographic contracts.

## Decision

Adopt the concrete [authentication contract](../../work/issue-6/auth-session-contract.md)
and [test design](../../work/issue-6/test-design.md) as independently reviewed and owner-approved.

1. Amend ADR-008's exact authentication-control-plane manifest from five to seven
   tables by adding identity.login_transaction and identity.auth_rate_limit.
   Keep no runtime/PUBLIC table access, app_owner ownership, safe fixed
   security-definer function boundaries and no tenant RLS for these explicit
   pre-authentication stores. This is no blanket exception for future tables.
2. Consume a bound 10-minute state transaction atomically before code exchange;
   failures/crashes require a new flow. Retain only digests except an AEAD
   encrypted PKCE verifier, cleared atomically on claim; failures never reopen it. Rate counters are
   bounded keyed digests with fixed windows, not another service.
3. Narrowly exempt exact Google callback GET from ADR-009's nonmutating-GET
   rule: pre-validation writes are limited to rate counters, transaction
   claim/terminalization and bounded cleanup; identity/session authority and
   catalog orchestration require browser binding, one claim and full OIDC
   validation. Binder start/claim/finalize are serialized to prevent overlapping
   flows issuing competing cookies. All product GET/HEAD/OPTIONS remain nonmutating; logout stays protected POST.
4. Amend only ADR-009 CSRF generation to HKDF-SHA256 from the random session
   bearer and session UUID, with a fixed domain label. Keep its stored digest,
   hidden-field delivery and other browser controls unchanged. No raw CSRF
   persistence or extra readable cookie is introduced.
5. Preserve seven-day idle/30-day absolute session limits, rotation, independent
   sessions, fixed destinations, login-only catalog readiness and disabled-state
   checks. Use the contract's atomic concurrency/expiry/revocation rules.

## Alternatives

Browser-only consumption leaves replay races; raw verifier cookies expose more
secrets; anonymous rows in linked login_session weaken reviewed linkage rules.
A Redis auth store adds an unnecessary service. Encrypted raw CSRF persistence
could support re-rendering but introduces credential/key storage; deriving from
the existing bearer needs no reversible stored session credential.

## Consequences, review and rollback

This adds bounded pre-auth database state, cleanup/counter work and application
key requirements. The owner approved the control-plane expansion and browser/
crypto amendments on 2026-10-22 after independent reviews. ADR-008/009 now
incorporate the exact amendments and link here. Manifests/role tests must match
before implementation is accepted; no undocumented bypass is authorized.

No account linking, mobile/Telegram, privileged action UI, worker or infrastructure
is enabled. Issue #6 design completion does not close runtime SEC-05 evidence.

## Independent review disposition

[Architecture](../../work/issue-6/architecture-review.md),
[security](../../work/issue-6/security-review.md) and
[test-design](../../work/issue-6/test-design-review.md) reviews pass after
remediation. Findings and their dispositions remain recorded in those reports.
No runtime evidence or owner acceptance is supplied by independent review.
The signed nonrenewing binder envelope and exact function inventory in contract
sections 2/10 are part of the reviewed design. No unresolved review finding
requires further feature scope. Owner approval and ADR reconciliation are now
recorded; runtime verification remains for the implementing slices.
