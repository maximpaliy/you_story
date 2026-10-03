# GitHub Issue #5 — Fail-closed PostgreSQL tenant isolation

## Current status

Issue #5 (`MVP-02`) started after approval of the first-increment test strategy.
ADR-008 defines the accepted roles, grants, RLS/context lifecycle, pool reset,
worker absence, schema-migration boundary, future privileged-data-migration
gate, explicit repository tenant predicates, observability and evidence needed
for the SEC-01 pre-implementation gate.

The design, independent architecture/security/test reviews and human approval
are complete. Tenant-backed repository implementation remains in Issue #9 and
must satisfy the accepted evidence and re-review gates.

## Deliverables

- `docs/architecture/decisions/008-fail-closed-postgresql-tenant-context.md`
- `docs/work/issue-5/test-design.md`
- independent architecture, security and test-design review records
- `docs/work/issue-5/status.yaml`

## Completion evidence

- **Changed:** Proposed the fail-closed tenant-isolation implementation design.
- **Verified:** Independent architecture, security and test-design reviews passed
  after their findings were resolved.
- **Unresolved:** SEC-01 implementation evidence and re-review in Issue #9;
  deployed owner/runtime credential separation in Issue #16; SEC-05 and SEC-07.
- **Security review:** SEC-01 remains open and blocks tenant-backed repositories.
- **Production implementation:** Not started or authorized.
