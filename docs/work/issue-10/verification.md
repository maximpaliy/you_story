# Issue #10 implementation verification

Date: 2026-10-26. Base: merged #9 / PR #25 `ca99acd`; proposal commits in
[PR #26](https://github.com/maximpaliy/you_story/pull/26). Owner approved the
HTTP contract and scoped ADR-012 browser amendment in this conversation.

## Executed environment

- Python 3.12.14; uv 0.12.19; PostgreSQL 17.6; Ruff 0.17.2; mypy 2.4.0;
  pytest 9.1.1; Playwright 1.56.0. Production dependency pins are in uv.lock.
- Real localhost-only marked disposable you_story_issue9_test fixture. Owner
  migrations authenticate as app_owner; production calls use app_runtime, with
  FORCE RLS and separate fixture-admin inspection. No SQLite/owner-as-runtime.
- Local browser explicitly selected with TEST_CHROMIUM_PATH=/usr/bin/chromium:
  Chromium 151.0.7922.173 (Debian). CI installs the frozen Playwright bundled
  engine; that separate CI engine is not claimed executed locally.
- Uvicorn HTTPS fixture has synthetic certificates, access_log=False and
  proxy_headers=False. Certificate bypass applies only to its generated local
  certificate. Actual fixed Google navigation is intercepted using CDP Fetch;
  the original start response/Location is not rewritten. Backend provider
  transport returns real signed synthetic RS256 tokens/JWKS, not live accounts.

## Canonical command and results

The guarded local command is:

```sh
TEST_ADMIN_URL=<marked-disposable-fixture-admin-url> \
TEST_DATABASE_CONFIRM=disposable TEST_CHROMIUM_PATH=/usr/bin/chromium \
UV_CACHE_DIR=work/uv-cache make check
```

The initial complete run passed 580 tests. Independent evidence review then
identified missing actual-composition pending-catalog fault journeys; two native
browser cases and persisted-input probes were added. The next complete run
exited zero: **582 passed, 0 failed, 0 skipped**, 75.37 seconds, including:

| Suite | Cases |
| --- | ---: |
| Native HTTPS Chromium | 9 |
| Auth crypto/config | 25 |
| Existing PostgreSQL authentication foundation | 98 |
| Browser policy/HTTP controls | 188 (including 120 method/path/status/media combinations) |
| Google signed-token/deadline/key-cache boundary | 87 |
| Identity public-port/orchestration | 29 |
| Catalog provisioning | 5 |
| Privacy/access logging | 2 |

The remaining cases cover source/artifact/SQL/OpenAPI mutations, runtime/pool
security, exact schema/RLS, migration rollback/upgrades and health behavior.
Lint, formatting, strict typing (48 production files), source/SQL/composition,
generated OpenAPI, wheel build and artifact inventory all passed. Retained
sanitized work/issue10-check.log and work/test-results.xml record the actual
commands/counts. These workspace intermediates are not committed as raw traces.
The final guard-only amendment and authoritative rerun are recorded below.

One existing upstream Starlette TestClient/httpx deprecation warning remains.
uv build warns that work/uv-cache sits below the build directory; exact wheel
payload comparison passed, proving that scratch/cache files are not packaged.
Neither warning was hidden or converted into a skipped required test.

## Additional actual evidence

- Focused production HTTPS/browser run: 9 passed in 12.85 seconds. Tests cover
  login/profile/native logout, revoked bearer replay, wrong CSRF, two-user
  isolation, direct actor-field rejection, enforced CSP and Google navigation.
- Before-pair and post-pair-ready fault tests execute the real app callback
  orchestration. Identity/session/admission commit survives; catalog row counts
  are respectively zero or one pair; pending profile/logout remain usable;
  ordinary GETs never retry; later fresh login retains the same identity and
  consumed admission and converges on one pair plus ready state.
- Actual persisted preference/control and signed provider name/image canaries
  remain absent from HTML/JSON/DOM. No nonexistent stored-text rendering sink is
  reported tested. Synthetic callback reflection stays unreflected.
- Real public-port tests cover successful digest-only issuance, one-shot claim
  erasure/replay, invalid proof, expired claim/session, provider/AEAD/challenge
  failure, unknown admission, two-device/cross-user CSRF and logout boundaries.
- Snapshot seals reject construction and mutation of genuine issued actors and
  sessions before authority-bearing SQL. Source/query mutations detect missing
  actor predicates independently of RLS.
- Installed-wheel smoke imports exclusively from an extracted wheel and verifies
  runtime-only database readiness, packaged login templates, active ADR-012
  policy, anonymous profile denial and GET-logout denial. It passed; no source
  package or test actor factory supplies that smoke's application implementation.
- Every applied 000–005 migration is unchanged; no new SQL privilege/migration,
  worker, media adapter, provider-selection or destructive endpoint was added.

## Review and evidence limits

Independent implementation security, provider/core code, composition/catalog,
policy-design and test-evidence reviews are linked from README.md. Authorship
exclusions prevent self-approval. The initially found actor-mutation seal,
access-log URL leakage, outage misclassification, origin parsing, provider client
validation and required pending-flow evidence were remediated and tested.

Real Chromium exposed the originally approved native-form incompatibility.
Historical failures and three diagnostic comparisons remain explicitly recorded
in browser-compatibility-evidence.md. The owner separately approved ADR-012;
final browser cases use its actual production headers without diagnostic
substitutions. This does not waive null-Origin rejection or CSRF.

No live Google account/registration, production TLS/proxy/tracing/cloud-IAM,
paid infrastructure, real-user data or production deployment was exercised.
Production/deployed credential separation, global security finding closure and
later feature matrices remain their own gates. This evidence is a local
implementation acceptance record, not production-release authorization.

## Authoritative frozen result after final issuer-guard review

Independent final gate review found that another registered identity module
could import or extract the private session issuer without the source checker
rejecting it. The actual implementation used the intended issuer path, but the
claimed static boundary was incomplete. IR-G01 was remediated by checking
minting imports, aliases, extracted/qualified references, wildcard imports and
exact permitted call sites. Fifty-six meaningful guard mutations were added;
the independent reviewer reproduced rejection and ran 112 focused gate tests.
No feature behavior, SQL migration or provider policy changed for this fix.

The final **make check exited 0: 638 passed, 0 errors, 0 failures, 0 skipped,
76.196 seconds** (summary rounds to 76.20). It includes 103 architecture cases,
nine browser cases and all feature cases above. Ruff checked/formatted 153
Python files, strict mypy checked 48 production files, and source/SQL, generated
OpenAPI, build and exact wheel checks passed. The one upstream Starlette warning
remains. Prior 580/582 runs above are historical, not the final aggregate.

Frozen production inventory SHA-256:
`9fb0e97e00ff826d3438fc7f7a3943195ed30b91d12dc797b993de7051bd45a2`.
This hashes sorted package-relative paths, a NUL separator, exact bytes and NUL
for every packaged .py/.sql/.json/.html file under src/you_story.
Final wheel SHA-256:
`104d439f356b90d87e8a6b6da3e65bc553ae0a0688a0279ff29fd7d6f4727cae`.

Independent partitioned implementation code/security and final test-evidence
reviews pass after remediation. The separate final gate review is recorded in
composition-code-review.md. All review scopes and author exclusions remain
explicit; no report grants production deployment or accepts a security risk.
