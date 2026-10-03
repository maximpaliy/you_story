# Independent security review — GitHub Issue #5

- **Latest review date:** 2026-10-03
- **Material:** Two-role ADR-008 plus explicit repository tenant scoping and
  Issue #5 test design
- **Verdict:** Pass
- **Scope:** SEC-01 design portion only; implementation evidence remains open

## Security assessment

1. `app_runtime` is non-superuser, non-owner and `NOBYPASSRLS NOINHERIT`; it has
   no owner membership, `SET ROLE`, schema creation, temporary-object, policy-
   management or unapproved function access.
2. `app_owner` is available only to the controlled migration/deployment process.
   The application cannot obtain its credential or authenticate/assume it.
3. FORCE RLS applies to ordinary owner-issued tenant queries but cannot prevent an
   object owner from altering policies. The design correctly treats operational
   owner/runtime credential separation, reviewed migrations and post-migration
   catalog assertions—not FORCE RLS alone—as the control for that privilege.
4. The five-table pre-authentication control plane remains deny-by-default to
   runtime except for fixed-path, schema-qualified, least-result security-definer
   functions with exact execute grants and mutation-tested contracts.
5. Removing the separate migrator and temporary grant/revoke choreography creates
   no gap because the MVP has no requirement to traverse or mutate existing
   tenant-private data with privilege.
6. TD-08 blocks any such migration, RLS weakening, generic all-tenant function or
   temporary runtime elevation until a new architecture, security and test-design
   review is approved.
7. Normal private repository statements independently bind every private table
   occurrence to the typed `ActorContext` tenant. FORCE RLS remains a separate
   database enforcement layer; mutation tests prevent either layer from masking
   absence of the other.
8. Joins, loaders, subqueries, aggregates, writes, cursors and bulk operations are
   covered by a reconciled statement registry and semantic pre-driver oracle.
   Raw SQL, registry omissions and request-derived tenant binds fail closed.
9. Future sharing replaces affected owner predicates with reviewed ActorContext-
   derived grant/authorized-scope predicates mirrored in grant-aware RLS and
   use-case authorization; it cannot merely remove explicit scoping.
10. Catalog provisioning is not a per-request side effect. Catalog plus owner
    grant commit atomically; the internal ready transition derives its target
    from `ActorContext`, is monotonic and active-state guarded, and follows only a
    typed catalog success. Concurrent pending logins converge without exposing
    uniqueness errors or whether catalog commit preceded the ready update.

## Future privileged data migrations

A future migration that reads or changes existing tenant-private rows is a new
security-sensitive work item even if described as a small transformation. Its
design must cover scope, backup, reconciliation, idempotency, interruption,
repair, audit, RLS behavior and proof that runtime never receives owner access.
No mechanism or risk is accepted in advance.

## Conclusion

No blocking or material security finding remains in the two-role design. This
passes the SEC-01 design portion only. SEC-01 remains open until Issue #9
implements the design against real PostgreSQL and passes independent security
re-review. Issue #16 must separately prove deployed credential/IAM separation;
local role assertions do not establish that production control. SEC-05 and
SEC-07 remain separate gates.
