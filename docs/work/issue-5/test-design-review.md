# Independent test-design review — GitHub Issue #5

- **Latest review date:** 2026-10-03
- **Material:** Two-role ADR-008 plus explicit repository tenant scoping and
  Issue #5 test design
- **Verdict:** Pass after documentation consistency corrections

## Findings and dispositions

1. **Runtime/owner separation could be asserted only logically.** TD-01, TD-06,
   TD-08 and TD-11 now require direct/transitive role denial, credential/profile
   separation, owner-only migration execution, runtime reconnection for
   postconditions, and tracked platform proof.
2. **A privileged tenant-data migration could enter as an ordinary migration.**
   TD-08 requires a checked classification manifest and fails CI for owner-
   privileged access to existing tenant rows, weakened RLS, generic all-tenant
   functions or temporary runtime elevation until a new reviewed design exists.
3. **Migration evidence could miss actual changes.** Empty-to-head and every
   supported fixture exercise each real migration with failure/recovery and
   post-migration catalog checks; synthetic fixtures cannot substitute.
4. **Earlier false-pass findings remain resolved.** Canonical non-enumeration
   positive controls, catalog/authorization inventory reconciliation, policy and
   relationship mutations, physical backend reuse, worker/composition absence,
   bootstrap/session ACLs and telemetry sentinels remain required.
5. **Review records described the superseded role model.** Resolved by independent
   re-review and replacement of the stale migrator/grant conclusions.
6. **The generated-SQL oracle was underspecified.** Resolved by capturing the
   final statement/binds before driver execution and requiring a PostgreSQL-aware
   AST or ORM expression-tree oracle; regex, substring and `EXPLAIN` are rejected.
7. **Complex reads and writes could escape scoping.** Resolved with every private
   alias/range variable anchored to the actor bind across CTE/subquery/set/loader/
   aggregate shapes, full insert/upsert/update/delete/cascade coverage, tenant-
   bound cursors, and positive/negative mutations.
8. **Query inventory could be incomplete.** Resolved with a checked statement-
   site registry reconciled to repository methods, ORM factories and raw/text SQL
   sites; unregistered variants or missing executable tests fail CI.
9. **Catalog provisioning could be interpreted as per-request work and lacked
   race evidence.** Resolved by distinguishing first/pending login callbacks from
   side-effect-free session/ready requests; testing atomic catalog/grant rollback,
   concurrent callbacks, failed ready updates, forged transitions, disabled
   lifecycle state, response equivalence and absence of an HTTP retry endpoint or
   middleware/worker/CLI/scheduler trigger.

## Conclusion

The revised design would fail when runtime can obtain owner authority, an MVP
migration attempts privileged tenant-data work, RLS is weakened, tenant context
bleeds across a pool, a child/join omits tenant scope, or an observable
non-enumeration difference appears. This approves test design only; SEC-01 still
requires Issue #9 implementation evidence and independent security re-review.
