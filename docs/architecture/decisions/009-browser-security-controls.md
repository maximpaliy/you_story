# ADR-009: Strict browser request and rendering controls

- Status: Accepted
- Date: 2026-10-06
- Owners: Architecture / security / human owner

## Context

The server-rendered web client uses an opaque session cookie. `SameSite` and
`HttpOnly` reduce exposure but do not prevent CSRF or same-origin actions by
injected script. User-authored names, notes, tags, goals and source metadata can
become stored-XSS inputs. The first increment does not require rich text,
third-party scripts, framing, cross-origin credentialed browser access or file
upload forms. Future Android bearer-token and Telegram webhook clients must not
be forced through browser-only controls.

## Decision

Use a session-bound synchronizer CSRF token. Generate 32 bytes (256 bits) with
the operating-system CSPRNG and encode as unpadded base64url (exactly 43 ASCII
characters). Store with the authenticated session only a SHA-256 digest of the
UTF-8 domain separator `you-story:csrf:v1`, a zero byte, the internal session
row UUID bytes, a zero byte and the raw token. Compare fixed-length digests
without secret-dependent timing. Expose the raw token only in a hidden field in
authenticated server-rendered HTML, never a URL or a separate token endpoint.
Require it in exactly one form
field or dedicated header on every cookie-authenticated `POST`, `PUT`, `PATCH`
and `DELETE`. Reject missing, duplicate, malformed, mismatched and expired
values with the same bounded forbidden response. Rotate it with every session
rotation, including login and privilege change, and invalidate it with logout or
session expiry. A session token remains valid across tabs and retries.

For those unsafe requests, require the deployment-provided canonical external
web origin. Production configuration contains exactly one absolute HTTPS origin:
scheme, ASCII IDNA A-label host and optional non-default port, with no path,
query, fragment, credentials or trailing dot. Development/test may explicitly
configure an HTTP loopback origin and non-default port; no other HTTP origin is
valid. Parse request provenance as origins: scheme and ASCII host comparison is
case-insensitive and an omitted default port equals its scheme's default port;
the resulting tuple must equal configuration. Reject multiple/opaque/malformed
values, credentials, trailing-dot or percent-encoded hosts and noncanonical IDN
input. The expected origin never derives from `Host`, `Forwarded` or
`X-Forwarded-*`; those headers are separately constrained by the deployment's
allowlisted Cloud Run/proxy path. Only when
`Origin` is absent may an exact-origin HTTPS `Referer` satisfy provenance; reject
when both are absent. Apply the same parser to the origin portion of `Referer`
and ignore its path/query/fragment. When `Sec-Fetch-Site` is present, require
`same-origin`.

Each route declares exactly one representation and a finite pre-parser body-size
limit. Accept `application/x-www-form-urlencoded` for ordinary forms or
`application/json` for JSON, comparing type/subtype case-insensitively. Permit no
parameter or a single case-insensitive `charset=UTF-8`; reject all other,
duplicate or conflicting parameters and multiple or comma-folded `Content-Type`
fields. Validate method, authentication boundary, provenance, declared content
length/stream limit and media type before parsing, then validate CSRF input before
domain dispatch. Oversize or chunked bodies are bounded while streaming and
cannot reach application commands or repositories. Reject `text/plain`,
content-type guessing and multipart until a reviewed upload route exists. There is no
credentialed cross-origin browser API; cookie routes emit no permissive CORS or
cross-origin credential permission. Bearer-token and webhook clients receive
separately reviewed provenance controls. Middleware classifies the boundary from
validated authentication scheme, not paths or arbitrary credential presence; an
ambient session cookie cannot bypass browser controls by adding another
credential. `GET`, `HEAD` and `OPTIONS` never perform application mutation, and
logout is an unsafe protected request.

All first-increment user-authored values are plain text. Use contextual template
auto-escaping, JSON serialization and safe DOM text APIs. Raw/template-safe
markers, string-built HTML, inline event handlers, unreviewed HTML sinks and raw
HTML are prohibited. Markdown or sanitized HTML requires a new named use case,
format and sanitizer policy, tests and independent security review.

Every HTML response carries a fresh 32-byte CSPRNG, unpadded-base64url CSP nonce.
The enforced policy shape is `default-src 'none'; script-src
'nonce-{NONCE}' 'strict-dynamic'; style-src 'self'; img-src 'self'; font-src
'self'; connect-src 'self'; manifest-src 'self'; object-src 'none'; base-uri
'none'; frame-ancestors 'none'; form-action 'self'; frame-src 'none'; media-src
'none'; worker-src 'none'`. Only approved `<script nonce="{NONCE}">` elements
receive it. Inline `<style>` elements and style attributes are prohibited and do
not receive a nonce. Remote CDN scripts, inline handlers, `'unsafe-inline'`,
`'unsafe-eval'` and `data:` resources are prohibited. Adding any source or
element class requires architecture/security/test review; generated nonces are
the only varying policy value.
A time-boxed report-only production observation may precede enforcement only
with an owner, nonsensitive reports and fixed removal date; development and
automated tests enforce immediately.

Responses also set correct content types/charsets, `X-Content-Type-Options:
nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, a
`Permissions-Policy: accelerometer=(), autoplay=(), camera=(), display-capture=(),
encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(),
microphone=(), midi=(), payment=(), picture-in-picture=(),
publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), web-share=(),
xr-spatial-tracking=()`, and
`Cross-Origin-Opener-Policy: same-origin`. Authenticated HTML and responses
containing CSRF tokens use `Cache-Control: no-store`; fingerprinted public assets
may be immutable. Production sets `Strict-Transport-Security:
max-age=31536000`, initially without `includeSubDomains` or preload. COEP,
subdomain HSTS and preload require later compatibility and domain review. Error
responses are bounded, contextually escaped and do not echo raw request
fragments. Adding a browser feature requires the same reviewed change mechanism
as a CSP source.

One outer response-policy middleware owns the following applicability contract:

| Response class | CSP/nonce | `nosniff`, referrer, frame, permissions, COOP | `no-store` | HSTS in production |
| --- | --- | --- | --- | --- |
| HTML success or error, anonymous or authenticated | Yes | Yes | Yes when authenticated or containing a CSRF value; otherwise explicit route cache policy | Yes |
| Redirect, including login/OIDC/logout | No | Yes | Yes | Yes |
| JSON/API success or error | No | Yes | Yes when authenticated or containing private/token data; otherwise explicit route cache policy | Yes |
| Fingerprinted public static asset | No | `nosniff` and referrer; frame/permissions/COOP not required | No; may be immutable | Yes |

Early middleware/framework errors must pass through this outer policy. No
response is cacheable by omission: routes not forced to `no-store` declare an
explicit reviewed cache policy.

## Alternatives considered

- Signed double-submit cookie: unnecessary complexity for a stateful server.
- One-time per-request tokens: disproportionate navigation, concurrency and
  retry cost.
- Origin checks without a token, or optional provenance: weaker independent
  defenses without a present compatibility requirement.
- Markdown or sanitized HTML: unneeded parser/sanitizer lifecycle and stored-XSS
  surface.
- `script-src 'none'`: strongest but likely forces redesign for progressive
  enhancement.
- `script-src 'self'`: simpler but broadens trust to every same-origin
  script-compatible response.

## Consequences

Framework adapters must implement nonce propagation, contextual rendering,
precise media-type parsing, provenance validation and stable failures rather
than relying on framework defaults. Unusual cookie clients that send neither
origin header cannot mutate state. The policy deliberately requires review when
rich content, upload forms, remote resources, framing, a distinct web origin or
new browser capabilities are introduced.

## Security / privacy impact

The controls provide independent request-provenance, token, encoding and browser
policy layers. They do not claim to make XSS harmless: injected same-origin code
can act for the user, so source/sink review and adversarial tests remain gates.
CSRF values, session values and CSP report payloads are secrets or potentially
sensitive telemetry and must not be logged or retained in test artifacts.

## Human approval

The human owner approved choices `1A`, `2A`, `3A` and `4A` on 2026-10-06. This
approves the design direction, not implementation or any residual risk.
