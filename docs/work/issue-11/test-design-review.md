# Independent test-design review — Issue #11

Reviewer: `/root/catalog_design_review`; 2026-10-26. Reviewed issue-11 proposals
against approved docs/testing/strategy.md and Issue #8 catalog test oracles.
Status: changes requested; no test execution or coverage completion claimed.

CAT-01–12 cover the major boundaries and correctly require real PostgreSQL,
separate owner/runtime identities, actual Chromium HTTPS/native forms, independent
property generators, barrier-controlled races and both tenant defenses separately.
The plan preserves canonical checks and does not invent runtime passes.

Required additions:

- T11-01: Exact native form header matrix for new queryless catalog pages, a
  preserved no-referrer matrix for query-bearing search/errors/JSON/redirects,
  actual native POST compatibility, null/cross-origin denial and no form-action
  extension to Google. Trace the scoped browser-policy amendment (A11-02/S11-01).
- T11-02: Positive-canary access-log/referrer tests for search text, cursor,
  private metadata and IDs at all enabled server/proxy/application/browser
  diagnostic sinks; inspect actual captured output, not only logging helpers.
- T11-03: Yousician v1/v2 retained-binding and changed-default fixtures are absent.
  Prove existing entries retain v1 interpretation, new roots select configured
  v2, children inherit v1, and mixed-version move fails. Defer practice snapshot
  assertions to their owning issue without omitting catalog version evolution.
- T11-04: Complete API/schema candidate first; add schema-derived negative tests
  and independent response allowlist oracles including reference payload shape,
  unknown nested keys, strict JSON booleans/integers and 428 versus 422 precedence.
- T11-05: Add coherent ancestry-read/move interleaving, cursor expiry equality,
  key rotation/invalidation, missing key startup behavior, max decoded payload,
  and DB timeout zero-partial-write tests.
- T11-06: Explain universal versus Yousician-specific database constraints and
  prove the Songsterr graph through actual persistence/contract fixture boundary
  where applicable; a policy-only mock cannot prove source-neutral storage.

After these additions, re-review the design before production implementation.
Independent implementation/security/code/evidence reviews remain required later.

## Delta reviewed during this review

CAT-13 and proposed ADR-013 now supply T11-01/T11-02 design coverage for the
chosen query-bearing same-origin exception. Update the exact matrix oracle to
ADR-013 once approved; these are design additions, not executed browser/log tests.
Exact prose reference schema is now supplied; candidate review and T11-03–06
still remain before a complete test-design pass.

Candidate check identified a concrete default-metadata schema failure: empty
song/fragment metadata is rejected by overlapping oneOf branches (A11-07).
Add independent valid-default schema examples and wrong-type metadata negatives
before claiming candidate verification; JSON parse/path-preservation alone does
not establish contract correctness.

## Final remediation verdict

Independent re-review: **pass for test design**. CAT-13–16 and clarified design
now cover T11-01–06, including definition evolution, actual fixture persistence,
coherent reads, timeouts and cursor rotation/bounds. OpenAPI overlapping metadata
union is corrected; independent schema checks exercised 11 expected-valid/invalid
creation examples, structural schemas, exact reference bounds and unchanged
baseline paths. These are design/schema checks only. No application, DB, browser,
performance or canonical-suite pass is claimed. Preserve the full planned matrix
and obtain implementation/code/security/evidence reviews after human approval.

## Author-search amendment independent test-design review — 2026-10-26

Reviewer: `/root/author_delta_review`. Verdict: **pass for test design**. The
amendment specifies song/version/fragment author resolution, missing authors,
case/Unicode/literal wildcard behavior, AND combinations, normalized input bounds,
author changes and moves between songs, changed-filter cursor rejection,
cross-tenant joins, browser escaping and log/referrer canaries. These distinguish
name-match OR author-match from the separate AND author-filter semantics. Tests
must include a foreign song with the same author and prove none of its IDs/names
enter search results. Parent author edits/moves must affect subsequent fresh
queries without copying metadata or claiming a snapshot across page requests.

Independently parsed candidate JSON and asserted author parameter maxLength 200
and general-text containing-song-author description. These are design checks,
not an executed HTTP, PostgreSQL or browser suite. Owner approved the full MVP
proposal after author-search discussion; no further approval is required for this
unchanged delta. Actual implementation evidence and independent code/security
review remain outstanding.
