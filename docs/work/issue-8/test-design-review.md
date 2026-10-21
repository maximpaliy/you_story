# Independent test-design review — Issue #8

- Review date: 2026-10-21
- Reviewer: independent test-design review agent
- Material: authorization-spec.md, test-design.md, owner decisions in README.md,
  AGENTS.md and approved docs/testing/strategy.md
- Verdict: pass after focused remediation for the specified authorization
  contract; initial source-specific schema expansion remains blocked

This is approval of the reviewed test-design structure and oracles, not a claim
that application tests have executed. No implementation, security closure or
owner approval of proposed architectural defaults is granted by this report.

## Findings and dispositions

| ID | Initial severity | Finding | Disposition |
| --- | --- | --- | --- |
| TDR8-R1 | Medium | Schema boundary/property coverage was implicit. | Resolved: SCHEMA-01/02/03 name normalization, exact-limit/one-over lengths, tag count/duplicates, numeric bounds, decimal precision/scale, bool-as-integer, enums, null/omission, source metadata and pagination/date boundaries. Independent model oracles and recorded property seeds/shrinking are required. |
| TDR8-R2 | High | Characteristic retirement/assignment and entry tombstone/record-creation races lacked explicit expected outcomes and policy guards. | Resolved at design level: A6 defines transaction-scoped owner guards and atomic linearization; RACE-DEF and RACE-ENTRY require both serialization orders, coherent snapshots and unchanged state on denial. RACE-CUSTOM and RACE-COUNT additionally cover active-entry customization and aggregate statistic limits. Concrete lock-order/transaction proof remains implementation evidence. |
| TDR8-R3 | Medium | Pagination ordering lacked exact collation and composite directions. | Resolved: F specifies NFC case-sensitive UTF-8 C ordering, numeric versions, UUID order, full Q03 tuple and descending Q13 components. ORDER-01 exercises case/Unicode variants, version 2/10, ties, page-size-one boundaries and cursor tuples. |

## Scope and remaining gates

The revised design covers C01–C23 and Q01–Q13 through parameterized positive,
actor, foreign/missing, parent, field, version, state, serializer and pagination
cases. Named fixtures and owner-state oracles exercise direct public use cases,
HTTP and real-runtime-role PostgreSQL; ADR-008 SQL/RLS mutations and inventories
are referenced without replacing them. Non-enumeration, dormant surfaces,
historical statistic eligibility and captured-zone behavior have named evidence.

The exact initial source metadata contract, particularly Yousician level type
and boundaries, is not defined. B explicitly blocks C03/C04, and BINDING-01
requires source-schema expansion before tests for those inputs can be regarded
as complete. This report does not waive that blocker or make the whole MVP-05
specification implementation-ready. When the source contract is supplied, its
schema-specific cases must be independently reviewed rather than inferred from
this generic pass.

Owner review and architecture/security re-review of proposed defaults remain
separate gates. Evidence for production implementation must identify current
case counts, revisions, layers, outcomes and persisted-state checks; none has
been executed as part of this documentation review. SEC-07 remains open.
