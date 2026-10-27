# Independent implementation security review — Issue #11

Reviewer: `/root/author_delta_review`; 2026-10-26. Independent of catalog
implementation authors. Reviewed uncommitted feature source on baseline
`4c6ac30`: public/application/domain catalog code, cursor/config, repository,
006 migration, delivery parsers/templates, app composition/header policy and
catalog PostgreSQL/HTTP/browser tests. No production code edited by reviewer.

Status: **changes/evidence requested**. No observed high-severity authorization,
SQL injection or CSRF bypass in reviewed source; this is not a completed
security pass and no SEC finding is closed. Findings below must be re-reviewed.

## Findings

### IS11-01 — Medium: response serialization is a blacklist

`catalog/application/service.py:_wire` currently forwards every repository dict
key except keys starting with underscore. It does not implement the approved
exact Catalog/Entry/Mutation/References returned-field allowlists. Current SQL
selects intended fields and underscore internals, so no current tenant/token
exposure was observed; however an added `tenant_id`, owner or grant field would
silently reach JSON and templates. Replace generic dict forwarding at public
boundaries with explicit serializers, including nested reference shapes, and
add poison-extra-field negative oracles. Preserve internal definition/sort data
for application use without exposing it. Root notified; remediation in progress.

### IS11-02 — High acceptance blocker: incomplete adversarial evidence

At initial review, new PostgreSQL tests primarily call the repository directly;
they cover one foreign entry read/search, missing tenant context and one shared
catalog-version race. They do not yet prove all public commands/queries against
foreign/missing/wrong-parent IDs and exhaustive immutable-field mass assignment,
or independently mutate repository predicates and RLS for new statements as
required by CAT-07/CAT-08. Existing SQL AST registration hashes detect unapproved
edits but are not runtime isolation evidence. Add direct public-port tests with
real runtime PostgreSQL, committed zero-mutation assertions and the independent
predicate/RLS negative controls. Root reports these additions are in progress.

### IS11-03 — Evidence boundary: logging and native-form policy

New browser tests correctly use real Chromium/HTTPS and production middleware,
and inspect escaping, exact response classes and cross-origin Referer absence.
The logging canary test inspects `caplog.text` only. Completion evidence must
identify every enabled application/server/proxy sink and show its actual output
or document that a sink is disabled/not present. Do not interpret one logger
helper assertion as evidence for an independently enabled proxy. ADR-013's
same-origin query referrer change is owner-approved, but that approval does not
waive mandatory suppression tests. Need final successful browser suite results
and explicit sink inventory before pass.

## Controls inspected

- Public methods validate identity-issued ActorContext; repository repeats this
  check. HTTP session comes only from existing opaque-cookie resolver. No
  caller tenant/session selector or header-based identity was added.
- Catalog/owner-grant resolution carries actor tenant predicates; entry reads,
  ancestor lookups, author joins, inserts and updates retain explicit predicates
  plus existing FORCE RLS. Bound parameters carry all caller values; interpolated
  SQL identifiers/order clauses come from fixed internal branches.
- Writes lock the catalog before authorization/version checks. Private IDs resolve
  before stale-version comparisons; move checks same source/instrument/definition
  and legal type edges. Trigger repeats ownership/graph/metadata/terminal checks
  and catalog serialization for direct runtime writes. No SECURITY DEFINER or
  new runtime role grants; fixed function search_path and revoked PUBLIC execute.
- Definitions remain immutable; generic descriptor validation is data-only,
  with no executable schema or dynamic SQL. Songsterr remains fixture-only.
- JSON parser rejects duplicate keys/nonfinite values; streamed body caps precede
  decoding; forms use closed operation-specific field sets. Existing origin,
  Fetch Metadata and session-derived CSRF checks execute before dispatch.
- Cursor integrity uses HMAC-SHA256 with domain separation, canonical base64url,
  bounded encoding/payload, actor/operation/parent/filter binding, strict expiry
  and immediate key rotation invalidation. Key is separately injected with no
  fallback. Tokens are readable/private, never authority.
- Template autoescaping, fixed local action/redirect URLs, no scripts/assets,
  nonce CSP, no-store and exact successful catalog-form policy are retained.
  Error envelopes contain fixed safe messages and correlation IDs.

## Actual verification and limits

Independent Python JSON checks of the author contract were recorded in design
review. For implementation, attempted focused domain/HTTP execution with
`UV_CACHE_DIR=work/uv-cache uv run --frozen pytest tests/test_catalog_domain.py
 tests/test_catalog_http.py -q`; emitted 35 completed-case dots then stalled at
sandbox TestClient/network boundary and was terminated. Do not count this as a
suite pass. Root owns canonical execution with the needed environment setting;
reviewer deliberately did not run destructive DB suites concurrently.

Pending: explicit serializer remediation, independent negative controls,
public-port/DB adversarial tests, actual successful browser suite, canonical
checks, migration/ACL evidence and final source delta review. No deployment,
production privacy risk acceptance, or global SEC closure is inferred.

## Remediation source delta — independent review

IS11-01 resolved in source: public response construction now uses explicit
_catalog/_entry/_references/_mutation serializers, including nested metadata,
parent rules and field descriptor keys. The poison-column test injects tenant,
owner and grant extras at multiple levels and asserts exclusion. No blacklist
serializer remains at the response boundary.

IS11-02 source remediation reviewed: new test_catalog_service_postgres.py calls
real owning public ports for foreign/missing selectors across detail/children/
ancestors/search/update/move/create-parent/tombstone, mass assignment, invalid
hierarchy/instrument/nested metadata, precondition conflicts, author move/edit,
cross-actor/filter cursors, forgery and concurrent same-version writes. New
repository tests independently remove e/p/g SQL predicates while retaining RLS,
disable RLS while preserving production predicates, prove leakage when both
layers are removed, and restore/recheck RLS in finally. Snapshot interleaving
and timeout rollback cases were also inspected. Root reports combined real
PostgreSQL suite 30 passed; reviewer did not independently rerun shared DB.

IS11-03 remains final evidence pending. Required local logging evidence is a
positive capture-control at INFO in the actual browser canary test (not a
potentially empty default WARNING capture), synthetic catalog query/Referer/
cursor records through both existing access/client filters, and explicit enabled
sink inventory. The actual local fixture sets Uvicorn access_log=False,
proxy_headers=False and log_level=error; no proxy is present, so there is no
separate proxy sink to verify in this harness. Production proxy/access logging
remains separately deployment-gated. Catalog/header/API browser completion and
canonical pass results still awaited; no premature security completion claimed.

## Final independent security and evidence verdict — 2026-10-26

Verdict: **pass for the implemented Issue #11 slice and the documented local
verification environment**. IS11-01/02/03 are resolved for that scope. No known
unresolved catalog authorization/CSRF/tenant-isolation/source-policy/serializer
finding remains from this review. This is not production deployment approval,
CI acceptance, a security-risk waiver, or global SEC-01/06/07 closure.

Independently inspected the final source/test deltas and actual evidence files,
not only the prose summary:

- Parsed `work/test-results.xml`: **736 tests, 0 failures, 0 errors, 0 skips**;
  checked catalog groups: 36 domain, 16 HTTP, 2 logging, 9 repository PostgreSQL,
  23 public-service PostgreSQL and 7 actual browser journeys, with no failed,
  skipped or errored cases in those groups.
- Read `work/canonical-check.log`: Ruff checks/formatting, strict mypy (54 source
  files), architecture/composition, OpenAPI gate and cumulative test execution
  pass; wheel build and built-wheel inventory checks pass.
- Reviewed production-service create-versus-tombstone and move-versus-tombstone
  races. They call actual owning ports on separate threads/runtime transactions,
  assert one same-CV winner and stale loser, then inspect committed public tree,
  catalog/entry versions and absence of invalid active-child/tombstone state.
- Reviewed logging test remediation: real browser capture enabled at INFO with
  safe app and uvicorn.error positive controls; actual native same-origin
  request Referer is inspected and query/cursor/name/author/referrer canaries
  are absent. Separate uvicorn.access/httpx pipeline tests attach capture without
  replacing filters, emit INFO/WARNING canaries and prove safe marker capture.
  The local sink inventory identifies disabled Uvicorn access, no forwarding/
  proxy/sidecar, captured app/error loggers, SQL echo off and parameters hidden.
  There is no untested enabled local proxy sink being represented as covered.
- Inspected isolated installed-wheel smoke script and its result. Package import
  resolves inside the separate venv rather than src; packaged migration checksum,
  strict metadata/cursor behavior, route inventory, headers and author-search
  schema are checked. Root ran the script; reviewer independently inspected its
  assertions/output and wheel digest, without rerunning destructive DB suites.

Browser qualification is explicit: Playwright runner 1.56.0 used local Chromium
151.0.7922.173 because managed policy denied pinned Chromium 141 CDN downloads.
The real local browser evidence is useful and passed, but it is not evidence
that the runner-pinned engine executed. Existing GitHub CI must verify that
engine before merge/release acceptance. No network-policy bypass or TLS
weakening is implied. Future production/server/proxy telemetry and capacity
checks remain their deployment gates; no production SLO or privacy retention
claim follows from local catalog testing.

The previously interrupted reviewer TestClient run remains honestly recorded
above and is superseded for feature evidence by the complete canonical run,
not retroactively relabelled as a reviewer pass. Source security assessment and
independent evidence examination now support this scoped final verdict.

## Pinned-browser CI oracle correction — independent delta review

Reviewed the test-only diff after root reported CI run `40250098469` on `6f`
with 735 passes and one failure. Reported observation: actual catalog-to-external
Document navigation had no Referer, while Chromium 141 additionally requested
the synthetic external site's favicon with the external site's own URL as
Referer. Reviewer inspected the source diff; the CI observation is attributed
to root, not falsely claimed as a reviewer-reproduced run.

Verdict: **pass for this test correction**. Limiting the exact `[None]` assertion
to CDP `Document` requests tests the intended catalog document navigation and
still requires exactly one observed navigation to the fixed external URL.
Every intercepted external request continues through a separate collected-header
assertion forbidding the private catalog-query canary anywhere. No production
header, route, CSRF/provenance validation or test response from the production
origin changes. A same-origin external favicon Referer containing only the
already-public synthetic external URL is not a catalog referrer leak.

This fixes an overbroad resource-type oracle, not a security control bypass or
risk waiver. The pinned Chromium CI repeat must pass before claiming that
engine's final verification. The initial failure remains recorded rather than
being treated as a successful CI run; local targeted execution alone cannot
substitute for the pending complete pinned-engine repeat.
