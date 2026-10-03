# GitHub Issue #6 — Web authentication and session security

## Current status

Issue #6 (`MVP-03`) has entered security design. ADR-007 fixes the cookie
attributes, and the human owner approved the persistent 30-day option documented
here on 2026-10-03. The remaining session/OIDC lifecycle, security review and
test-design work must still be completed before implementation.

No authentication implementation is authorized by this clarification.

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
- **Unresolved:** The remaining Issue #6 lifecycle, OAuth-error, redirect,
  reauthentication, security-review, and test-design work.
- **Security review:** Not started; required before authentication implementation.
- **Production implementation:** Not started or authorized.
