# GitHub Issue #7 — Browser security control decisions

## Current status

Issue #7 (`MVP-04`) completed its design gates after the human owner approved choices
`1A`, `2A`, `3A` and `4A` on 2026-10-06. ADR-009 records the resulting design
and the approved test design is in this work directory. Independent architecture,
security and test-design reviews passed after their findings were remediated.
Implementation evidence remains owned by Issue #10 and later web slices.

## Decisions requested from the human owner

The human owner approved the coherent restrictive baseline: `1A, 2A, 3A, 4A`.

### 1. CSRF token design

| Choice | Behavior | Trade-off |
| --- | --- | --- |
| **1A — Session-bound synchronizer token (recommended)** | Generate an unpredictable token server-side, bind its digest to the authenticated session, place the raw token in rendered forms (or a response value for same-origin script), and require it in the form body or a dedicated header on every unsafe request. Rotate it whenever the session rotates, including login and privilege change; invalidate it on logout and session expiry. Do not put it in a URL. | Fits the accepted server-side session model and makes binding and revocation explicit. Multiple open tabs continue to work because the token is valid for the session rather than only one request. An XSS can still act as the user, so XSS controls remain necessary. |
| 1B — Signed double-submit cookie | Issue a second readable cookie and require a session-bound, signed value to match a request value. | Useful for stateless servers, which this application is not. It adds cookie/parser rules and is easier to implement incorrectly without reducing server state here. |
| 1C — One-time token per request | Consume each token once and render a replacement. | Strong replay semantics, but back/forward navigation, retries, concurrent tabs, and stale forms need substantial UX and concurrency handling. It is disproportionate for the MVP. |

For **1A**, token comparison should avoid secret-dependent timing. Token failure
returns the stable generic forbidden response and must not reveal whether the
session or token was the failing component.

### 2. Unsafe-request origin and media-type policy

| Choice | Behavior | Trade-off |
| --- | --- | --- |
| **2A — Strict same-origin browser endpoints (recommended)** | For every cookie-authenticated unsafe method (`POST`, `PUT`, `PATCH`, `DELETE`), require a valid CSRF token, require `Sec-Fetch-Site` to be `same-origin` when the header is present, and require an exact configured HTTPS origin from `Origin`; only when `Origin` is absent may an exact-origin `Referer` be used. Reject requests with neither. Accept only the media type explicitly declared by the route: `application/x-www-form-urlencoded` for ordinary forms and `application/json` for JSON endpoints. Multipart is prohibited until a reviewed upload route exists; `text/plain` and content-type guessing are rejected. | Strong defense in depth and unambiguous parsing. Older/unusual clients that omit both origin headers cannot use cookie-authenticated mutation endpoints. Future Android uses bearer-token endpoints and is not forced through browser CSRF semantics. |
| 2B — Token plus origin when available | Require the CSRF token, but check `Origin`/`Referer` only when supplied. | More compatible with unusual clients, but silently loses a useful independent control. There is no current client requirement that needs it. |
| 2C — Origin check without token | Depend on origin metadata and `SameSite` cookies. | Simpler, but browser behavior, same-site sibling origins, and request provenance edge cases make this insufficient for the accepted architecture. Not recommended. |

The application should have no credentialed cross-origin browser API in the
first increment. If CORS is configured at all, the cookie-authenticated routes
must not emit permissive origins, wildcard origins, or cross-origin credential
permission. A future distinct web origin is a new reviewed design decision.

### 3. User-authored markup policy

| Choice | Behavior | Trade-off |
| --- | --- | --- |
| **3A — Plain text only (recommended)** | Names, notes, tags, goals, source metadata, and validation values are text. Use framework auto-escaping in HTML text and attribute contexts; JSON serialization for JSON; and safe DOM text APIs in script. Prohibit raw/template-safe markers, string-built HTML, inline event handlers, and unreviewed HTML sinks. | Smallest stored-XSS surface and meets current product requirements. Formatting can be added later through a reviewed format and sanitizer. |
| 3B — Restricted Markdown | Store source text, render through a pinned parser, sanitize with an explicit allowlist, and test protocols, malformed markup, and sanitizer/parser upgrades. Raw HTML remains disabled. | Adds useful formatting but creates a security-sensitive parser/sanitizer lifecycle that no MVP requirement currently justifies. |
| 3C — Sanitized HTML | Permit an HTML subset after sanitization. | Greatest authoring flexibility and greatest persistent XSS risk. It requires a precise element/attribute/URL policy and renewed security review. Not recommended for the MVP. |

Any later exception to **3A** requires a named use case, contextual-encoding
rules, independent security review, and stored/reflected XSS tests before use.

### 4. CSP strictness and script policy

| Choice | Behavior | Trade-off |
| --- | --- | --- |
| **4A — Nonce-capable strict CSP (recommended)** | Generate a fresh unpredictable nonce per HTML response. Start from `default-src 'none'`; allow scripts only by nonce (with `'strict-dynamic'`), styles from `'self'`, images from `'self'` plus `data:` only if a concrete first-increment asset needs it, fonts/connect/manifest from `'self'`, and no objects or frames. Set `base-uri 'none'`, `frame-ancestors 'none'`, and `form-action 'self'`. Prohibit `'unsafe-inline'`, `'unsafe-eval'`, remote CDN scripts, inline event handlers, and style attributes. | Supports progressive enhancement without weakening policy later for an inline bootstrap. Requires nonce plumbing and CSP-aware templates. Old browsers fall back to the nonce source. |
| 4B — No-script CSP initially | Use `script-src 'none'` until a reviewed feature needs JavaScript; otherwise retain the restrictive directives above. | Strongest initial policy, but may force a policy/architecture change as soon as progressive behavior is implemented. |
| 4C — Self-hosted scripts without nonces | Use `script-src 'self'` and no inline scripts. | Operationally simple, but any same-origin path that can serve attacker-controlled script-compatible content broadens the policy. It is less robust than 4A. |

The final CSP must be emitted as an HTTP response header, not only a meta tag.
Begin rollout in enforcement mode in development and automated tests; a short,
time-boxed report-only production observation may precede enforcement only if
it has an owner, no sensitive report payloads, and a fixed removal date.

## Controls that do not need a product trade-off

Unless the owner identifies a compatibility requirement, the reviewed design
should also require:

- `Content-Type` with the correct charset on HTML and JSON plus
  `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- clickjacking denial through CSP `frame-ancestors 'none'`, with
  `X-Frame-Options: DENY` as legacy defense in depth;
- a `Permissions-Policy` disabling camera, microphone, geolocation, payment,
  USB, and other unused powerful features, with additions reviewed per feature;
- `Cross-Origin-Opener-Policy: same-origin`; do not enable COEP globally until a
  concrete isolation requirement and all subresources are tested;
- production-only `Strict-Transport-Security: max-age=31536000`; initially omit
  `includeSubDomains` and do not request preload until every subdomain is
  inventoried and permanently HTTPS-capable;
- `Cache-Control: no-store` on authenticated HTML and responses containing CSRF
  tokens; static fingerprinted public assets may use long-lived immutable
  caching;
- generic bounded error pages that preserve contextual escaping and never echo
  raw request fragments into HTML; and
- the already accepted host-only, `Secure`, `HttpOnly`, `SameSite=Lax` session
  cookie. These attributes supplement rather than replace the controls above.

## Scope and consequences

- These rules apply to the server-rendered web client and cookie-authenticated
  endpoints. Future Android bearer tokens and Telegram webhooks require their
  own provenance controls and are not made browser endpoints.
- The first increment has no rich text, user HTML, third-party script, framing,
  credentialed cross-origin UI, or upload form requirement. Adding one reopens
  the affected decision and its tests.
- Framework-specific APIs and exact header serialization belong in the final
  architecture and test design after the web framework is selected; the
  security properties above must not depend on a particular framework default.

## Work remaining after design approval

1. Implement ADR-009 only in the applicable feature issues after their other
   architecture, security and test gates pass.
2. Run WEB-01 through WEB-05 against production-equivalent middleware,
   templates, PostgreSQL and a pinned real browser.
3. Obtain independent implementation security and code review before closing
   SEC-06.

Issue #7 authorizes implementation against this design but does not itself
implement browser behavior, close SEC-06 or authorize production deployment.

## Completion evidence for this clarification

- **Changed:** Added an owner-facing choice set, recorded approval of all four
  recommended controls, and linked ADR-009 and the approved test design.
- **Verified:** Reconciled the choices with ADR-007, SEC-06, the approved
  multi-client architecture, and the test strategy; all three independent
  design reviews pass after remediation.
- **Unresolved:** Framework-specific implementation and its test, security and
  code-review evidence in Issue #10 and later web slices.
- **Security review:** Design passed with no risk accepted; SEC-06 remains open
  pending implementation evidence and independent implementation re-review.
- **Files changed:** `docs/work/issue-7/README.md` and
  `docs/work/issue-7/status.yaml`, ADR-009, project review records, and the Issue
  #7 architecture, security and test-design evidence.
