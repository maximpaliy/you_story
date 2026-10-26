# Issue #11 implementation verification

Date: 2026-10-26. Baseline main `4c6ac30`; feature branch
`codex/issue-11-personal-yousician-catalog`. No deployment or real user data.
The owner approved the HTTP contract, author-search amendment, scoped catalog
policy defaults and ADR-013 before implementation. Independent design reviews
passed; implementation reviews are recorded separately with initial findings and
remediation deltas.

## Final canonical run

Executed with the guarded disposable database, sequentially (no concurrent
schema-mutating suites):

```sh
TEST_DATABASE_CONFIRM=disposable \
TEST_ADMIN_URL=postgresql://postgres:local-fixture-only@127.0.0.1:55439/you_story_issue9_test \
TEST_CHROMIUM_PATH=/usr/bin/chromium UV_CACHE_DIR=work/uv-cache make check
```

Result: **736 passed, zero failures, zero skips**, 91.95 seconds. One existing
Starlette/httpx TestClient deprecation warning; no test was hidden or skipped.
The same command passed Ruff checks/formatting, strict mypy (54 source files),
architecture/composition/SQL registration checks, exact OpenAPI regeneration,
wheel build, and built-wheel inventory/SQL/composition inspection.
Local JUnit and full command output: `work/test-results.xml` and
`work/canonical-check.log` (scratch evidence, not deployed assets).

Actual catalog coverage includes 36 domain/serialization/cursor cases, 1 secret
configuration case, 16 HTTP adapter cases, 2 logging-filter cases, 9 repository
PostgreSQL cases, 23 public-service PostgreSQL cases, and 7 real HTTPS Chromium
catalog journeys. Existing authentication, architecture, database-security,
migration and artifact suites run cumulatively. These are counts of collected
tests, not an invented count of every subcase in the design matrix.

The catalog journeys use production application/session resolution, forms,
CSRF/provenance, SQL and security headers. Only the synthetic Google transport
is replaced at its documented test boundary. Guitar/piano CRUD, breadcrumbs,
metadata defaults/replacement, native moves/tombstones, author inheritance after
edits/moves, stale forms, JSON ETags/preconditions, cross-tenant IDOR, XSS,
referrer policy and logging positive controls ran successfully.

Repository/service evidence includes immutable definition v1/v2 interpretation,
fixture-only distinct Songsterr persistence, independent predicate-vs-FORCE-RLS
mutations with an actual leakage positive control and checked restoration,
repeatable-read ancestry/author coherence, timeout rollback, same-version races,
create-vs-tombstone and move-vs-tombstone races, and mass-assignment denials.
Migration tests cover empty/upgrade/replay and before/after-DDL/after-ledger
interruptions for every real revision, including additive 006. Applied 000–005
were not edited. Default migration target is now 006.

## Environment and browser qualification

Python 3.12.14; PostgreSQL 17.6-bookworm from the existing disposable Compose
fixture; locked dependencies and Playwright runner 1.56.0. Local engine:
**Chromium 151.0.7922.173 (Debian 13)** via TEST_CHROMIUM_PATH.
The Playwright-pinned Chromium 141 download was explicitly denied by the managed
network policy for cdn.playwright.dev and playwright.download.prss.microsoft.com.
No proxy bypass or TLS weakening was attempted. The locally installed engine
ran all actual browser checks. Existing GitHub CI installs the runner-pinned
Chromium build and must independently verify that engine; local evidence does
not claim the blocked download or pinned-engine execution passed.

## Installed-wheel smoke

Built artifact SHA256:
`427a654d31556a4034a82344338088c1382689b3b86de059125983f156304404`.

Created a separate venv, installed frozen exported runtime dependencies with
hash verification, then installed the wheel with --no-deps. Ran an isolated
Python (`-I`) smoke script; asserted package import resolves under
`work/wheel-env/lib/python3.12/site-packages`, never src. Verified packaged 006
SQL checksum, metadata/strict integer and signed cursor behavior, exact 27 runtime
route registrations, health/auth-unavailable/405 behavior, no-store headers and
packaged author-search OpenAPI. Result: pass. Scratch command artifacts are
`work/wheel-requirements.txt`, `work/wheel-smoke.py`, and
`work/wheel-smoke-results.json`.

## Contract and logging evidence

All 9 baseline OpenAPI operation contracts remain exactly equal as parsed JSON;
18 approved catalog JSON/HTML operations are additive. The active contract is
`docs/api/openapi.json`; packaged catalog schema matches the approved candidate.
Exact route/method Counter controls retain hidden-route and duplicate/unapproved
method negative tests. Closed response serializers have poisoned-repository
controls preventing tenant/grant/ownership fields, even nested, from escaping.

Enabled local sinks: Uvicorn access logging disabled (`access_log=False`),
forwarding disabled (`proxy_headers=False`); existing app/uvicorn.error loggers
are captured with safe INFO/ERROR positive controls. Browser canaries prove
actual stored/reflected text, query, native same-origin Referer and cursor data
are absent. Separate tests explicitly emit sensitive Uvicorn-access and httpx
records through their real filter pipelines and verify suppression alongside a
captured safe positive marker. SQLAlchemy echo remains disabled and parameter
hiding enabled. No reverse proxy or additional telemetry/sidecar sink exists in
this local fixture. Future deployment must verify every newly enabled sink;
no unconfigured proxy evidence is claimed.

## Findings resolved and limits

Earlier runs exposed/fixed a missing-context test oracle (fail-closed exception),
select accessible-name markup, Playwright's incomplete convenience header view,
multi-method OpenAPI gate handling, explicit serializer allowlists, omitted
navigation beyond 100 children, and default migration target 005. The first
canonical run had 734 passes and two logging test assertion failures (metadata-
only unavailable resolver returns 503); corrected tests pass in the final run.
The final evidence above supersedes those runs without hiding their findings.

No production deployment, live Google registration, global SEC-01/06/07 closure,
production log-proxy verification, capacity/SLO approval or mixed production
load result is inferred. Deterministic request/query/timeout bounds are tested;
the proposed p95 500ms target remains planning input under the approved strategy.
No sharing, import, practice/characteristic workflow or Songsterr user feature
is exposed. Independent implementation code/security reviews assessed the final source and
actual evidence and passed after remediation. Their scoped verdicts retain the
pinned-browser CI requirement before merge/release.
