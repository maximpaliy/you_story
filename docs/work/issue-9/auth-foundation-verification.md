# ADR-011 authentication database foundation evidence

Date: 2026-10-23. Status: database foundation verified; independent reviews passed;
ready for owner review. No production/authentication exposure is authorized.
Baseline: merged PR #24 / ce4b102. Issue #6 and ADR-011 are approved; the prior
local #6 blocker was stale. Issue #9 was reopened for this owner-requested delta.

## Scope

Additive 005_identity preserves all 000..004 migration artifacts and existing
identities. It adds the exact seven-table authentication control plane, legacy-
nullable session identity/CSRF fields, owner-managed admission metadata inside
invitation, fixed privileged login/session/counter functions and an internal
session-derived ready transition. It registers no login/provider/browser route,
production actor issuer, catalog repository, worker or infrastructure.

SEC-05 provider/crypto/browser tests and catalog provisioning orchestration are
#10 scope. Passing database tests here cannot close those gates or certify that
real users may sign in. Deployed credential separation remains #16.

## Environment and isolation

Use the existing task-created PostgreSQL 17.6 Compose fixture on localhost,
exact database you_story_issue9_test, explicit disposable confirmation and its
required fixture marker. Owner migrations connect directly as app_owner; all
isolation/function authority tests authenticate as app_runtime. Administrative
connections arrange/inspect synthetic fixtures, never replace runtime evidence.
Database tests run sequentially against this fixture, not concurrently across
agents. No provider credentials, real users, production resources or external
identity endpoints are used.

## Review findings and verification

Independent preimplementation architecture, security and test-design reviews
passed for the concrete delta. Internal coarse failure discriminants represent
the already approved 409/429/503 outcomes; no account attributes, counts, scope or
limiter keys are added to failure results. All private result fields remain NULL
on generic failure; limits return only their fixed window end.

Implementation review identified expiry checks sampled before later row-lock
waits and caller-time-zone-dependent day intervals. Fixes must re-read database
time and lifecycle eligibility after authority-bearing row locks, and use fixed
UTC-duration arithmetic. Real lock-wait and non-UTC/DST probes are required.
Test review also requires observed blocking races, individual auth guard
mutations, discriminant/NULL shape checks and independent active-session-cap
versus issuance-rate-cap cases.

## Final canonical results

```sh
TEST_ADMIN_URL=<marked-disposable-fixture-url> TEST_DATABASE_CONFIRM=disposable make check
```

Python 3.12.14, uv 0.12.19, PostgreSQL 17.6, Ruff 0.17.2, mypy 2.4.0,
pytest 9.1.1. The final frozen-source command exited zero:

| Check | Result |
| --- | --- |
| Ruff lint / formatting | Pass; 118 Python files formatted |
| Strict mypy | Pass; 38 production source files |
| Source/import/SQL-site/composition/deployment gates | Pass |
| Exact generated OpenAPI / actual route inventory | Pass; health-only |
| Full pytest | **217 passed, 0 failed, 0 skipped**, 43.17 seconds |
| Wheel build / exact bytes and package inventory | Pass |
| Separately installed wheel, real Uvicorn, runtime-only credential | `/live` 200, `/ready` 200, `/login` 404 |
| Independent architecture/security/test/code reviews | Pass for #9 database foundation |
| Diff / historical 000..004 artifact comparison with origin/main | Pass; unchanged |

The full set includes 98 authentication database cases, 28 migration cases,
16 runtime PostgreSQL cases, and the retained RLS/constraints/architecture/
privacy/contract probes. Evidence includes observed independent-connection
blocking, both resolver/revoke serialization orders, real row-lock waits across
expiry, fixed-clock exact boundaries, non-UTC/DST durations, atomic failure at
all authority phases, independent SQL guard mutations, actual 100,000/200,000-row
admission boundaries, combined 100-row cleanup and exact 24-hour eligibility with
one-microsecond controls. The fixture-only clock is restored and checked.

A preceding 216-case canonical run passed; independent review then identified
the remaining exact retention-equality boundary. That test passed individually,
and the complete final 217-case command above passed. One upstream Starlette/
httpx TestClient deprecation warning remains unsuppressed. UV warns that its
workspace cache lies inside the source directory; exact wheel inventory proves
that cache and test fixtures are excluded. No hidden retries or skips are used.

Reviewed SQL005 SHA-256:
`4cad83d3b26ad8dab1abbb2666c21ed1a6db7c088cec844745009d55c91e04bc`.
Built wheel SHA-256:
`2443d184372667f43b24aab0925b519daa17213d4242e7bffb18bd6c816a39cf`.
Sanitized local test output is generated in `work/auth-foundation-check.log` and
`work/test-results.xml`; it is not uploaded as raw test data. All intermediate
failures/findings and their resolutions remain in the review records.

## Completion boundary

All scoped database findings are resolved. The architecture review confirms
that #9 can advance to owner review/completion once merged: requiring #10's
OIDC/browser/ActorContext/catalog orchestration first would invert the approved
#9→#10 dependency. These remain future feature gates, not a technical blocker
requiring #10 before #9. SEC-01 foundation evidence passes, while cumulative
SEC-01 and SEC-05 remain open for the later feature/runtime evidence. No global
security closure, Google validation, CSRF behavior, login journey or production
readiness is claimed by these database probes. In particular #10 must reconcile
its HKDF form validation with the least-result resolver contract without adding
direct table access or unreviewed result fields.

The exact Git revision and PR checks are recorded on the linked follow-up PR.
Temporary HTTP processes are stopped after smoke verification.
