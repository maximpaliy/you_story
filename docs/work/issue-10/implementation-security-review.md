# Independent implementation security review — Issue #10

- Reviewer: security-review agent, independent of the identity-core, crypto,
  PostgreSQL adapters, catalog provisioning, delivery and composition authors
- Date: 2026-10-26
- Scope: `identity/application/service.py`, public/domain contracts, private
  config/crypto/actors/postgres/wiring; browser adapter/templates; root app;
  catalog public/provisioning boundary; merged 005 integration obligations
- Excluded from independent verdict: `identity/infrastructure/google.py` and
  its tests, which this reviewer authored. A different reviewer must approve
  that provider implementation and evidence.
- Verdict: **independent implementation/evidence pass for the inspected core,
  delivery, catalog and composition boundaries**. The final reassessment below
  supersedes earlier pending checkpoints. Authored Google provider code is
  excluded and requires the other reviewer's disposition. No deployment or
  global security-finding closure is granted by this scoped pass.
- Current frozen final acceptance evidence: **638 passed, zero errors/failures/
  skips, 76.196 seconds**, including nine native HTTPS browser cases. The
  580- and 582-case results below are historical checkpoints, superseded by the
  frozen final evidence addendum.

## IS10-01 — Genuine issued actor/session could be mutated without breaking its seal

**Blocking finding; source remediated and focused tests passed.** Initially the
weak-reference registries checked object identity only. A legitimate issued A
actor could be changed with object.__setattr__ to another tenant while retaining
registration. Catalog's direct public command would trust that actor and install
the changed tenant into its RLS context. Frozen dataclasses and rejection of new
forged objects did not cover modification of genuine registered evidence.

This reviewer reproduced acceptance of the changed actor before remediation,
without touching PostgreSQL. The revised registry binds original actor UUID
bytes/provenance and original session actor identity/session UUID bytes/state/
expiry/bearer hash. Validation compares current values with those snapshots,
including exact object/UUID/bearer types. UUID bytes are copied snapshots, not
references to a mutable UUID object. A changed actor or session now fails before
catalog or identity use-case SQL. Focused tests mutate all actor authority fields
and five session fields; they assert no ready/revoke side effect. These tests
are stronger than constructor-only forgery tests and were independently run.

The process memory itself, private issuer access and registry internals remain
trusted Python application code, not a sandbox against arbitrary code execution.
HTTP models never deserialize those objects or expose registry/issuer selection.

## IS10-02 — Default server/client access logging could expose callback credentials

**Blocking finding; supported local source/logging boundary remediated and focused
canary test passed. Final aggregate/launch evidence remains pending.**
The initial documented uvicorn invocation allowed default access records, which
include the callback query containing code/state. Safe app-level error messages
do not sanitize an independent server or HTTP-client log sink.

The app now installs filters suppressing raw uvicorn.access and httpx records
before handlers; safe event/correlation logging remains separate. The documented
launch adds --no-access-log and --no-proxy-headers, and the real browser fixture
uses the same flags. Disabling implicit forwarding interpretation also prevents
an untrusted X-Forwarded-For value from selecting request.client rate keys in
this supported local launch. Future deployed trusted-proxy configuration remains
a separately reviewed environment boundary.

The independently run canary test has a positive capture control and injects raw
access/client query values, asserting their absence in retained logs/response.
Its two-case logging/contract suite passed in 0.52 seconds. Final evidence
must identify every enabled sink and the actual launch policy; a test of one
logger cannot certify an unconfigured external reverse proxy or tracing agent.
No such production sink is silently approved by this review.

## IS10-03 — CSRF validation hid a database outage as forbidden

**Source remediated and focused test passed.** Initial validate_csrf caught every
AuthFailure, converting a 503 dependency failure to False and then HTTP 403.
It now propagates 503 while wrong/malformed/expired/foreign CSRF still returns
uniform forbidden without a revoke. The focused outage test asserts 503 and no
revoke. This preserves both fail-closed authority and truthful infrastructure
failure reporting.

## IS10-04 — Approved header combination blocks the required native browser journey

**Historical blocker; resolved by approved ADR-012, inspected implementation and
native-browser evidence in the final reassessment.** The real HTTPS Chromium baseline reports
403 at native login start, opaque Origin/no Referer and zero provider exchanges.
The current strict provenance gate correctly rejects that request; changing
test headers or admitting Origin:null would conceal the defect. The additional
external-303/form-action interaction is being isolated in a diagnostic fixture.

Proposed ADR-012 and the separate [browser-policy security review](browser-policy-security-review.md)
describe a narrow compatibility adjustment. It remains inactive until explicit
owner approval. Diagnostic header overrides are not passing production behavior.
After a decision, inspect exact activated policy and require native-form browser
login/profile/logout plus adverse origin/CSRF/CSP/header-class tests. No design
review of the proposal substitutes for the owner's decision or executed evidence.

## IS10-05 — Empty query/fragment delimiters accepted by strict origin parsers

**Minor contract finding; source remediated and focused tests passed.** Origin and
deployment-origin parsing reject nonempty query/fragment but initially accept
`https://app.example?` or `https://app.example#`, because urlsplit returns empty
query/fragment strings. Both parsers now reject those delimiters explicitly for
origins while preserving the reviewed rule that Referer path/query/fragment are
ignored after validating its origin portion. Exact negative controls are present.
Deployment client IDs now also reject embedded NUL/DEL consistently with visible
ASCII provider-audience validation. The focused origin/client selection passed
28 cases in 0.28 seconds (64 unrelated cases deliberately deselected).
No cross-origin authority
bypass was demonstrated; this is a strict-schema consistency issue, not an
accepted request-provenance relaxation.

## Inspected controls and remaining verification

The service obtains DB time, validates signed nonrenewing binder/proof, generates
the transaction UUID before AEAD encryption, binds verifier to that UUID/client,
and verifies PKCE challenge before provider exchange. Claim commits independently
before networking; result parsing keeps 005's exact success/denial fields and
normal denials commit to preserve outer attempt budgets. Failed claims are
terminalized separately and never reopened. Fresh session UUID/bearer/CSRF are
generated only after verified identity, and returned session UUID is checked.

Private adapters call only fixed, bound-parameter 005 wrappers. They retain
reviewed one-shot allowlist/bearer selection, legacy-invalid linkage, shared
advisory serialization, post-wait clocks and no direct control-table privileges.
Resolver results do not broaden to expose CSRF/token digests. HKDF/AESGCM come
from maintained cryptography primitives; canonical encoding, domain labels,
signed original expiry, associated data and constant-time digest comparison
match the approved contract. Missing configuration has no insecure default.

Ordinary request authority comes only from a resolved session and sealed actor.
Current-session logout/ready re-resolve and compare linkage before their narrow
wrappers. Public profile returns only owner-approved user_id/readiness, never
tenant/session IDs, provider claims, tokens or private preferences. Alternate
URL/body/header credentials cannot establish or override the actor.

The catalog transaction enforces explicit actor-bound insert/read predicates
independently of FORCE RLS and creates exactly one catalog/owner-grant pair.
Its atomic failure does not roll back already committed identity/session; only
login composition calls it and then conditional readiness. No profile/middleware
retry, extra catalog command, worker or cross-owner SQL was identified.

Browser parsing caps streamed bodies/query bytes, rejects ambiguous cookies,
duplicate fields/headers and unsupported media, applies strict configured-origin
and Fetch Metadata checks, and keeps callback GET the sole narrow mutation
exception. Logout remains protected POST. Autoescaped templates do not render
provider/user text, callback failures remain generic HTML, and one outer policy
adds no-store/CSP/security headers to early errors as well as successful output.

Independent focused run after the seal/CSRF fixes:

`pytest tests/test_identity_use_cases.py tests/test_auth_crypto.py tests/test_browser_policy.py tests/test_catalog_provisioning.py -m 'not postgres' -q`

Result: **109 passed, 5 PostgreSQL cases deselected, one upstream Starlette/httpx
deprecation warning, 1.16 seconds**. This was a declared unit/delivery subset,
not an integration acceptance run. An earlier sandboxed attempt stalled before
TestClient startup and was terminated; the successful run used the supported
network-enabled executor permissions needed for asyncio's local self-pipe.
No destructive shared-database suite was run concurrently by this reviewer.

Final canonical PostgreSQL/wheel/architecture/OpenAPI results, real-browser
journeys, canary-sink collection, provisioning races/faults and the independent
provider review remain required. Passing the focused subset cannot override
IS10-04 or those missing results. No security risk, production exposure,
real-user data or global SEC-01/05/06/07 closure is approved here.

## Authoritative final implementation and evidence reassessment

The owner explicitly approved the exact scoped ADR-012 adjustment on 2026-10-26
before activation. This reviewer inspected the final predicate and root wiring:
only HTML/status-200/exact-GET /login, / or /profile responses use same-origin
referrer policy; only the login-form class adds the fixed Google authorize source
to form-action. Every other response, including callback/errors/redirects/JSON
and absent request classification, retains strict defaults. No null-Origin,
request-selected provider/source or provenance bypass was introduced. All other
CSP directives, nonce, cookie/CSRF and outer security-header controls remain.

The final native-browser tests retain actual form POST and server 303 behavior.
Their CDP replacement intercepts the fixed Google request **after** browser CSP
checks and supplies only a synthetic provider redirect; it does not rewrite the
original start redirect, synthesize same-origin provenance or override response
policy. The provider transport signs RS256 synthetic tokens while PostgreSQL,
cookies, templates, public ports, catalog wiring and logout are real. Browser
negatives verify bad CSRF/GET logout/actor query rejection, independent accounts,
revoked-cookie replay, actual blocked script with a matching-nonce positive
control, generic unreflected callback errors, attacker form targets and
non-login Google form denial. These assertions substantiate the compatibility
remediation rather than just checking a 200 status.

Independent reviewer focused runs are recorded above. After activation this
reviewer additionally ran the browser-policy/logging suites: **190 passed, one
upstream Starlette/httpx warning, 1.10 seconds**. The 120-combination policy
classification matrix checks every remaining directive and strict fallback.

The coordinator's final canonical `make check` completed successfully. This
reviewer independently parsed `work/test-results.xml` and inspected
`work/issue10-check.log`: **580 tests, zero errors/failures/skips, 72.911 seconds**.
The run includes 7 real HTTPS browser cases, 29 identity use-case cases, 5
catalog-provisioning cases, 98 retained database-auth foundation cases, 188
browser-policy cases, 2 safe-logging cases, 28 migration and 16 runtime
PostgreSQL cases, together with the remaining architecture/contract/provider/
foundation checks. These are the coordinator's executed aggregate results,
not a claim that this reviewer concurrently reran the destructive database suite.

The checked log records lint/format pass for 152 Python files, strict mypy for
48 source files, source/SQL architecture and generated OpenAPI checks, wheel
build and packaged-artifact checks. The upstream Starlette/httpx deprecation
warning was not hidden. The build's cache-location warning remains separately
visible; artifact inventory checks passed. The actual `005_identity.sql` SHA256
was independently rechecked as
`4cad83d3b26ad8dab1abbb2666c21ed1a6db7c088cec844745009d55c91e04bc`,
matching merged #9's reviewed foundation; no new auth migration is substituted.

**Final scoped security disposition: pass.** IS10-01/02/03/05 are remediated with
focused source/test evidence. IS10-04 is resolved by the explicit owner decision,
exact activated header matrix and native-browser result. No unresolved blocking
security defect was identified in this review's inspected implementation scope.
The Google adapter remains excluded from this reviewer's independent verdict
because of authorship; its separate independent code/evidence review is required.

This supports acceptance of the implemented #10 authentication integration slice
through the normal PR/review process. It does not establish a live Google OAuth
registration, production TLS/proxy/telemetry behavior, production credentials or
real-user-data permission. Future endpoints/resources must extend the same
cumulative controls and evidence. No residual risk is accepted and no global
SEC-01/05/06/07 finding is silently closed for future feature/deployment scopes.

## Final acceptance evidence addendum — 582-case run

The coordinator added the previously missing actual-app catalog fault journeys
and strengthened stored-input exclusion probes, then reran the full canonical
command. This reviewer inspected the added test source, parsed the new
`work/test-results.xml` and rechecked the aggregate log. The current result is
**582 passed, zero errors/failures/skips, 75.370 seconds**, with nine actual
HTTPS browser cases and one visible upstream Starlette/httpx warning. Static,
type, architecture/SQL, generated OpenAPI, wheel build and packaged-artifact
checks passed again. This supersedes the earlier 580-case acceptance checkpoint;
it is not an independently rerun destructive suite by this reviewer.

The two parameterized browser fault journeys inject failure before catalog-pair
creation and after the pair commits but before readiness. Each uses the real
app, runtime database, native login and signed synthetic provider boundary.
Assertions inspect committed active identity/session and catalog_pending, exact
zero-pair or complete-one-pair state, and consumed invitation linkage. Repeated
home/profile GETs preserve both state and orchestration call counts. Native
logout works while pending. A later fresh login reuses the same user/invitation,
converges to exactly one catalog/owner grant and ready, and logs out normally.
These are genuine orchestration fault/retry observations, not tests of a fake
pending response or a mocked cookie assignment.

The stored-input probe now seeds actual tenant-private user_preference data and
consumed control-plane text canaries, alongside a signed provider-name canary.
It proves they are unselected and absent from real HTML/JSON/DOM, provider images
are absent, and no probe executes. This appropriately proves exclusion for the
minimal profile; it still does not claim a shipped stored rich/text rendering
journey or expand profile persistence.

**Final scoped security verdict remains pass**, now supported by the complete
582-case current acceptance run. No production implementation changed for this
test/evidence refinement. All scope exclusions, independent-provider-review
requirements and production/real-data limitations above remain unchanged.

## Frozen final acceptance addendum — 638-case run

The coordinator's frozen final canonical run completed **638 passed, zero
errors/failures/skips, 76.196 seconds**, with nine native HTTPS browser cases and
one unsuppressed upstream Starlette/httpx warning. This reviewer independently
parsed the current JUnit, checked the final log's successful aggregate/package
disposition, and inspected the added issuer-capability mutation coverage and
its source-gate logic. The current log also records 153 formatted Python files,
strict typing for 48 source files, source/SQL and OpenAPI gates, wheel build and
packaged-artifact success.

The additional 56 cases strengthen the static identity-issuance capability
boundary: direct and aliased imports/calls, module-qualified use, extraction,
registration and wildcard forms are rejected outside the exact approved chain.
The legitimate wiring-to-session-issuer-to-actor-issuer control remains allowed;
mutations moving or extracting that capability fail. Architecture cases rise
from 47 to 103. This is a gate/test hardening refinement, not a new product API,
database migration or browser policy. The coordinator additionally reports a
separate final-gate reviewer passing 112 focused cases; that result is attributed
to that reviewer, not an independent execution by this security reviewer.

**The authoritative final scoped security verdict remains pass on the frozen
638-case acceptance run.** The earlier 580/582 counts are retained solely as
historical verification checkpoints. No previously stated scope exclusion,
independent-provider-review requirement or production/real-user-data limitation
is relaxed, and no new unresolved security finding was identified.
