# Independent security review — GitHub Issue #7

- **Review date:** 2026-10-06
- **Material:** ADR-009, the Issue #7 decision brief, the reconciled project
  architecture, SEC-06, and the proposed Issue #7 test design
- **Verdict:** Pass after focused re-review; implementation evidence remains
  required
- **Scope:** SEC-06 design portion only
- **Risk acceptance:** None

## Threat assessment

The reviewed boundary has four independent layers rather than treating any one
browser mechanism as sufficient: a session-bound synchronizer token, strict
same-origin provenance and media-type checks, contextual output handling, and an
enforced restrictive CSP. This is appropriate for the accepted server-side
session architecture. Keeping future Android bearer-token and Telegram webhook
authentication outside the cookie boundary avoids imposing browser headers on
non-browser clients without weakening browser routes.

The principal residual threat is stored or reflected script execution. A valid
same-origin script can act with the user's ambient session even though it cannot
read an `HttpOnly` cookie, so CSP is defense in depth rather than a substitute
for safe rendering. The plain-text-only rule, prohibited sink list, template and
route inventory, browser probes, and mutation-sensitive checks address that
risk at the right layers. The CSRF design likewise does not rely on `SameSite`
alone and fails closed when provenance is unavailable.

## Findings and dispositions

1. **CSRF lifecycle and ambiguity — resolved at design.** The token is
   unpredictable, session-bound by a stored digest, rotated with the session,
   invalidated on logout/expiry, excluded from URLs and telemetry, and accepted
   through exactly one transport. Duplicate or conflicting representations have
   a generic failure. Implementation evidence must show that form routes accept
   the form field and JSON routes accept the dedicated header; a request must
   not gain two parsing paths merely because both transports exist globally.

2. **Safe-method and authentication-boundary bypass — implementation
   condition.** `GET`, `HEAD` and `OPTIONS` must have no application mutation,
   and logout or another state transition must use an unsafe protected request.
   Every route that accepts the browser session cookie must be in the cookie
   route inventory even if it can also accept another credential; presenting a
   bearer token must not let a request with ambient cookies bypass the browser
   controls. These are required review checks, not accepted exceptions.

3. **Origin canonicalization and proxy trust — implementation condition.** The
   exact expected HTTPS origin must come from trusted deployment configuration,
   not an untrusted `Host`, `Forwarded` or `X-Forwarded-*` value. Parsing must
   reject duplicate, malformed, user-info, encoded-confusion and non-canonical
   values before comparison. The proposed provenance matrix is sufficient to
   produce evidence when it runs against production middleware.

4. **Active content contexts — implementation condition.** Contextual escaping
   is sufficient for text and inert attribute values but is not a URL-scheme
   policy. User-authored/source metadata must not be placed into executable,
   navigation, stylesheet or other active URL contexts. If a product slice
   needs a user-controlled destination, it must first define an allowed scheme,
   destination and navigation policy and extend the security tests. No such
   exception is approved by ADR-009.

5. **CSP and header precision — resolved at design.** The nonce is fresh per
   HTML response and authorizes only intended script elements; `strict-dynamic`
   does not authorize inline handlers, `eval`, unnonced same-origin scripts or
   unsafe style attributes. Header behavior applies to error responses as well
   as successful pages. `Permissions-Policy` must be generated from an explicit
   checked feature allowlist (empty for unused powerful features), rather than
   relying on changing browser defaults. HSTS is production-only and deliberately
   excludes subdomains and preload pending domain review; COEP is deliberately
   deferred. These deferrals do not weaken the accepted first-increment threat
   boundary.

6. **Leakage and observability — implementation condition.** Raw session and
   CSRF values, submitted private content, and sensitive CSP reports must remain
   absent from logs, traces, URLs, screenshots and retained test artifacts.
   Generic rejection behavior must not disclose whether session, provenance,
   media type or token validation failed. Positive controls for each scanner are
   necessary so an empty sink cannot create false confidence.

7. **Test design adequacy — adequate for security implementation evidence.**
   WEB-01 through WEB-05 cover token lifecycle and parser ambiguity, provenance
   and content types, stored/reflected XSS contexts, effective CSP and headers,
   cache behavior, complete surface inventory and leakage. Real-browser checks
   complement HTTP-level middleware tests, while mutation tests demonstrate
   that independent controls are actually observed. This assessment does not
   replace the required independent test-design review.

## Gate disposition

No blocking security-design gap remains for Issue #7, and the design is ready
to proceed to implementation evidence after the independent architecture and
test-design gates also pass. This review accepts no residual risk and approves
no report-only deployment exception, rich text, active user-controlled URL,
cross-origin credentialed API, upload form, third-party script or framing.

SEC-06 remains **open — implementation evidence blocker**. Closure requires the
production middleware and templates to implement ADR-009, all applicable
WEB-01 through WEB-05 checks to pass against that configuration, route/template/
sink inventories to reconcile without omissions, and an independent security
and code re-review of the implementation. A framework change or addition of
any excluded capability reopens the relevant design and test review.

## Focused re-review after architecture-review remediation

The 2026-10-06 remediation was reviewed against the threat assessment and all
seven dispositions above. It closes the architecture review's implementation
ambiguities without weakening the owner-approved controls:

- The canonical external origin is now a deployment value with explicit syntax,
  normalization and rejection rules. Request host and forwarding headers cannot
  establish it, and the separately allowlisted proxy path is not confused with
  request provenance. WEB-02 now tests the same parsed origin tuple and trusted-
  configuration boundary. Finding 3 is therefore deterministic rather than
  framework-dependent.
- Each route now has one representation, a finite streaming body bound, a narrow
  UTF-8 parameter rule and fail-closed duplicate/header behavior. Authentication
  boundary, provenance, body bound and media type precede parsing; CSRF precedes
  domain dispatch. Safe methods, protected logout and authentication-scheme
  classification are explicit. This resolves the bypass concerns in Findings 1
  and 2. “Both transports” in WEB-01 means coverage of form routes and header-
  using routes, not acceptance of both on one route; the execution profile and
  traceability table preserve that one-transport oracle.
- Token entropy, encoding, length, domain-separated session binding, response
  location and digest comparison are reproducible. The digest is not used as a
  substitute for token entropy, and only the digest persists. No token-fetch
  endpoint was introduced, avoiding an extra disclosure and cache surface.
- The exact CSP shape, nonce format and recipients, inline-style prohibition,
  resource denials and explicit `Permissions-Policy` list now admit direct
  parsing and mutation tests. The response matrix gives one outer middleware
  ownership of HTML, redirects, JSON/errors, static assets, authentication
  responses, cache policy and early failures. These changes close the precision
  concerns in Finding 5 while retaining CSP as defense in depth.
- WEB-05 now treats telemetry collection failures as inconclusive failures,
  records the inspected revision/window/sinks and ingestion allowance, requires
  benign positive sentinels, and sanitizes retained artifacts. This strengthens
  Finding 6's evidence against false passes. Pinned execution versions, seeds
  and payload corpus plus non-retried security failures make the evidence
  reproducible.

No new security-design gap was introduced. The earlier active-context condition
still applies: plain-text source metadata is rendered as text, not as a user-
controlled navigation or executable URL. Introducing such a destination needs
an explicit scheme/destination/navigation policy and renewed tests and review.
Likewise, production report-only CSP remains unavailable unless its separately
stated owner, nonsensitive-report and fixed-removal-date conditions are met;
this review grants no exception.

**Final disposition:** ADR-009 and the remediated test design are ready for
implementation evidence. No residual risk is accepted, and SEC-06 remains open
until production implementation passes the specified evidence and independent
security/code re-review gates.
