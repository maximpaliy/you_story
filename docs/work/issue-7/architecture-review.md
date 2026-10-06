# Independent architecture review — GitHub Issue #7

- **Latest review date:** 2026-10-06
- **Material:** ADR-009, the Issue #7 decision record and test design, and the
  corresponding amendment to the project architecture
- **Reviewer role:** Independent architecture reviewer
- **Verdict:** Pass after architecture clarification

## Scope and approach

This review checks whether the approved choices `1A`, `2A`, `3A` and `4A` are
represented consistently, preserve the established web/API boundary, account
for the planned Android and Telegram clients, and are precise enough to hand to
implementation. It is not the required independent security review or
test-design review, and it accepts no security risk.

The overall direction is sound: a synchronizer token is appropriate for the
PostgreSQL-backed session model in ADR-007; plain-text rendering avoids an
unnecessary content-processing subsystem; and browser-cookie provenance is
kept separate from future bearer-token and webhook authentication.

## Findings and dispositions

### AR-07-01 — Canonical browser origin and proxy trust boundary (resolved)

The initial draft required an exact configured origin without defining its
authority or relationship to proxy headers. ADR-009 now defines a single
deployment-provided external origin, canonical parsing/comparison rules, the
limited loopback development exception, and explicitly excludes `Host` and
forwarding headers from establishing the expected origin. It assigns those
headers to the separately allowlisted proxy path. This preserves choice `2A`.

### AR-07-02 — Media-type and body parsing contract (resolved)

The initial draft named accepted media types but left parameters, charset and
parsing order unresolved. ADR-009 now defines case-insensitive type/subtype
comparison, the sole optional UTF-8 charset parameter, rejection of ambiguous
header forms, one declared representation and finite body bound per route, and
the order of provenance, size, media, parsing, CSRF and domain-dispatch checks.
Streaming bodies are bounded. WEB-02 therefore has an unambiguous architecture
oracle.

### AR-07-03 — Reproducible CSP and `Permissions-Policy` (resolved)

The initial CSP and browser-feature rules were open-ended policy templates.
ADR-009 now enumerates the complete initial CSP, identifies scripts as the only
nonce-bearing element class, prohibits inline style elements and attributes,
enumerates the initial denied browser features, and makes additions reviewed
changes. Generated response nonces are the policy's only varying value.

### AR-07-04 — Response-policy ownership and applicability (resolved)

The initial draft did not fully allocate headers across response classes.
ADR-009 now assigns policy to outer response middleware and includes an
applicability matrix for HTML, redirects, JSON/API responses and fingerprinted
assets. It covers early errors, authentication redirects and CSRF-bearing
responses, and prohibits cacheability by omission.

### AR-07-05 — CSRF token invariants and delivery boundary (resolved)

The initial draft did not supply a stable token-format minimum or a closed
delivery boundary. ADR-009 now specifies 256 CSPRNG bits, exact unpadded
base64url representation, a session-bound domain-separated SHA-256 digest,
fixed-length comparison, and hidden fields in authenticated server-rendered
HTML as the sole delivery location. It removes the speculative separate token
endpoint. These are implementation invariants within choice `1A`.

## Consistency and client-impact assessment

- **Approved choices:** Pass. ADR-009 accurately records all four owner choices
  and does not silently introduce rich text, uploads, framing, third-party
  scripts or cross-origin credentialed browser access.
- **ADR-007 compatibility:** Pass. Session-bound token rotation and invalidation
  follow session rotation, expiry and logout. The browser controls do not alter
  the accepted identity key, cookie or session-lifetime decisions.
- **Android:** Pass with an explicit future gate. Bearer-token requests do not
  inherit cookie CSRF middleware. Android authentication, redirect, token and
  CORS requirements remain deferred and must be reviewed when scoped.
- **Telegram:** Pass with an explicit future gate. Webhook authenticity and
  replay controls remain distinct from browser origin and CSRF checks.
- **Shared REST API:** Pass. ADR-009 requires middleware to classify the boundary
  from validated authentication scheme rather than path or arbitrary credential
  presence. An ambient session cookie plus another credential cannot bypass
  browser controls.
- **Test handoff:** Pass for architecture. WEB-01 through WEB-05 cover the main
  architecture obligations, and ADR-009 now supplies deterministic policy
  oracles. Independent test-design review remains a separate required gate.

## Verdict

The selected architecture is coherent, accounts for all currently planned
clients and integrations, and does not need renewed human product approval. The
focused re-review finds AR-07-01 through AR-07-05 resolved. **The independent
architecture gate passes with no open architecture finding and no accepted
risk.**

This verdict approves the architecture handoff, not production implementation.
The independent security and test-design reviews remain separate gates, and
their findings may require further architecture review. Production code remains
blocked until all applicable workflow gates pass.
