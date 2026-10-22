# GitHub Issue #6 — Web authentication and session security

## Current status

Issue #6 (`MVP-03`) now has a concrete [auth/session contract](auth-session-contract.md)
and [test design](test-design.md). Independent [architecture](architecture-review.md),
[security](security-review.md) and [test-design](test-design-review.md) reviews
passed after remediation. Cookie decisions remain approved as before.

The owner approved [ADR-011](../../architecture/decisions/011-web-login-transaction-and-session-lifecycle.md)
on 2026-10-22. ADR-008/009 now incorporate the seven-table control-plane,
validated callback GET and HKDF CSRF amendments. **Issue #6's design scope is
complete and ready for merge and GitHub issue closure.** This records design
acceptance, not permission to bypass other feature/test gates or production
approval. SEC-05 remains open for MVP-07 implementation evidence and independent
security/code review; no application tests or authentication implementation ran.

## Cookie decision baseline

| Property | Effect | First-increment baseline |
| --- | --- | --- |
| Name | Selects the cookie the server reads. Names are application-defined and are not centrally registered. A later rename invalidates existing browser sessions. | Keep ADR-007's `__Host-you_story_session`. The `__Host-` prefix makes supporting browsers reject the cookie unless it is `Secure`, has `Path=/`, and has no `Domain` attribute. |
| Path | Controls which request paths receive the cookie; it is routing scope, not an authorization boundary. Cookies with the same name and different paths can create ambiguous handling. | `Path=/`, because the session applies to the whole application and the `__Host-` prefix requires it. |
| Domain | If present, permits the cookie on the named host and matching subdomains. If absent, the cookie is host-only and is returned only to the exact host that set it. | Omit `Domain`. Do not use `.example.com` or the eventual parent domain: sibling subdomains do not need this bearer credential. |
| Persistence | `Max-Age` or `Expires` makes a cookie persistent across browser sessions until its deadline (subject to browser eviction). Omitting both creates a browser-session cookie, but the browser defines when that session ends and may restore it. | Use `Max-Age=2592000` (30 days), approved by the human owner on 2026-10-03. Server-side expiry and revocation remain authoritative. |

`Secure`, `HttpOnly`, and `SameSite=Lax` remain the accepted ADR-007 baseline.
They respectively restrict transport to secure requests, hide the value from
script cookie APIs, and limit cross-site attachment. They do not replace CSRF,
XSS, session validation, or server-side revocation controls.

## Approved persistence decision

Use a persistent cookie with `Max-Age=2592000` (30 days), optionally accompanied
by a matching `Expires` value for compatibility. This lets a valid session
survive a browser restart. PostgreSQL still enforces the seven-day idle and
30-day absolute deadlines, so possession of an unexpired cookie never extends a
server session. Logout revokes the stored session and expires the browser cookie
using the same name, path, and domain scope.

The alternative is to omit `Max-Age` and `Expires`. That improves the intended
close-browser sign-out behavior but does not guarantee it because user agents
may restore browser sessions. It also does not replace the seven-day idle,
30-day absolute, logout, or revocation checks.

## Registration and deployment implications

- The cookie name, path, and domain scope have no external registry.
- The production hostname must exist in DNS and TLS configuration, but it is not
  copied into the cookie because `Domain` is omitted.
- Google OAuth client configuration is separate: every complete callback URI
  (scheme, host, port where applicable, and path) must be registered as an exact
  authorized redirect URI. This does not register or widen the session cookie.
- Each environment should use its own host and OAuth client/redirect allowlist.
  A host-only cookie set by one environment is not sent to another hostname.

## Approval outcome

The human owner approved the persistent option on 2026-10-03:

- **Persistent for at most 30 days:** convenient across browser restarts, with
  the seven-day idle and 30-day absolute limits enforced by the server.

All other cookie properties above are consequences of accepted ADR-007 rather
than new choices.

## Completion evidence

- **Changed:** Recorded cookie semantics, the accepted baseline, and the one
  remaining persistence decision.
- **Verified:** Reconciled the clarification with ADR-007, SEC-05, and the test
  strategy.
- **Unresolved:** No remaining Issue #6 design blocker; implementation evidence remains later. Deferred destructive and
  client/linking flows remain unavailable, not silently approved.
- **Security review:** Passed after design remediation; runtime evidence pending.
- **Production implementation:** Not started or authorized.

## Lifecycle and OIDC design draft

The owner authorized completing Issue #6 with reasonable defaults. The
[auth/session contract](auth-session-contract.md) and [test design](test-design.md)
now supply concrete lifecycle, callback, invitation, redirect/error and concurrency
rules. Their review status supersedes the earlier cookie-only progress notes once
reports below are finalized; they do not claim authentication is implemented.

[ADR-011](../../architecture/decisions/011-web-login-transaction-and-session-lifecycle.md)
explicitly proposes amendments for durable one-shot pre-authentication
transactions/shared rate counters, the exact OIDC callback GET exception, and
re-renderable session-bound CSRF derivation. The owner approved these material amendments after independent reviews;
ADR-008/009 now explicitly incorporate them. No runtime schema privilege was
granted by editing documentation.

Google API access to read the live Issue #6 body remains forbidden. The task is
based on the repository backlog, accepted ADRs and this conversation; no issue
comment, issue closure or production deployment has been performed.

## Review completion evidence

- Concrete defaults: 10-minute browser-bound one-shot login; invitation 24-hour
  lifetime; exact destination enum; seven-day idle/30-day absolute sessions;
  ten-device-session bound; atomic identity/session/invitation finalization;
  separate login-only catalog reconciliation; fixed rate limits and lazy bounded
  cleanup. These defaults and amendments now have explicit owner approval following
  independent review.
- Reviews resolved browser-binding races, issuance atomicity, signed binder
  expiry, callback pre-validation authority boundaries, encrypted-verifier
  tampering, cleanup semantics and per-scope rate-limit oracles.
- AUTH6-01–27 are designed cases with real browser/public-port/PostgreSQL
  evidence requirements; none is reported executed.
- Documentation links/field inventories and whitespace checks were validated.
  All application logic/dependencies/runtime services remain unchanged.

## Approval and completion

The owner approved the reviewed amendments on 2026-10-22 after an explanation of
request-triggered state, cleanup, counters and key requirements. Approval records
a product/architecture decision; it does not substitute for independent security
judgment or accept any security risk. Reconciliation was checked against the
reviewed contract and inventories. GitHub closure/merge are not performed by
this local design-complete status.

## GitHub PR #23 review follow-up

The [transaction UUID / verifier-encryption comment](https://github.com/maximpaliy/you_story/pull/23#discussion_r4353817634)
identified an ordering conflict in start_web_login. Trusted application code now
generates the transaction UUID before encryption and supplies that same UUID to
the fixed owner function. HTTP callers cannot select it; duplicate UUIDs cannot
overwrite an existing row. AUTH6-27 covers round-trip decryption, wrong-ID
substitution, duplicate rejection and fresh encryption on a new-ID retry.
This corrects the implementability of the accepted AEAD boundary without adding
new database access, ciphertext update/reservation APIs or product behavior.
