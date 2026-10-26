# Independent architecture review — Issue #11

Reviewer: `/root/catalog_design_review`, independent reviewer agent; 2026-10-26.
Reviewed baseline `4c6ac30`, issue-11 design/HTTP/test proposals, AGENTS.md,
ADR-002/005/010/012, Issue #8 catalog policy and approved test strategy.
Status: changes requested; design review only, no implementation approval.

The proposed vertical slice preserves module ownership, login-only provisioning,
actor-derived authority, versioned source policy, dormant grants, catalog-wide
concurrency and bounded navigation. Restricting the product source to Yousician
while exercising Songsterr only through fixtures is consistent with the backlog.
No new deployment or technology is required.

Blocking findings:

- A11-01: HTTP references response contains unnamed `types,parent_rules,
  metadata_rules` structures and explicitly defers their concrete definition.
  There is no OpenAPI candidate. Complete every public field type, bound,
  required/null/default rule and error/status mapping in a reviewable candidate
  before asking the owner to approve an “exact” contract.
- A11-02: Reusing ADR-012 does not authorize catalog-form header exceptions.
  That ADR enumerates exact paths and prohibits query-bearing native form pages.
  Specify a scoped amendment for new form pages, preserve no-referrer for search
  pages containing private queries, and obtain owner approval of that amendment.
- A11-03: The fixed three-level migration/ancestry wording does not explain how
  the same storage/policy seam admits structurally different fixture graphs.
  Specify which constraints are universal versus definition-specific, and
  ensure the migration does not hardcode Yousician as the storage model.

Clarifications to settle before implementation:

- A11-04: Define repeatable/coherent ancestry read semantics under concurrent
  moves; one default READ COMMITTED transaction alone is not one snapshot.
- A11-05: Cursor claims include user/tenant IDs and private names. HMAC authenticates
  but does not encrypt; document that encoding is readable, ensure cursors cannot
  enter access logs/referrers, and define signing-key rotation behavior.
- A11-06: Catalog aggregate ETag on an entry mutation is a deliberate custom
  precondition convention. Keep explicit client documentation and test that an
  entry GET ETag cannot satisfy it. Do not describe it as a representation hash.

After remediation, independently re-review deltas. Existing ADR-010 scoped
engineering defaults and human API approval are still separate pending gates.

## Delta reviewed during this review

The appended exact reference-definition representation resolves the unnamed
reference structures in A11-01 at prose level. The machine-readable candidate
is still pending and must match it before exact-contract approval.
Proposed ADR-013 now explicitly identifies the new browser-policy decision,
exact route/status matrix and query referrer privacy implications. A11-02 is
resolved as an undeclared-policy-change finding; approval of ADR-013 remains a
human gate. It deliberately extends beyond queryless pages and must not be
represented as unchanged ADR-012 policy. A11-03–05 remain clarification work.

## Candidate review

The newly added OpenAPI candidate preserves baseline path definitions and adds
10 catalog JSON operations; HTML remains specified by the normative route table.
A11-07 (blocking): CatalogCreate.metadata uses oneOf with two optional-field
object schemas. Valid song `{}` and fragment `{}` match both and are rejected.
Confirmed using installed jsonschema Draft202012Validator; version `{level:0}`
and song `{author:null}` pass. Use an unambiguous outer type discriminator or
anyOf plus the existing entry_type conditional. Exact-count reference arrays
also need minItems alongside maxItems to match prose. These checks are schema
analysis only, not API/runtime execution.

## Final remediation verdict

Independent re-review: **pass for design**, subject to explicit owner approval
of the HTTP contract, scoped ADR-010 catalog defaults and proposed ADR-013.
The storage/read/cursor clarification distinguishes universal from dispatched
source-specific constraints, uses repeatable-read snapshots for multi-statement
ancestry, and specifies readable cursor handling, byte bounds, expiry equality
and immediate key-rotation invalidation. These resolve A11-03–05 at design level.
A11-06 remains explicit client documentation, not an implementation blocker.

A11-07 is fixed: create metadata now uses anyOf with entry_type conditionals.
Independent Draft202012Validator checks confirmed all candidate component schemas
are structurally valid, baseline paths are unchanged, exact reference array
bounds match prose, and 11 valid/invalid create examples match their independent
oracles (including song/fragment empty metadata, boolean integers and cross-type
metadata). No HTTP/runtime/PostgreSQL execution is implied. Review the actual
trigger dispatch and SQL safety during implementation; this pass does not approve
unreviewed dynamic policy execution or exempt manifests/constraints from tests.

## Author-search amendment independent review — 2026-10-26

Reviewer: `/root/author_delta_review`, independent review of the author-search
changes in design.md, http-contract.md, test-design.md and openapi.candidate.json.
Verdict: **pass for design**. General text matches entry name OR containing-song
author; separate author filter ANDs with remaining filters. Songs use their own
metadata; versions/fragments resolve authorized song ancestry in the same read
snapshot. This preserves source metadata ownership without denormalized copies
or a new author entity. Ordering and pagination remain stable by entry name/UUID;
normalized author participates in cursor binding. Null/empty semantics and input
bounds are explicit. Candidate parameter names and 200-character author bound
were independently checked with Python JSON parsing. No implementation examined.

The owner subsequently approved the complete MVP proposal including author search:
“Great, looks good for MVP, approved”. This resolves the pending owner contract,
scoped catalog-default and ADR-013 decisions for this slice; unrelated ADR-010
policies and production deployment remain outside that approval.
