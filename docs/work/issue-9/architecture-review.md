# Independent architecture review — Issue #9

- Reviewer: independent architecture agent (`/root/architecture_review`), not the design author.
- Date: 2026-10-22
- Material: Issue #9 design and test design, accepted ADR-005/006/008, Issue #5 reviews and test design.
- Status: pass for the explicitly incomplete foundation subset, after AR9-02 resolution.
- Scope: pre-implementation review of the explicitly incomplete executable foundation subset. This does not complete Issue #9 or close SEC-01.

## Findings

1. **AR9-01 — Authentication scope conflicts with the unfinished Issue #6 gate.** Resolved in the proposed subset. The design creates only the five denied control-plane tables and introduces neither privileged authentication functions nor an ActorContext issuer. It explicitly records ADR-008 bootstrap/provisioning evidence as missing and blocking Issue #9/SEC-01 completion. This is staged work, not a waiver or authorization to merge tenant-backed repositories before the full evidence gate.
2. **AR9-02 — Initial schema needs exact reviewed constraints before implementation.** Resolved by the reviewed initial column/constraint appendix. Catalog ancestry retains tenant/catalog/source/definition/instrument; private local foreign keys are tenant-composite; owner grants cannot activate sharing; private IDs/ownership and entry source bindings are immutable. Snapshot UPDATE/DELETE is denied by ACL and an owner-local immutable-row trigger. The explicit owner-owned, runtime-read-only `foundation.schema_revision` exception contains technical metadata only; exact checksums and the `000_security` supported upgrade fixture make readiness/recovery reviewable. No additional global/domain exception is implied.
3. **AR9-03 — Ownership/extraction coupling.** Pass. Modules own their SQL mappings and migrations. Cross-module references are opaque UUIDs, no cross-schema foreign key or ORM navigation is introduced, and any later constraint returns to the ADR-005 coupling-register review. SQLAlchemy Core is within the approved SQLAlchemy choice.
4. **AR9-04 — Application and composition boundaries.** Pass in design. Cross-module public-only edges, no private query/repository registration, no media adapter, no worker and no authentication adapter are explicit, with artifact/composition mutation checks. The technical transaction helper must not become a generic SQL handle for delivery/domain code.
5. **AR9-05 — Tenant-context architecture.** Pass in design. The two approved application roles, FORCE RLS, invoker parser, actor-derived transaction-local setting, first-statement setup/readback, physical-connection reset/retirement, and same-actor nesting preserve ADR-008. Direct GUC alteration remains the documented compromised-runtime boundary. Independent security/test reviews and real-runtime evidence are still required.
6. **AR9-06 — HTTP and client compatibility.** Pass for the issue's health-only scope. Liveness avoids database dependence; readiness checks actual connected role and migration state with bounded failures. Generated OpenAPI and route checks prohibit product behavior. No API product defaults from unaccepted ADR-010 are adopted.
7. **AR9-07 — Recovery and migration ownership.** Pass in design. Each owner-classified schema revision is transactional, failed revisions cannot be marked applied, the supported bootstrap upgrade point is explicit, and existing tenant-data transformation or RLS weakening fails closed. No third application identity, backfill mechanism or speculative infrastructure is introduced.

## Gate conclusion

No blocking architecture finding remains for this subset. Obtain the separate independent security/test-design reviews before implementing affected production code. This review approves only the already authorized foundation subset. It does not authorize authentication, product repositories/use cases, deployment, new API contracts, accepted security risks, or closure of Issue #9/SEC-01. Full ADR-008 bootstrap and then-present resource evidence remain required; Issue #16 separately proves deployed credential/IAM separation.
