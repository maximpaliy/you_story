# Independent test-evidence review — Issue #10

- Reviewer: independent test reviewer; not the feature-test author
- Date: 2026-10-26
- Baseline: `ca99acd` plus current Issue #10 source/test changes and approved ADR-012
- Verdict: **scoped feature test-evidence pass after TE10-01 remediation**,
  including the final frozen-source cumulative run: **638 passed**
- Reviewed evidence: `work/test-results.xml`, `work/issue10-check.log`, actual test
  source, application/browser policy and provider-interception code
- Reviewer execution: inspected/parsed retained results; did not rerun the
  destructive PostgreSQL or browser suites during this review

## TE10-01 — Required pending-catalog orchestration journey — resolved

AUTH6-11 requires failure on either side of the catalog/ready boundary to leave
an active session and catalog_pending, ordinary profile/logout to remain usable,
normal requests not to retry provisioning, and a later fresh login to reconcile
exactly one complete catalog/grant pair and ready state.

The initially reviewed catalog tests proved isolated pair rollback, idempotence,
actor predicates, RLS isolation and concurrent convergence. Foundation tests
proved the identity ready wrapper separately; initial browser journeys covered
successful login and profile.
None of those exercised failure of the actual app callback's `provision` closure,
especially failure after the pair commits but before identity is marked ready.
The initial 580 passing cases did not satisfy this explicit approved journey.

Remediation now implemented in
`test_pending_catalog_failure_keeps_session_and_fresh_login_retries[before/after]`.
Both use the actual application callback closure, native HTTPS forms, signed
provider adapter and real runtime/PostgreSQL. Test-only faults occur before ensure
or after the real catalog pair commits and before ready marking. They inspect
active identity/user/tenant and consumed admission, pending own profile, pair
counts of zero/zero versus one/one, and no repeated ensure/ready calls during
ordinary home/profile requests. Native logout produces unauthenticated profile;
removing the fault and completing a fresh login preserves the user/admission and
converges to exactly one catalog/grant pair and ready state. A second native
logout again revokes access. These are committed-state oracles, not only mock
call/status assertions.

Parsed `work/issue10-browser-final.xml`: **9 passed, zero failed/errors/skipped**
in **12.846 seconds**, including both remediation parameter cases. Source review
confirms no Origin/response-policy substitution or start-redirect rewrite was
introduced. TE10-01 is resolved. The original happy browser case additionally
seeds real stored preference/control canaries and signs malicious provider
name/picture fields, asserting their absence from actual DOM/JSON and absence of
new image nodes or executed canary variables. It does not invent a stored-text
rendering feature.

## Verified result inventory

Parsed final `work/test-results.xml`: **638 cases, zero failures/errors/skips**,
no repeated classname/name pairs; suite duration **76.196 seconds** (log rounds to 76.20). The recorded
canonical log agrees with collection/results and passes Ruff, formatting, strict
mypy (48 source files), source/composition, generated OpenAPI, wheel build and
wheel inventory checks. Ruff formatting checked 153 files. One upstream
Starlette TestClient/httpx deprecation warning remains and was not hidden. The
final run includes both added fault-boundary browser cases and 56 newly added
issuer-capability gate mutation cases; no extra focused count is added to the
canonical total. These results confirm checks ran; a green
total is not a substitute for per-case review.

| Actual suite | Executed cases | Substantive reviewed scope |
| --- | --- | --- |
| Browser journeys | 9 | Native HTTPS login/profile/logout, replayed revoked cookie, invalid CSRF/GET logout/request actor, two independent accounts, CSP positive/negative scripts and reflected-error exclusion, off-provider/wrong-Google-path/profile-to-Google form blocking; both pending-catalog failure boundaries and fresh-login reconciliation |
| Provider | 87 | Real RSA signatures, issuer/aud/azp/nonce/time/type rejection, duplicate/nonfinite JSON, signing/key constraints, fixed endpoints, bounded cache refresh, response sizes and shared total timeout |
| Crypto/config | 25 | Signed binder/proof tampering and original expiry, AEAD/AAD substitution, reference HKDF/digest/rotation, canonical tokens, trusted IP HMAC and fail-closed configuration |
| Identity use cases | 29 | Direct public ports, real DB login/digest storage, invalid proof/expired claims/session, five claimed-failure branches, independent sessions/logout, forged and mutated actor/session rejection |
| Browser policy | 188 | Raw header/cookie/form/query/body/provenance parsing, callback generic failures, cookie lifecycle, exact ADR-012 scope and header policy; **120** of these are the method/path/status/representation Cartesian matrix |
| Catalog provisioning | 5 | Public actor rejection; explicit scope/bind oracle; real-runtime idempotence/isolation, grant rollback and concurrent pair convergence |
| Source architecture | 103 | Exact registered file/module/SQL/process boundaries, actor/session construction and registry protection, and 56 additional direct/aliased/qualified/extracted/wildcard mint-capability mutations |
| Auth foundation | 98 | Existing exact function/ACL inventory, claims/admission/session atomics, lock/expiry and revoke/touch races, issuance limits, bounded cleanup/capacity and independent SQL guard mutations |

A later independent gate review found that a same-owner registered provider
file could import/call `issue_session` even though actor construction was
restricted. The actual provider did not misuse it. Exact import/reference/call
checks now seal the actors -> wiring._issuer capability chain; 56 additional
mutation cases reject alternate registered-file calls, aliases, module-qualified
references, callback extraction and wildcard imports. The separate independent
[composition review](composition-code-review.md) reproduced the finding, verified
its remediation and reports 112 focused cases passed. The final canonical 638
includes the gate fix; the earlier 582 run is historical, not the final approval
basis. Production feature behavior and SQL did not change for that gate repair.

The remaining cases cover cumulative role/RLS/schema/migration/pool/runtime and
source/artifact/OpenAPI checks. Existing foundation tests are executed again;
they are not newly authored feature tests. The 29 identity cases include eight
real-PostgreSQL parameter-expanded cases; unit Store fixtures are explicitly
labelled and are not credited as database atomicity evidence.

## Native browser policy assessment

The current real-browser helper uses CDP Fetch interception at the actual fixed
Google authorize request, after CSP processing. It preserves the real native
POST-start response and Google Location, replacing only external provider
behavior with a synthetic callback. The backend uses maintained-library signed
RS256 validation and real database state. This addresses the earlier diagnostic
problem where redirect replacement could bypass the navigation under test.
The final tests do not inject Origin or substitute production response policy.

ADR-012 policy tests parse all CSP directives and exact varying nonce rather
than matching an allowed-host substring alone. The 120-case matrix binds the
exception to exact GET/path/200/HTML; callback/errors/non-HTML/redirects keep
strict defaults. Nine browser tests include actual forbidden form violations
and absence of intercepted external requests. Their positive allowed Google
navigation provides an observed request control.

## Evidence limits

Browser evidence uses the explicit local system Chromium 151.0.7922.173 override
with Playwright 1.56.0. It is not execution against the CI bundled engine; the
repository keeps the pinned default/CI installation. No live Google registration,
network exchange, deployment or production user data was exercised.

The feature has no stored user-text rendering sink. Actual stored-canary
exclusion plus escaping/control tests are appropriate; they do not establish
future notes, tags or rich-text rendering behavior. No standalone test per every
designed AUTH6/WEB subcase is inferred from the passing counts, and no operational
proxy/trace deployment evidence is claimed. Future deployed observability and
production privacy/operations gates stay separate.

Source and artifact gates were authored by this reviewer, so their test-design
independence is limited here: their outcomes are reconciled as cumulative
checks, not offered as an independent code review of the reviewer's own gates.
The separate composition review supplies that independent gate review; feature
implementation/security dispositions remain in their respective reports. This
test-evidence pass authorizes no deployment or unrelated security-gate closure.
