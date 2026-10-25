# Issue #10 independent implementation code review

Reviewer: independent agent `test_design`; authored the catalog provisioning
adapter/tests and browser journey tests, which are **excluded** from this review.
Scope reviewed: `identity/infrastructure/google.py`, its provider tests,
`identity/application/service.py`, typed persistence/public evidence flow, and
`app.py` composition. Other authors' review of the excluded code and the
database/browser-security implementation remains necessary.

Status: **PASS — provider, core and root-composition code review approved after
remediation and final cumulative verification**. ICR10-01–06 are resolved.
The owner approved ADR-012 before
activation; its exact production policy has passing real-browser and PostgreSQL
evidence. This approval covers only the independently reviewed scope above.
This is a review of the current implementation,
not a claim that every designed AUTH6/WEB case has executed.

## Findings

| ID | Finding / required action | Status |
| --- | --- | --- |
| ICR10-01 | Initial delivery tests injected `FakeIdentity`, while foundation tests called SQL wrappers directly. Real public-port cases now cover provider/AEAD/challenge/denial failures, consumed state, active-session fixation, unavailable storage, forged/stale evidence and cross-session CSRF. PostgreSQL variants assert committed no-authority/invitation-consumption and call-count oracles. | Resolved; unit and all eight real-PostgreSQL cases passed |
| ICR10-02 | CSRF validation initially swallowed DB 503 and returned false, producing 403. It now propagates unavailable failures; the outage regression asserts 503 and unchanged stored sessions. Invalid/stale evidence still denies. | Resolved; regression passed |
| ICR10-03 | Initial stalled-body test covered one request only. Added delayed token and JWKS stages of six seconds each; the outer ten-second exchange deadline cancels their combined processing. | Resolved; combined-budget regression passed |
| ICR10-04 | Secondary audience values initially admitted whitespace/control/non-ASCII strings. Every audience is now a bounded visible ASCII client ID; signed negatives cover those values and the valid multiple-audience+azp positive remains. | Resolved; signed-token regressions passed |
| ICR10-05 | The initial native form sends opaque Origin under no-referrer and the self-only CSP blocks the Google redirect. ADR-012 repairs only successful GET form-document Referrer-Policy and the login-only fixed Google form-action source, preserving opaque-origin rejection. Independent reviews and explicit owner approval were obtained before activation. | Resolved; seven native HTTPS/real-DB browser cases passed with production headers |
| ICR10-06 | Evidence review found missing full AUTH6-11 composition journeys. Real native HTTPS cases now inject failure before pair ensure and after pair commit/before ready mark; prove pending profile/home/logout, no normal-request retry, and fresh-login convergence. The happy path seeds actual unselected preference/control XSS canaries and signed provider name/picture probes. | Resolved; all nine browser cases and final 582-case canonical run passed; separate independent evidence review passed |

No account-takeover or authority-bypass defect was identified in the reviewed
provider signature/claim path. Findings remain material to completion until
their dispositions and actual final results are recorded.

## Reviewed controls

The provider uses fixed Google HTTPS endpoints, `verify=True`, no redirects,
five-second connect limits, bounded streamed bytes and one ten-second exchange
deadline including JWKS. Provider errors become one safe failure string without
raw response/credential text, and ambiguous exchanges are not retried. PyJWT
performs maintained-library RS256 verification; the adapter separately enforces
the reviewed OIDC claim policy. It is not a generic discovery/OIDC client.

Raw JWT header/payload and response JSON parsing rejects duplicate keys and
nonfinite literals. The adapter rejects unsigned/symmetric algorithms,
untrusted signing URL headers, critical/b64 extensions, weak/non-signing/private
JWKs, duplicate kids and unrecognized keys. Issuer normalization, strict integer
NumericDates excluding booleans, precise leeway, aud/azp, bounded ASCII subject
and fixed-length nonce-digest comparison are present. Display names, email and
provider URLs do not enter profile results.

The JWKS cache uses a monotonic clock, caps TTL at one hour or a shorter valid
provider max-age after Age, refreshes unknown kid once per exchange and clears
cached authority before a failed refresh. Concurrent callers may cause duplicate
bounded refreshes or fail closed during replacement; no stale-acceptance path
was found. Do not describe this as a cross-replica distributed cache.

The identity service commits claim before provider exchange, checks AEAD-bound
verifier and PKCE challenge before the token request, and delegates finish to one
typed atomic wrapper. It requires a canonical issuer/bounded subject result,
fresh server-generated session UUID/bearer, and verifies persistence returned
the exact session UUID before issuing public session evidence. Failed callback
terminalization cannot reopen an already committed claim. Direct logout/ready
calls re-resolve registered session evidence and compare actor/session linkage.

The app composes only public module boundaries, validates auth deployment
configuration for normal serving, and gives metadata-only test composition an
unavailable auth implementation. Login completion alone invokes the separate
catalog transaction and conditional mark-ready; failure preserves the committed
identity/session and pending state. Home/profile requests cannot invoke that
hook. Outer correlation/response policy also applies to framework and unexpected
errors, and callback errors use a generic HTML failure page. No raw exception is
logged by these composition handlers.

## Evidence limits and final disposition

The provider tests include real RSA signatures and maintained-library JWK
verification with valid controls; adverse claims, algorithm/signature errors,
duplicate/nonfinite JSON, byte bounds, key constraints, cache expiry, unknown-kid
refresh and no-retry/no-detail failures are substantive. MockTransport substitutes
external networking; it does not establish live Google/TLS/proxy behavior.
Full real-runtime/public-port negative coverage and final canonical checks remain
the lead's evidence gate. This review does not approve production deployment or
close SEC-01/05/06/07 merely because its inspected paths appear sound.

Focused reviewer run: `pytest tests/test_google_oidc.py -q` completed **80 passed**
in 10.39 seconds, including the real ten-second stalled-stream cancellation.
This was a unit/provider run without PostgreSQL. Separately, the real HTTPS/DB
browser baseline failed at the start-response oracle: **403**, opaque Origin,
valid binder-cookie name present, and **zero provider exchanges**. Only safe
status/header categories were retained; no proof/bearer/callback query was logged.

After remediation, the reviewer ran
`pytest tests/test_identity_use_cases.py tests/test_google_oidc.py -m 'not postgres' -q`:
**108 passed, 8 deselected in 20.64 seconds**. The eight real-DB cases were
explicitly outside this focused run, not hidden skips or claimed passes. The
lead subsequently ran them serially, as recorded below. Both ten-second provider
deadline regressions and CSRF-503/audience hardening passed. See
[browser compatibility evidence](browser-compatibility-evidence.md) for the
separate unchanged-baseline failures and response-only repair diagnostics.

Final focused integration evidence reported by the lead:
`pytest tests/test_identity_use_cases.py tests/test_runtime_postgres.py tests/browser/test_auth_journeys.py`
completed **52 passed in 9.68 seconds**. This includes all eight actual
identity-core PostgreSQL cases and all seven native HTTPS browser cases. The
browser tests use the approved production response matrix without header
substitution and intercept the actual Google request via CDP; signed synthetic
token/JWKS responses still exercise the real verifier and persistence adapter.
Off-provider, wrong Google path and Google-form-on-profile probes are blocked by
actual browser policy. The preserved original failures are resolved, not hidden.

The lead completed canonical `make check` with **exit 0: 580 passed, 0 failed,
0 skipped in 72.91 seconds**, including all seven real-browser cases and all
eight core PostgreSQL cases. Ruff lint/format, strict mypy (48 production source
files), source/SQL/composition gates, generated OpenAPI, wheel build and installed
artifact composition checks passed. Evidence was inspected in
`work/issue10-check.log`; JUnit is `work/test-results.xml`. One reported Starlette
TestClient/httpx deprecation warning is retained; it is not hidden or described
as a zero-warning run. The uv build also reports the local cache-directory
placement warning; the explicit wheel-content/artifact gate passed.

This final approval excludes the reviewer's own catalog/browser implementation
and requires the separate independent review of those files. It does not
authorize deployment or waive broader SEC/production gates. New material changes
after this reviewed state require focused re-review.

Follow-up evidence review identified ICR10-06 after the historical 580-case run.
The added test code remains outside this reviewer's independent scope (authored
by this agent); the lead confirmed separate independent security/evidence review
passed for those tests and the excluded catalog/browser implementation.

The earlier 582-case run passed in 75.37 seconds. After 56 additional actor-issuer
static-guard mutations were independently reviewed, the **final authoritative
canonical run** completed with **exit 0: 638 passed, 0 errors, 0 failed,
0 skipped in 76.196 seconds**, including all nine native TLS/browser
cases. Current evidence is `work/issue10-check.log` and `work/test-results.xml`;
the reviewer inspected the final log, including both new browser passes and
all canonical gates. One Starlette TestClient/httpx deprecation warning remains
recorded, as does the local uv cache-placement build warning; artifact composition
passed. No further code changes or database runs are needed for this scope.

The frozen-state run also passed Ruff lint and formatting (153 files), strict
mypy (48 production source files), source/SQL/composition, generated OpenAPI,
wheel and artifact gates. The issuer-guard additions received separate independent
focused review with 112 passing cases; they do not change the reviewed feature
implementation or remove the catalog/browser self-review exclusion.

Both new composition cases retain active identity/session and the consumed
invitation while provisioning is pending, prove no retry on ordinary home/profile
requests, allow protected native logout, then use a fresh login to converge to
one catalog/grant and ready state without another account or invitation use.
The added stored probes prove the unselected canaries never reach profile JSON,
HTML text or DOM/image/execution sinks; they do not claim a stored text-rendering
round-trip feature exists. All ICR10 findings are resolved and scoped code review
is **PASS**. Deployment and broader production/security gates remain separate.
