# ADR-007: Google OIDC with server-side web sessions

- Status: Accepted
- Date: 2026-09-29
- Owners: Architecture / human owner

## Context

The first increment needs Google authentication for a web client. It initially
serves an allowlisted audience, must preserve application-owned identity, and
must not make future providers or clients depend on a Google email address.

## Decision

Use Google OpenID Connect Authorization Code flow with PKCE, exact redirect URI
allowlists, `state`, `nonce`, and issuer/audience/signature/expiry validation.
Request only `openid profile`; do not request, persist or authorize with email.
The external identity key is the verified `(issuer, subject)` pair, mapped to an
application-generated internal user UUID.

First login requires either an allowlisted `(issuer, subject)` or a high-entropy,
short-lived, single-use invitation token delivered out of band. An invitation is
stored server-side only as a one-way digest and, during the validated OIDC
callback, is atomically consumed and bound to `(issuer, subject)` while creating
the internal user, personal tenant and external-identity mapping. Unique
constraints and an idempotent callback prevent concurrent or replayed callbacks
from creating duplicate mappings. Attempts are rate limited. Email equality
never links identities. Additional providers require an explicit authenticated
linking flow and a separately reviewed decision.

The web client receives only an opaque, cryptographically random
`__Host-you_story_session` cookie with `HttpOnly`, `Secure`, `SameSite=Lax`, path
`/`, no `Domain`, and `Max-Age=2592000` (30 days). The persistent browser cookie
may survive a browser restart, but never extends the authoritative server-side
absolute or idle deadline. Store only a one-way digest of its bearer token in
PostgreSQL under the identity module; the raw token exists only in the cookie and
comparisons avoid secret-dependent timing. Request no refresh token, and discard
the authorization code and Google ID/access tokens after the callback establishes
identity.
Sessions rotate after login and future privilege changes, expire after 7 idle
days or 30 absolute days, and are revoked immediately on logout. Multiple
independently revocable browser/device sessions are allowed. State-changing
requests require CSRF protection.

Android and Telegram identity flows remain deferred. The session durations and
allowlist policy are configuration/policy, not database identifiers or public
API contracts.

## Alternatives considered

- Use email as identity or an account-linking key: mutable, privacy-expanding and
  unsafe across issuers.
- Request email only for display: no first-increment requirement justifies the
  additional personal data; it can be added through an additive migration and
  renewed consent later.
- Put OIDC tokens in the browser: enlarges the token-exposure surface without an
  MVP need.
- Add Redis for sessions: unnecessary infrastructure while PostgreSQL already
  provides durable, revocable session state.
- Permit public self-registration: expands abuse and operating scope before the
  initial deployment needs it.

## Consequences and reversibility

Email may be added later as nullable presentation/contact data with an additive
migration, updated consent, lifecycle rules and no change to identity keys.
Session timeouts, concurrent-session policy and allowlist/open-registration
policy can change without schema or API changes. Changing the cookie name or
storage backend can invalidate active sessions but does not change user identity.
Any replacement session representation must continue to store no bearer-
equivalent raw token. New providers add external-identity rows and an approved
linking flow.

The durable constraints are that internal user IDs remain application-owned,
external identities remain keyed by issuer plus subject, and authorization never
uses mutable profile claims. Changing those invariants would require identity
migration, collision/account-takeover analysis and independent review.

## Security / privacy impact

Data minimization resolves the architectural email-scope decision in SEC-12.
The implementation must still resolve SEC-05 and SEC-06, including exact cookie
and CSRF mechanics, safe redirect/error behavior, session fixation/replay tests,
security headers and XSS tests. SEC-01 and SEC-07 remain mandatory for tenant
context and application authorization.

## Human approval

Approved by the human owner on 2026-09-29.

The human owner approved the Issue #6 cookie name, path, host-only scope and
30-day persistence clarification on 2026-10-03.
