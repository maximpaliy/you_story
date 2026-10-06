# Issue #7 browser-security test design

- **Status:** Approved after independent review on 2026-10-06
- **Design under test:** ADR-009
- **Security finding:** SEC-06
- **Implementation owners:** Issue #10 and later web slices after all gates pass

## Test oracle

HTTP tests run the production middleware/template configuration. Browser tests
run a pinned, project-supported browser against the real application and
PostgreSQL. Browser controls are necessary, never sufficient authorization:
failure of session, provenance, media type or CSRF validation must stop at the
outer browser-policy/application-dispatch boundary with no downstream command or
repository call and no durable state change. Passing all four merely permits
normal validation, authorization, tenancy, concurrency and domain rules to run.
Every rejection has the same documented bounded response class and exposes no
token or submitted value in body, redirect, logs, traces, screenshots or
retained HTTP artifacts.

## Required cases

### WEB-01 — CSRF lifecycle and parsing

- Inspect configuration/source to prove ADR-009's 32-byte OS-CSPRNG, exact
  base64url encoding, bounded format and domain-separated digest construction;
  prove digest-only session persistence and
  secret-independent comparison; raw tokens appear only in approved response
  locations and never URLs or telemetry.
- Cover correct, missing, empty, malformed, expired, foreign-session, old-after-
  rotation and post-logout tokens for every unsafe method and both form/header
  transports.
- Cover duplicate fields/headers, field plus header, comma-folded headers and
  conflicting encodings; ambiguous input fails closed.
- Prove concurrent tabs, repeated reads and legitimate retry retain the
  session-bound token, while login and privilege/session rotation replace it.
- Positive controls remove the token check and binding independently and must
  make the suite fail.

### WEB-02 — Request provenance and content type

- Cross-product exact good/bad/missing/duplicate `Origin`, fallback `Referer`,
  `Sec-Fetch-Site`, safe/unsafe method and valid/invalid token. Test scheme,
  host, port, user-info, suffix/prefix, case and encoded-confusion variants.
- `Referer` is consulted only when `Origin` is absent; both absent fail. Present
  non-`same-origin` Fetch Metadata fails even with valid token and origin.
- Each route accepts only its declared normalized media type and charset rules.
  Reject missing, duplicated, malformed, `text/plain`, guessed JSON/form and
  multipart types before domain mutation.
- Assert cookie routes emit neither wildcard/permissive CORS origins nor
  cross-origin credential permission. Cross-site form, fetch and iframe browser
  journeys cannot mutate state.
- Derive expectations from ADR-009's parsed `(scheme, ASCII host, effective
  port)` tuple: scheme/host case and omitted default ports normalize equal;
  configured non-default ports must match; trailing-dot, Unicode/non-A-label or
  percent-encoded hosts, credentials, opaque/multiple/malformed values fail.
  Apply identical origin extraction expectations to `Referer` while ignoring
  its path/query/fragment. Assert the expected origin comes only from trusted
  configuration, never request host or forwarding headers.

### WEB-03 — Contextual encoding and stored/reflected XSS

Inject unique canaries and a maintained payload corpus into names, notes, tags,
goals, source metadata, query/filter values and validation errors. Exercise HTML
text and attribute contexts, JSON embedded or fetched by script, DOM updates,
redirect/error pages and every create/edit/list/detail/history rendering path.
Assert the intended text round-trips while no script executes, DOM element or
attribute is created, navigation occurs, network canary fires or CSP violation
reveals sensitive data. Include broken markup, entity/double encoding, quote and
backtick variants, URL schemes, SVG/MathML, closing script/style sequences and
Unicode normalization/bidirectional cases.

Static checks reject raw/safe template markers, unreviewed HTML sinks,
`innerHTML`/equivalents, string-built markup, inline event handlers/style
attributes, `eval`-class APIs, raw HTML/Markdown renderers and templates with
auto-escaping disabled. A checked exception manifest is empty for the MVP; each
introduced forbidden sink mutation must fail CI.

### WEB-04 — CSP and security headers

- Parse the effective enforced CSP rather than substring matching. Assert every
  HTML response and success/error/redirect class receives the applicable header
  set exactly once without conflicting duplicates.
- Inspect configuration/source for ADR-009's 32-byte OS-CSPRNG and exact encoding.
  Response tests prove header/approved-script propagation and no leakage, and a
  bounded deterministic sample contains no repeated nonce (regression evidence,
  not proof of unpredictability). Browser probes prove scripts with missing,
  mismatched or guessed attacker-controlled nonces do not execute; browsers are
  not expected to detect nonce reuse.
- Real-browser probes attempt inline/remote/same-origin unnonced script, event
  handlers, `eval`, style attributes, objects, framing, base replacement and
  off-origin form submission. All are blocked; the intentionally nonced
  progressive script and approved self-hosted resources work.
- Assert `nosniff`, no-referrer behavior, framing denial, disabled powerful
  features and opener isolation. Validate authenticated/CSRF responses are
  `no-store` and fingerprinted public assets alone may be immutable.
- In production-mode configuration assert one-year HSTS without subdomains or
  preload; in local non-TLS mode assert the documented omission. COEP remains
  absent unless a later decision changes it.

### WEB-05 — Coverage, leakage and regression controls

Mechanically inventory all cookie-authenticated mutation routes, HTML templates,
HTML/error response constructors and script/style/resource declarations. Reconcile
each with CSRF/provenance/media-type cases, contextual-encoding cases and header
assertions. An unclassified route/template/sink fails CI. Scan enabled log,
trace, CSP-report and retained-test-artifact sinks using unique sentinels for raw
session/CSRF values and submitted private content; positive controls prove every
scanner observes its sink. Leakage collection records application revision,
bounded inspected interval, sink/query, ingestion-lag allowance and timeout.
Use synthetic canaries, never actual credentials. A missing benign sentinel,
timeout, uninspected enabled sink or failed collection is inconclusive and fails
the check. Scan or redact raw artifacts from both successful and failed tests
before retention.

## Execution profile

The repository records and pins the browser engine/version, browser runner,
PostgreSQL version, generator seed and payload-corpus version with retained test
evidence. Generate canonical equivalence/boundary cases for every unsafe method
and its one token transport. Use full combinations for token validity × origin
fallback × Fetch Metadata × media type; pairwise generation is permitted only
for documented non-interacting parser variants. Browser-security failures are
never automatically retried to green; infrastructure retries remain separately
reported and preserve the first failure.

## Traceability

| Requirement | Cases / level | Positive control or mutation | Implementation owner |
| --- | --- | --- | --- |
| Session-bound CSRF format, digest, lifecycle and one transport | WEB-01; static, HTTP, browser | Remove binding/check; duplicate transport | #10 and each later mutation route |
| Canonical origin, Fetch Metadata, CORS and authentication boundary | WEB-02; configuration, HTTP, browser | Trust request host; omit provenance check | #10 and each later mutation route |
| Exact route media type, body bound and pre-dispatch failure | WEB-02; static, HTTP | Broaden parser; dispatch before check | Owning web slice |
| Plain text, contextual escaping and prohibited sinks | WEB-03, WEB-05; static, HTTP, browser | Add each forbidden sink/disabled escaping | Owning rendering slice |
| Exact CSP, nonce and resource behavior | WEB-04; configuration, HTTP, browser | Missing/mismatched/guessed nonce; weakened directive | #10 and each later HTML slice |
| Header matrix, cache policy and HSTS profile | WEB-04; configuration, HTTP, browser | Omit header on each response class | #10/platform integration |
| Complete route/template/sink inventory and leakage | WEB-05; static, HTTP, sink polling | Add unclassified surface; benign sentinels | Every web slice |
| SEC-06 escaping, unsafe-HTML prohibition, CSP/headers, origins/content types, CSRF binding/rotation, stored/reflected negatives | WEB-01–WEB-05 at the levels above | Independent mutations above | #10–#15 |
| Deferred COEP, HSTS subdomains/preload, rich text, upload, framing, third-party script and credentialed cross-origin UI remain absent | WEB-02–WEB-05; configuration/static/inventory | Add each forbidden capability | Future issue must reopen design |

## Gate

Implementation may start only after independent architecture, security and
test-design reviews accept ADR-009 and this design. Passing tests later supplies
implementation evidence; it does not by itself close SEC-06 or prove absence of
XSS/CSRF.
