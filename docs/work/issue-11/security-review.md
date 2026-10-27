# Independent security design review — Issue #11

Reviewer: `/root/catalog_design_review`; 2026-10-26. Independent design-only
review against baseline `4c6ac30`, Issue #8 authorization rules, ADR-008/009/012
and the proposed issue-11 documents. Status: changes requested.
No runtime tests executed, no security finding closed, no residual risk accepted.

Positive controls: public-port actor validation, explicit tenant predicates plus
FORCE RLS, exhaustive mutation allowlists, authorization before version-dependent
private errors, catalog-first locking, signed actor/filter-bound cursors, leaf
only tombstone, unchanged dormant sharing and login-only provisioning.

Blocking S11-01: The proposal assumes ADR-012 successful-form policy can be
reused on new paths. Its exception is exact-path and queryless. Native catalog
forms under no-referrer may submit opaque Origin and fail; broadly extending
same-origin to search pages can propagate personal query/cursor URLs internally.
Specify a scoped queryless-form-page exception with exact method/path/status
matrix; leave search/query/error/JSON/redirect classes no-referrer. Independently
review and obtain owner approval; prove behavior in real Chromium without
forged Origin headers or a null-Origin allowance.

Blocking S11-02: Search/cursor privacy needs an explicit deployment access-log
policy. The new GET catalog query includes names and readable authenticated
cursor payloads, while existing auth log suppression only addresses callback
URLs. Require query suppression at every enabled application/server/proxy sink;
positive-canary test those sinks and avoid recording browser blockedURI/referrer
values. Do not infer suppression from “do not add logs”.

S11-03: Complete strict request schemas and exact response definition structures
before implementation; unknown nested metadata/reference data and duplicate
keys must have concrete independent test oracles. See A11-01.

S11-04: Document cursor key rotation (old-key acceptance/expiry or immediate
invalidation), exact expiry boundary, bounded decoded input and fixed safe
failure behavior. HMAC is integrity only, not encryption or tenant authorization.

Required implementation evidence remains SEC-01/06/07 applicable negative
controls, cross-tenant/wrong-parent/mass-assignment, pool reuse, concurrency,
headers/CSRF/XSS, source-definition immutability, SQL/architecture manifest
mutation tests, and source/wheel review. No design pass can replace this evidence.

## Delta reviewed during this review

Proposed ADR-013 and CAT-13 now explicitly cover the browser amendment and
positive-canary sink evidence. S11-01/S11-02 are resolved at design level by an
explicitly proposed new privacy boundary, not by silently inheriting ADR-012.
The chosen alternative permits readable query/referrer data within the same
origin, requires suppression at every sink, and still needs explicit human
approval. Queryless form pages would reduce exposure; if retaining the selected
query-bearing design, do not imply this review accepts residual logging risk.
All mandatory sink/browser evidence remains unverified. Exact reference fields
now have a prose schema; the OpenAPI artifact remains pending (S11-03).

## Final remediation verdict

Independent re-review: **pass for design**, with human approval of the newly
explicit ADR-013 privacy/browser decision still pending. Cursor rotation,
decoded size, exact expiry, readable payload privacy and source-specific
fail-closed validation are now specified; CAT-13–16 supply the missing evidence
plan. No security-risk waiver, implementation approval before human gates,
SEC closure or production exposure is granted. Actual trigger dispatch, runtime
ACLs and every enabled logging sink require independent implementation review.

## Author-search amendment independent security review — 2026-10-26

Reviewer: `/root/author_delta_review`. Verdict: **pass for design**. The author
amendment does not add identity authority or expose global author discovery.
The required containing-song join is tenant-predicated and RLS-protected like
the selected entry; same-snapshot ancestor resolution prevents mixed-tree reads.
The normalized author filter is cursor-bound; cross-actor/filter rejection,
literal wildcard escaping and bounded inputs remain required. Author is private
catalog text and is covered by existing query/referrer/log-sink suppression and
XSS tests. No counts or unrestricted author autocomplete are introduced.

Owner approval of the full MVP contract including author search and scoped
ADR-013 has now been given. This is approval of the explicit design, not a waiver
of evidence obligations or residual security risks. Implementation security,
SQL/tenant mutation controls, real browser behavior and logging-canary evidence
remain unverified and mandatory before completion. No SEC finding is closed.
