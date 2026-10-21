# Independent architecture review — Issue #8

- Review/re-review date: 2026-10-21
- Reviewer: independent architecture-review agent; read-only review of policy
  and test materials, with this report saved separately
- Materials: authorization-spec.md, test-design.md, owner decisions in README.md;
  AGENTS.md, ADR-002/005/008 and relevant approved architecture
- Verdict: policy structure ready for owner review, with explicit source-schema
  block and proposed architecture clarifications still requiring acceptance

This is design review, not application test evidence, implementation approval or
SEC-07 closure. The source field contract is deliberately incomplete rather than
filled with invented Yousician bounds. Issue #8 must not be represented as fully
complete while its acceptance criteria require that missing contract.

## Initial findings and re-review dispositions

| ID | Severity | Initial finding | Re-review disposition |
| --- | --- | --- | --- |
| AR8-R1 | Medium | C18 lacked a consistency boundary with concurrent entry edit/move/tombstone. | Resolved at policy level. A6 requires transaction-scoped owner guards and coherent snapshot capture until commit; RACE-ENTRY specifies pre/post-transition outcomes and rejects hybrid captures. Actual lock-order/transaction proof remains implementation evidence. |
| AR8-R2 | Medium | Source-version selection and mixed-version ancestry were implicit. | Resolved as a concrete proposal. B specifies configured published default for roots, parent-version inheritance for children, immutable stored-version validation and rejection of mixed-version subtree moves. BINDING-01 exercises those choices. Owner review remains required; these were not prior approved details. |
| AR8-R3 | Medium | Retirement races had tests without a governing serialization rule. | Resolved at policy level. A6 requires authoritative state guards for characteristic assignment and statistic addition/initial capture; RACE-DEF and STAT-RACE enumerate permitted ordering outcomes. No raw cross-module table access is authorized. Runtime implementation must prove the guard protocol. |
| AR8-R4 | Medium | Exact initial source metadata contract was unspecified despite required Yousician level metadata. | Explicitly deferred and blocking affected field-contract completion. B now states C03/C04 cannot proceed without a reviewed initial source definition listing exact fields/types/bounds. Test design marks their concrete schema expansion blocked. This honest blocker is acceptable for reviewing the authorization framework, but the missing schema is not resolved and cannot support a claim that all MVP fields/tests are complete. |

## Architectural assessment

The command/query inventory, application-use-case enforcement, trusted actor
provenance, private-parent resolution, independent predicates/RLS and shared
session aggregate concurrency gate fit the approved modular monolith. Personal
customizations remain separate from source content. Retained practice history
is not reinterpreted by live catalog mutations. Deferred media/sharing/deletion/
offline capabilities remain dormant; no speculative distributed infrastructure
is required.

The immutable source-definition membership reference in section C is a reasonable
proposal for proving historical statistic eligibility without copying the whole
set into each record. It fits the accepted versioned-definition direction, but
its immutable binding, publication constraints and source-version selection must
be accepted and documented as architecture clarification before implementation.

Exact global table identities must still reconcile with ADR-008's manifest in
the database foundation; section C does not itself exempt any actual table from
RLS. Initial OIDC/session contract details remain owned by Issue #6 and must not
be silently invented under this authorization specification.

## Remaining gates

1. Supply and review the initial source-definition field contract before claiming
   complete C03/C04 schemas and corresponding tests.
2. Obtain owner review of newly proposed schemas/classifications and source
   binding/historical eligibility clarification; acceptance of the earlier
   inventory is not blanket acceptance of these added details.
3. Preserve independent security/test-design review outcomes, then implement and
   verify the policy in the owning slices. Material architecture decisions must
   be recorded under docs/architecture/decisions/ according to AGENTS.md before
   their implementation.

No new architecture defect beyond the explicitly bounded missing source contract
was found during this focused re-review. Concrete SQL, lock ordering, migrations
and runtime behavior have not been tested in this documentation-only task.
