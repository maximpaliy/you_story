# Independent security review — Issue #9

- Reviewer: independent security-review agent (not the design/implementation author)
- Date: 2026-10-22
- Material: Issue #9 design/test-design; accepted ADR-005/006/008; Issue #5
  security and test-design records; SEC-01/05/07 project gates
- Verdict: mechanism design pass for the restricted foundation subset below;
  exact schema appendix and implementation evidence still require review

## Scope of this disposition

The proposed role, tenant parser, transaction/pool lifecycle and health-only
composition implement approved ADR-008 without providing any authentication,
product authorization or privileged bootstrap behavior. Restricting the runtime
control-plane ACLs to no access and omitting all unfinished authentication
functions preserves SEC-05's implementation gate. It does not satisfy the full
ADR-008 bootstrap requirement. Issue #9 remains incomplete and SEC-01 remains
open. No risk is accepted and no deployment or real-user-data use is approved.

The design introduces no production ActorContext issuer, tenant repository,
media adapter or product route. Synthetic fixture actors and a test-only scoped
SQL probe may establish plumbing evidence; they cannot establish working
identity validation, per-use-case authorization, or the full eventual repository
query-shape matrix. The production registry must mechanically assert absence of
those execution sites, rather than claim an empty registry proves their safety.

## Required implementation controls

1. Connect as the actual production-named app_runtime and verify session/current
   identity and restrictive role/ownership/membership attributes. A username
   string check is insufficient. HTTP must never load owner credentials, mutate
   schema or invoke migration code. Ready checks read safe schema/version and
   role metadata only and have bounded connection/statement deadlines.
2. PUBLIC and runtime receive no CREATE/TEMP or schema creation capabilities;
   owner-created default ACLs revoke PUBLIC EXECUTE before function creation.
   Runtime has no owner membership, SET ROLE reach, control-plane or media
   privileges, including effective function and sequence grants.
3. The sole runtime identity function is invoker-rights current_tenant_id, with a
   fixed safe search_path and qualified references. Missing and invalid context
   never falls back to a tenant. No security-definer function is introduced in
   this subset.
4. Every private table is non-null tenant-bearing with ENABLE/FORCE RLS and
   explicit equal USING/WITH CHECK. All within-module private parent references
   include tenant identity; cross-module UUIDs provide no authority. Exact
   table/category/owner/relationship/policy/ACL inventory must be checked against
   live PostgreSQL catalogs.
5. Transaction setup binds actor-derived context first, reads it back before
   probe/repository SQL and rejects mismatch. Reset must clear injected
   session-level context outside the tenant transaction on both checkout and
   return. Cancellation, failed transactions and reset errors must either prove
   cleanup or retire the physical connection. Same-PID A/B/missing-context
   evidence and independent fault injection are required.
6. No general execute handle is exposed to delivery/domain callers. The lack of
   a production issuer means HTTP cannot establish tenant authority in this
   subset. Future issuance, repository methods and ownership checks remain gated.
7. Health/error responses and telemetry must never include DSNs, driver error
   strings, tenant UUIDs, private content or incoming untrusted headers. Generate
   bounded correlation UUIDs on the server. Positive capture sentinels are
   required for leakage assertions so a disconnected sink cannot pass.
8. Schema revisions are owner-only, transactional, module-owned, manifest-listed
   and schema-only. No existing-tenant scan/backfill, role elevation, RLS
   weakening, dynamic migration callback or domain execution root is authorized.

## Open pre-DDL review item

The initial mechanism draft intentionally leaves exact column/constraint/ACL
shapes to an appendix. That appendix must be reviewed before database DDL is
implemented. In particular: grant shape cannot activate cross-tenant sharing;
content snapshots/global version bindings must not receive mutable runtime
privileges; digest-only identity storage must not imply acceptance of unfinished
session lifecycle; and schema metadata must not become a sixth authentication
control-plane exception. This item is a review dependency, not an accepted risk.

## Required evidence and remaining gates

The named F-01 through F-11 suites are appropriately scoped to real PostgreSQL
and require positive controls, catalog reconciliation and mutation negatives.
Owner/admin fixture results cannot replace runtime isolation evidence. Passing
unit or simple probe tests cannot close SEC-01 while TD-11 bootstrap, identity
provenance, catalog provisioning and their concurrent/failure cases are missing.

Independent review of final code and actual command/results is still required.
Deployed owner/runtime credential separation remains Issue #16 evidence.
SEC-05, SEC-07, privacy, public-exposure and supply-chain gates remain unchanged.

## Exact schema re-review

The concrete column/constraint proposal and technical-ledger exception were
reviewed after the mechanism draft. The pre-DDL review dependency above is
resolved for that proposal. The explicit owner-only five-table control plane,
read-only three-table catalog reference inventory, same-tenant composite local
keys, personal/owner-only grant checks and immutable ownership guards preserve
the restricted boundary. Immutable snapshots receive SELECT/INSERT only and an
owner-local immutable-row guard; no deletion or history-rewrite behavior is
approved. Trigger functions are invoker-rights with safe paths, no direct runtime
EXECUTE and no privileged traversal. The technical foundation.schema_revision
metadata ledger is a separately classified non-domain exception, not a sixth
control-plane table, and runtime has SELECT only. Ready verifies the exact
packaged revision/checksum set.

**Preimplementation verdict: pass for the documented restricted subset.** This
is permission to implement approved mechanisms subject to the independent
architecture/test-design reviews; it does not approve any pending human product
or security choice. Actual DDL/code/test evidence remains unreviewed. Any
implementation deviation, extra privilege, table, function, executable or API
requires renewed review. SEC-01 and Issue #9 remain incomplete.

## Implementation review checkpoint — SR9-01

**Open / blocks restricted foundation merge:** the initial migration guard
compares candidate SQL's parsed AST with the AST obtained from the same current
packaged SQL file. The runner passes that file directly, and expected checksums
are recomputed from the same source. Editing a packaged migration therefore
changes both sides together; a cross-schema DDL, RLS weakening or existing-tenant
DML change can remain accepted. Tests that only pass alternate text to the guard
would not detect this artifact mutation.

Required remediation: independently checked reviewed revision hashes and a
fail-closed semantic ownership/classification check. Mutation tests must alter
the packaged revision (with an independent manifest/hash baseline) and demonstrate
that both the reviewed artifact check and the semantic guard reject forbidden
cross-schema, RLS/privilege weakening and tenant-data statements. The mechanical
classification cannot rely on names, comments or self-comparison. Architecture
review separately tracks file-wide SQL execution-site allowlist escape paths.

## SR9-01 remediation and code re-review

**Resolved for the restricted finite migration set.** The revision map now
contains independent frozen REVIEWED_CHECKSUMS constants. Before accepting any
candidate AST, validate_migration verifies the actual packaged revision bytes
against that reviewed checksum, then requires exact parsed statement equality.
expected_revisions returns the frozen set rather than rehashing mutable files.
The changed-packaged-migration mutation changes migration_sql's packaged content
while preserving the independent checksum baseline and is rejected. Candidate
cross-schema, tenant-data DML, RLS weakening, role escalation and privileged
function additions independently fail the exact reviewed-AST allowlist.

This is a strict reviewed-statement allowlist for five known revisions, not a
general-purpose semantic migration classifier. A later revision or changed
statement requires a new independently reviewed hash/AST baseline and ownership/
classification decision; the tool must not automatically regenerate approvals.
That narrower mechanism resolves the moving-baseline defect without claiming a
permissive parser can independently approve arbitrary future SQL.

The implementation review inspected all five packaged SQL revisions, runner and
manifest, runtime configuration/context/pool code, HTTP composition/errors,
real-role migration/runtime/security tests and the full checked schema catalog
oracle. The current DDL matches the reviewed exact five-table control plane,
three reference tables, private/dormant tables and technical-ledger exception.
No security-definer function exists; the only directly executable runtime
identity function is the fixed-path invoker tenant parser. Tenant ownership,
source-version bindings and snapshots have the documented storage guards.

Runtime evidence has its own positive actor-context/PID/control-plane-denial
cases rather than using owner success as isolation evidence. The schema catalog
oracle includes policies, owners, constraints, indexes, triggers, function
configuration and ACLs and detects a sixth control table, direct runtime
control-plane grants, missing relationship/trigger, ownership changes and PUBLIC
function privilege. RLS probes deliberately omit repository predicates, while
the separate simple SQL-expression probe checks actor scope independently.
Neither is described as proof of absent production feature repositories.

**Code-review disposition: pass for the restricted foundation subset, subject
to the canonical aggregate checks succeeding and their exact results being
recorded. No unresolved subset security finding remains in reviewed code.**
This is not completion of Issue #9, SEC-01 closure, acceptance of SEC-05/07
choices, or authorization for deployment/real-user data. Missing TD-11
bootstrap/session/provisioning behavior remains a blocking acceptance gap.

## Final implementation evidence disposition

The implementation coordinator supplied the final canonical `make check`
results after removal of the production migration fault callback and refresh of
the reviewed technical SQL-site registry: lint and formatting pass (102 files),
strict typing pass (38 source files), architecture and exact generated OpenAPI
checks pass, **112 tests passed, zero failed and zero skipped**, then wheel build
and packaged-composition checks pass. The test run took 7.07 seconds and reported
one Starlette/httpx deprecation warning; the warning is not a hidden failure or
retry. Separate installed-wheel smoke evidence resolves imports from the wheel
installation and observes `/live` 200 and `/ready` 200 from actual uvicorn with
runtime-only database configuration. PostgreSQL is the disposable 17.6 fixture
with real direct app_owner migration and app_runtime isolation connections.

This reviewer inspected the relevant final implementation and test oracles; the
aggregate command counts above are the coordinator's recorded run, not a claim
that this reviewer independently reran destructive shared-database tests. The
frozen migration hashes/AST allowlist, full schema catalog oracle, RLS and ACL
negatives, pooled-context/failure retirement tests and technical-site inventory
address the reviewed subset controls. No production code changed between that
reported canonical run and this documentation-only disposition.

**Final verdict: restricted foundation implementation/evidence pass.** SR9-01 is
resolved and no unresolved security defect was identified in the implemented
subset. **Issue #9 remains incomplete and SEC-01 remains open**: the required
TD-11 authentication bootstrap/session/provisioning matrix is intentionally
unimplemented behind Issue #6's gate. No downstream feature, real-user-data or
deployment approval follows from this pass; SEC-05/07 and deployed owner/runtime
credential separation remain their respective gates. No risk is accepted.
