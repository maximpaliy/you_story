# Independent code review — Issue #9

Date: 2026-10-22. Final disposition: **pass for the implemented foundation subset**.
All CR9-A1 through CR9-A4 findings are resolved. The complete Issue #9 remains
in progress; no SEC-01 closure or deployment authorization is implied. Database
security evidence has its separate independent review.

## Architecture/build review — initial findings

Reviewer: independent architecture agent `/root/architecture_review`.
Material: `tools/check_architecture.py`, `check_artifact.py`, `export_openapi.py`,
architecture/artifact tests, `pyproject.toml`, Makefile and foundation CI.
Initial disposition: changes required. Initial probes used Python 3.12 stdlib,
not database evidence. Full dependency execution was unavailable in the reviewer
sandbox; the parent owns the complete check run.

1. **CR9-A1 (blocking): architecture checks accept prohibited shapes.** Concrete
   calls to `check_source` returned no error for variable/default-schema Table
   mappings; aliasing `connection.execute`; `threading.Thread(target=handler)`;
   an aliased `asyncio.create_task`; dynamic imports of private infrastructure;
   and ActorContext construction through an import alias. The plan promises
   fail-closed mapping, statement-site, composition and issuer checks, so the
   obvious-name mutation tests are insufficient. Require a fail-closed narrow
   source/composition inventory for this empty-module subset, and resolve aliases
   or reject unsupported execution/mapping/import forms. Add each example as a
   negative mutation plus valid baselines. Do not describe heuristic name checks
   as exhaustive proof of arbitrary Python behavior.
2. **CR9-A2 (blocking): built artifact reconciliation is incomplete.** The wheel
   checker accepts arbitrary non-Python package payloads (`.so`, `.pth`, shell
   code), does not verify the packaged composition manifest, and can pass a wheel
   missing required migrations/runtime files. Reconcile exact allowed packaged
   files and their bytes against the approved source/package manifest; reject
   unclassified executable/data payloads and inspect the artifact's composition.
   Deployment commands/Compose/Docker roots also need reconciliation once added.
3. **CR9-A3 (blocking until covered): OpenAPI alone does not establish route
   absence.** A route with `include_in_schema=False` is invisible to the initial
   contract exporter. Compare actual route/method registrations with the two
   approved GETs in addition to generated schema. Hidden-media and method
   mutations are already being added and must pass the final run.
4. **CR9-A4 (minor): local Makefile commands rely on an unwritable default uv
   cache.** `sync` sets UV_CACHE_DIR for only its own command, while `check`,
   `unit`, `openapi` and `format` do not inherit it. The reviewer observed uv fail
   at `/home/agent/.cache/uv/CACHEDIR.TAG`. Export the documented workspace cache
   for all Make targets or document/pass it consistently. CI already supplies it.

## Required final disposition

Resolve the findings, run positive and mutation controls on the actual source
and built wheel, then record the reviewed revision/diff and exact command/results.
Separate runtime/database security/code reviews remain necessary. Missing
ADR-008 bootstrap/provisioning evidence remains an acceptance gap regardless of
this checker review's final result.

## Architecture/build re-review

Reviewer: `/root/architecture_review`, 2026-10-22.

CR9-A1 is resolved structurally: the restricted empty-module inventory rejects
unregistered behavior; mapping/import/actor aliases and common worker/process
facilities have negative controls; technical SQL registration records complete
call ASTs, sensitive attribute references and enclosing function bodies with
multiplicity. This catches alias extraction, new statements and altered binds
rather than exempting whole technical files. This is a narrow foundation guard,
not a claim that static analysis proves arbitrary Python safe.

CR9-A2 is resolved structurally: the built wheel is reconciled to source file
bytes, its composition is inspected, unknown archive paths/payloads and entry
points are rejected, and packaged SQL/JSON paths are declared. The reviewed
Compose/CI descriptor inventory and frozen hashes reject added or changed
execution descriptors. The current Compose file contains only the disposable
PostgreSQL fixture; the HTTP and dedicated owner-migration processes are the
only documented application roots.

CR9-A3 is resolved: the contract exporter compares actual registered routes and
methods, including hidden routes, before comparing generated OpenAPI. CR9-A4 is
resolved by exporting the workspace uv cache for every Make target.

The reviewer additionally inspected the complete health app, runtime settings,
immutable actor contract, primitives, transaction/pool helper, migration
manifest/runner/entry point and owner-scoped schema layout. No additional
non-security correctness blocker was identified. Database security assessment
and PostgreSQL evidence remain the independent security review's responsibility.
The runner authenticates directly as owner, serializes migrations, validates the
ledger prefix/checksums, applies each revision transactionally and unlocks on
failure. No product repository, issuer or deferred behavior is registered.

Review execution: the focused architecture/artifact/OpenAPI suite passed 34 tests.
An expanded ASGI/runtime run outside the restricted sandbox passed 43 tests and
caught one stale migration-runner SQL-registry baseline after a concurrent edit;
that failing guard is evidence of detection, not an accepted final state. The
restricted-sandbox ASGI run was stopped after its local test client stalled;
normal execution completed in 0.50s. The registry was subsequently frozen after removal of the test-only migration
callback and the final checks below passed.


## Final independent disposition

**Pass for the implemented, explicitly incomplete foundation subset.** No
blocking code-review finding remains. The final runner has no callback parameter
or domain callback path; interruption tests instrument the test harness instead.

Independent final checks on the frozen source:

- `work/venv/bin/python -m tools.check_architecture`: passed.
- `work/venv/bin/python -m tools.check_artifact`: passed against the actual built wheel.
- `work/venv/bin/python -m pytest tests/test_architecture.py tests/test_artifact.py tests/test_openapi_gate.py tests/test_http.py tests/test_runtime.py -q`: **44 passed, 0 failed, 0 skipped** in 0.46s. One upstream Starlette/httpx deprecation warning remains informational.

The implementation owner separately reported the canonical `make check` passing
ruff, formatting (102 files), strict mypy (38 source files), architecture, exact
OpenAPI, **112 tests passed, 0 failed, 0 skipped**, wheel build and wheel
composition. The owner also reported successful installed-wheel `/live` and
`/ready` HTTP smoke checks with only the runtime DSN. These full PostgreSQL and
installed-wheel results are owner execution evidence; this reviewer did not
independently rerun the destructive database suite.

Final reviewed source fingerprints:

- `shared/database.py`: `1e567763a62fc71c414e3b82267a373165c5759a1e3067f5d478334be4ea42ff`
- `migrations/runner.py`: `e44a986199be7690b2b2573e1ebde2b5f464a250c0a38fc936e9d96b821bcdab`
- `tools/check_architecture.py`: `86e4aadaa80d5fadd092ad56b3d722ec49e01a6a860792dee3543c4ad883a51d`
- `tools/check_artifact.py`: `f9e6d298d597cf97fa9c835cc9443214edea07603d4126d954b0cadec22d26fd`

Issue #6's authentication gate, ADR-008 bootstrap/provisioning functionality and
its full evidence, then-present product authorization evidence, and Issue #16
deployed credential separation remain unresolved as recorded in the work
README/security review. This code-review pass does not waive them or complete
Issue #9.

## CI health-command quoting correction

Independent reviewer: `/root/architecture_review`, 2026-10-22. **Pass.**
Reviewed the two-line implementation diff after the PR's container-initialization
failure: the GitHub Actions service health command now uses double quotes so the
runner preserves `pg_isready -U postgres -d you_story_issue9_test` as one Docker
option value. Its frozen deployment-descriptor checksum was updated to the exact
independently verified SHA-256
`1ceff4b0f7e16ff99f369afd758184c32fc3d733b3122886cf33d99ba57dc928`.
No health arguments, checks, grants, test scopes or application behavior changed.
Independent architecture checks and all 30 architecture tests passed. Remote CI
must still pass on this corrected revision before merge; local checks do not
substitute for successful service initialization in GitHub Actions.
