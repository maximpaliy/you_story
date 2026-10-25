# Browser policy compatibility evidence — Issue #10

Status: **original production-baseline failures preserved; ADR-012 approved and
activated; nine final production-policy browser tests passed**. Diagnostic
substitutions below demonstrated the repair before independent review and the
explicit owner decision. Production controls were unchanged during those
diagnostic runs; later approved activation is recorded at the end.

Environment: real Chromium **151.0.7922.173** selected explicitly with
`TEST_CHROMIUM_PATH=/usr/bin/chromium`; Playwright **1.56.0**; real Uvicorn HTTPS
on loopback with a generated synthetic certificate, access logging disabled and
`proxy_headers=False`; real PostgreSQL 17.6 marked disposable fixture with
separate runtime/owner/inspection credentials. TLS certificate bypass is scoped
to this generated browser fixture. No live Google network/credential was used.
Normal tests default to the Playwright-pinned bundled engine; system Chromium is
an explicit local override, not silently substituted CI evidence.

## Unchanged production baseline

The root's original browser run had **1 pass and 3 failures**. A focused rerun
with an early start-status oracle produced **1 failure** before any provider
exchange: native `POST /auth/google/start` returned **403**, request Origin was
the opaque literal `null`, Referer was absent, and the signed login-cookie name
was present. The strict gate correctly rejected opaque provenance.

The effective `Referrer-Policy: no-referrer` on the form document suppresses
usable native-form provenance in this Chromium behavior. The binder/proof did
not authorize bypassing the independent origin rule. No raw cookie, proof,
request body or callback query was retained.

## Response-only diagnostic comparisons

The scratch harness is `work/test_browser_compatibility_diagnostic.py`; it is
outside the production package and normal configured test inventory. It changes
only browser-observed response headers, never production source or origin gates.

| Diagnostic | Substitution | Observed result |
| --- | --- | --- |
| Referrer alone | `same-origin` on form-rendering responses; original `form-action 'self'` retained | Native start **303**, then browser reports `effectiveDirective=form-action`; **zero provider exchanges**. Confirms a second independent CSP conflict with Google redirect. |
| Google source compatibility | Same referrer change; add fixed `https://accounts.google.com/o/oauth2/v2/auth` only to login-document form-action | Native start **303**, browser attempts the actual Google host request, **no policy violations**, zero backend exchange because this comparison intentionally does not serve the provider. |
| Full synthetic-provider journey | Same narrow response headers; CDP serves the actual external Google authorize request with a synthetic callback redirect | Native form -> original start **303** -> actual fixed Google request -> callback -> home/profile **200** -> native protected logout -> profile **401**; one real signed-token exchange, no CSP violations. |

Final diagnostic command (synthetic fixture variables supplied separately):

```sh
TEST_CHROMIUM_PATH=/usr/bin/chromium uv run --frozen pytest \
  work/test_browser_compatibility_diagnostic.py -x -q
```

Result: **3 diagnostic tests passed in 9.63 seconds**, zero skips. This is a
diagnostic pass count, **not** a pass count for the unchanged production browser
suite. Earlier diagnostic failures exposed Playwright interception limits and
were corrected openly; no production login failure was relabelled as success.

Playwright `page.route` does not reliably intercept later server redirect-chain
requests. The final harness therefore uses Chrome DevTools `Fetch` interception
at the **actual Google authorize request**, after browser CSP checks. It never
rewrites the real start response or its Google Location. The backend uses the
actual Google adapter with MockTransport token/JWKS responses, actual RSA signing
and library verification, nonce/PKCE/client/callback checks and real identity and
catalog persistence. Only external provider behavior is synthetic. A fresh
profile GET makes the proposed form-page header interceptable before diagnostic
logout; production home/profile header behavior still requires its final tests.

## Candidate and remaining gate

Keep rejection of opaque/missing/wrong origins and all existing CSRF/session
controls. Proposed narrowly scoped changes for independent review are:

- Effective `Referrer-Policy: same-origin` on successful HTML form documents
  `/login`, `/` and `/profile`; other responses, especially callbacks/errors and
  redirects, retain `no-referrer`. Same-origin policy suppresses cross-origin
  referrers; do not weaken to a policy that sends callback secrets cross-origin.
- Add the fixed Google authorization source to **login-document only**
  `form-action`; other documents remain `'self'`. The application still fixes
  the exact authorize endpoint/client/callback and rejects arbitrary returns.
  CSP source-path matching has redirect semantics and is not a substitute for
  the application endpoint allowlist.

ADR-009 says “Adding any source or element class requires architecture/security/
test review” and fixes `no-referrer`; `AGENTS.md` reserves material architecture
and security decisions to the owner. These reviews and the explicit owner gate
were completed before activation. The full native browser suite then ran against
real production response policies without diagnostic header substitution. No risk
acceptance, deployment authorization or SEC closure follows from these results.

## Approved activation and final runtime result

The owner explicitly approved ADR-012 after independent architecture, security
and test-design review. The production outer response policy binds each exception
to exact GET method, registered path, status 200 and HTML class. Only login HTML
receives the Google form-action addition; home/profile remain self-only.

The lead's final integration command included all browser tests:
`pytest tests/test_identity_use_cases.py tests/test_runtime_postgres.py tests/browser/test_auth_journeys.py`.
Result: **52 passed in 9.68 seconds**, including **seven browser cases** and all
eight identity-core PostgreSQL cases. The browser suite uses actual production
headers, native forms and CDP interception of the actual Google request. It does
not rewrite the start redirect or replace the browser's Origin header.

The seven cases cover login/profile/logout and revoked-cookie reuse; invalid
CSRF, GET logout and client-actor input; independent A/B browser logout; enforced
nonce CSP with positive/negative script controls and reflected callback input;
and blocked off-provider, wrong Google path and Google-form-from-profile
submissions. The latter collect only directive categories and assert no external
network request. Final cumulative `make check` and independent implementation
security/code evidence remain separate completion requirements.

The subsequent cumulative `make check` completed with **exit 0: 580 passed,
0 failed, 0 skipped**, including all seven browser cases, in 72.91 seconds.
The Starlette TestClient/httpx deprecation warning remains recorded. This result
does not convert synthetic-provider evidence into live Google/deployment proof.

Final follow-up expanded the production browser module to **nine cases**. Two
AUTH6-11 cases inject failures before pair creation and after pair commit/before
ready marking, then prove pending home/profile/logout, no normal-request retry
and successful fresh-login convergence to exactly one pair. The happy path now
also seeds real stored preference/control canaries and signed provider
name/picture probes, asserting those unselected values never reach profile
HTML/JSON/DOM/image/execution sinks. This does not introduce or claim a stored
text-rendering feature.

The historical 582-case run passed in 75.37 seconds. After 56 additional
independently reviewed actor-issuer guard mutations, the final authoritative
canonical run is **exit 0: 638 passed, 0 errors, 0 failed, 0 skipped in 76.196
seconds**, including all nine native HTTPS browser cases. The historical
52/580/582-case results above are preserved as earlier verification stages. Separate
independent security/evidence review of the browser/catalog implementation
passed; this document's author does not self-review those implementations.
