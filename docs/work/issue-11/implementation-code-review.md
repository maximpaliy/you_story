# Independent implementation code and evidence review — Issue #11

Reviewer: `/root/catalog_code_review`, 2026-10-26. Independent from all catalog
implementation authors. Reviewed source on disk against baseline `4c6ac30`,
approved issue-11 design/HTTP/test plan and author-search amendment. Separate
security review is recorded elsewhere. No destructive database suite run by this
reviewer; root owns sequential verification.

Status: final pass after remediation; initial findings and staged verdicts below
are retained as review history. Pinned-engine CI verification remains qualified
explicitly in the final verdict.

## Findings

- **C11-01 — HTML children beyond the first 100 were unreachable from detail.**
  `entry_page` requested only the first child page and discarded its cursor.
  Remediation observed during review: detail now explicitly labels truncation
  and links to the existing paginated ancestor search, and a focused HTTP test
  proves the navigation and continuation link. This resolves the product-access
  defect without adding a new route or unbounded response. Final executed test
  result remains part of root verification.
- **C11-02 — Required adversarial implementation evidence incomplete.** Initial
  PostgreSQL tests exercise repository writes, with a race manually reproducing
  a version check rather than calling the production CatalogService. Before
  issue completion, add actual service/database and production HTTP evidence for
  cross-tenant/IDOR mutations, mass assignment, stale CV/EV checks, same-version
  concurrent commands, create/move-versus-tombstone serialization, independent
  predicate/RLS mutation controls, repeatable-read ancestry interleaving and
  timeout rollback. Planned CAT-06/07/08/16 cases are not satisfied merely by
  passing the initial six repository tests. Exact response-field allowlists and
  installed-wheel/compatibility checks also need concrete execution evidence.
- **C11-03 — OpenAPI exact-route gate mishandles multiple methods.** The initial
  updated expected inventory grouped methods per path, while delivery registers
  individual APIRoutes, breaking the length assertion. `expected_paths` also
  selected only `next(iter(methods))`, losing allowed methods. Normalize the
  runtime method inventory without weakening rejection of extra, duplicate,
  hidden or unapproved routes; compare all schema methods. Final re-review
  pending remediation.

## Positive findings and boundaries

Catalog-first locking keeps public hierarchy writes serialized; parent and target
resources resolve under actor predicates before stale version-dependent domain
errors. Read repository transactions use READ ONLY REPEATABLE READ. Search uses
parameterized literal ILIKE filters, fixed bounded ancestry joins and stable
C-collation/name or creation-time/UUID keysets. Author lookup follows the current
song in the same snapshot rather than copying author into children. Cursor
bindings include normalized filter digest, actor, operation and parent; tokens
have integrity, expiry and encoded/decoded bounds.

Migration 006 is additive; applied migrations are unchanged. Source-specific
metadata rules dispatch through retained immutable definitions, and the fixture
seam is not exposed as a Songsterr product workflow. Native forms use escaped
closed controls and no unsafe HTML or arbitrary metadata editor. The current
wire adapter removes internal underscore-prefixed fields; exact returned-field
tests are needed to guard this boundary against future repository additions.

This review does not approve deployment, close security findings, or treat
planned tests as executed evidence. Re-review the remediated source and final
canonical results before changing this verdict.

## Remediation delta review

Independently re-read service serializers, production SQL/store tests, public
service integration tests, real JSON browser journey and route gate. Explicit
catalog/entry/reference projections now replace the permissive prefix filter;
a poisoned repository test independently verifies extra private fields are dropped.
The route gate now compares exact per-method Counters and all OpenAPI methods,
retaining rejection of duplicate/hidden/extra routes. **C11-03 resolved.**

Reviewer execution (non-destructive):

- `.venv/bin/pytest tests/test_catalog_domain.py tests/test_openapi_gate.py -q`:
  **40 passed**.
- Independently parsed `contract()` output and compared every baseline `4c6ac30`
  path contract for exact JSON equality: **pass**. Both GET/POST entries and
  GET/PATCH detail methods retained: **pass**.

CAT-08 now has independent production-query predicate removal and owner-controlled
RLS disabling, plus the essential positive control proving leakage when both
layers are removed and verified restoration afterward. CAT-16 snapshot/move and
lock-timeout rollback tests are substantive. Public service cases now cover
foreign/missing selectors, immutable-field mass assignment, hierarchy/scope,
CV/EV checks, author changes, cursor binding and same-CV concurrent creates.
Root reports **30 PostgreSQL service/repository tests passed**; this reviewer
inspected their source and did not rerun the shared destructive database suites.

C11-02 is substantially remediated but still requires the explicitly planned
create-versus-tombstone and move-versus-tombstone production-service races,
plus root's final real JSON/browser and canonical/installed-wheel evidence.
Do not infer these passes from the generic same-CV create race. No further
production logic defect was identified in this remediation delta. Final review
verdict remains pending that evidence and current-status documentation cleanup.

## Final independent code/evidence verdict

**Pass after remediation for the implemented slice and the documented local
verification environment.** No unresolved code-review blocker remains.

Reviewed the default migration runner delta (`005_identity` -> `006_catalog`)
and exact SQL registration refresh. Default migration now reaches the additive
catalog revision; explicit historical upgrade targets remain supported. Reviewed
the two added production-service barrier races: create versus parent tombstone,
and move versus destination tombstone. Both inspect committed current catalog,
entry versions and child membership, require one valid winner and a stale
loser, and prove no active child under a tombstone. **C11-02 resolved** with the
new source and evidence; this does not imply every conceivable interleaving was
exhaustively tested.

Independently inspected retained artifacts rather than relying only on the
reported total:

- `work/test-results.xml`: **736 tests, 0 failures, 0 errors, 0 skips**; both
  requested tombstone races and the actual JSON cross-tenant browser test are
  present and passed.
- `work/canonical-check.log`: Ruff, formatting, strict mypy (54 source files),
  architecture/composition/SQL registration, OpenAPI regeneration, complete
  pytest, wheel build and wheel inventory/composition checks all passed.
- All **7 catalog browser journeys** appear in the canonical run, alongside
  existing authentication journeys. The 23 public-service PostgreSQL tests and
  9 repository PostgreSQL tests ran cumulatively, without skipped DB evidence.
- Built-wheel SHA256 independently recomputed as
  `427a654d31556a4034a82344338088c1382689b3b86de059125983f156304404`, matching
  verification.md. Isolated installed-wheel script and results resolve imports
  under the separate site-packages environment and check packaged migration,
  cursor/metadata, route and author-schema boundaries.
- Logging tests include a captured safe positive marker and actual sensitive
  records through the installed Uvicorn/httpx filters; the corrected metadata-
  only response expectation is 503. Browser canary evidence has the local sink
  boundaries explicitly documented.

The reviewer did not rerun the shared destructive DB suites. Independent earlier
execution of 40 domain/OpenAPI tests and baseline-contract comparisons is
recorded above; final complete-run evidence was independently inspected.

### Qualification and remaining release gates

The actual local engine was **Chromium 151.0.7922.173**, selected explicitly by
TEST_CHROMIUM_PATH. The Playwright-pinned Chromium 141 download was blocked by
managed network policy. This review **does not claim pinned-engine execution
passed**. Existing CI must independently verify its pinned engine; a different
browser failure must be fixed, not silently ignored. This is a transparent
verification limit, not a production deployment or compatibility waiver.

The implementation security review remains a separate required verdict. No
production deployment, capacity/SLO approval, global security-finding closure,
real Google registration, or unconfigured proxy log verification follows from
this code-review pass. Final status documentation should reflect these exact
local passes and remaining CI/deployment boundaries.
