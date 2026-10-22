# Issue #9 verification evidence

Status: implemented restricted subset verified and independently reviewed; full issue incomplete.

## Environment

2026-10-22; Python 3.12.14; uv 0.12.19; PostgreSQL 17.6 on a disposable,
localhost-only task-created Docker container. Integration administration uses
only `you_story_issue9_test`, guarded by its exact database name, explicit
`TEST_DATABASE_CONFIRM=disposable` and a synthetic fixture marker. The initial
reset attempt against an unmarked database was rejected by automatic approval
review; read-only container/database inspection followed by creation of the
new marked test database resolved that safely. No pre-existing database was
reset.

Migrations authenticate directly as `app_owner`; all runtime isolation checks
reconnect as `app_runtime` (non-owner, NOSUPERUSER, NOBYPASSRLS). Pool tests use
one physical connection and then a small pool with recorded seed. The owner
credential is never part of HTTP settings. Owner/cluster-admin assertions are
setup/catalog evidence, never substituted for runtime isolation.

## Commands and results

Canonical command, with the dedicated fixture variables set as documented:

```sh
make sync
TEST_ADMIN_URL=<dedicated-synthetic-fixture-url> TEST_DATABASE_CONFIRM=disposable make check
```

Results on the final production source state:

| Check | Result |
| --- | --- |
| Locked dependency sync | Pass |
| Ruff 0.17.2 lint / format | Pass; 102 Python files formatted |
| mypy 2.4.0 strict | Pass; 38 source files |
| Source, SQL-site, data and deployment composition | Pass |
| Exact generated OpenAPI and actual route/method allowlist | Pass |
| pytest 9.1.1 | **112 passed, 0 failed, 0 skipped**, 7.07 seconds |
| Wheel build and source/bytes/composition reconciliation | Pass |
| Separately installed wheel + actual Uvicorn HTTP | `/live` 200, `/ready` 200; runtime-only credential |
| Documented Compose bootstrap / owner migrations / wheel readiness | Pass from new marked fixture |
| Independent code/security review | Pass for restricted subset; full SEC-01 open |
| `git diff --check` | Pass |

The 112 cases include 52 database security/migration cases, 14 real runtime
lifecycle cases and the scoped test-probe driver/bind check. They test every real
revision at before-DDL, after-DDL and after-ledger interruption; exact DDL catalog
inventory; policy/grant/trigger/constraint/packaged-file mutations; all
then-present runtime-private resources; immutable rows/ownership; physical pool
PID reuse; missing/invalid/mismatched context; cancellation/rollback; retirement;
concurrent seed 90210; and forbidden packaged execution/hidden route shapes.
No missing/unfinished bootstrap test is counted as passing or skipped.

One upstream Starlette TestClient/httpx deprecation warning remains; no test or
warning was suppressed. An intermediate non-database check caught the stale
technical SQL registry while the runner was still changing. The final reviewed
registry was refreshed after removing the production fault callback, and the
complete canonical command above passed. UV warned that the local cache is
inside the source directory; exact wheel inventory confirmed it is excluded.

The Compose smoke initially found the managed workspace's restrictive file mode
prevented PostgreSQL from reading the bind-mounted fixture SQL. The file was
made world-readable (its ordinary Git checkout mode is 100644), and only the
new smoke-test volume was recreated. Bootstrap, direct-owner migration and
runtime readiness then passed. No source policy was weakened. Temporary HTTP
processes were stopped after verification.

Built wheel SHA-256:
`246f1acc7213369b11d2b87f89f696f7f42495e97441401a5a1cd93df11b65bd`.
The exact final Git revision is recorded by the linked PR/commit; baseline was
`ca7b244`. Machine-readable pytest results are generated locally at
`work/test-results.xml`; checked-in fixtures contain only synthetic DDL metadata.

## Evidence limits

The full Issue #9/ADR-008 bootstrap suite remains unimplemented because Issue #6
blocks authentication implementation. No full SEC-01 closure, product
repository/HTTP authorization, production deployment, cloud IAM separation or
independent operational verification is claimed. See the work README for the
explicit outstanding acceptance scope.
