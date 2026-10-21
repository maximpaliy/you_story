# Independent test-design review — Issue #8

- Review date: 2026-10-21
- Reviewer: independent test-design review agent
- Material: authorization-spec.md, test-design.md, owner decisions in README.md,
  yousician-content-schema.md, AGENTS.md and approved docs/testing/strategy.md
- Verdict: pass after focused remediation, including the initial Yousician
  source-schema test expansion

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

## Focused source-schema re-review

The prior missing-source-schema test-design blocker is resolved. The concrete
Yousician contract now supplies song author, version level 0–15, optional measured
fragment length, nonnegative note count with creation default zero, exact
replacement keys, hierarchy and published practiceability. Its note count is
explicitly numeric, not free-text notes; fragment length is independent of
practice-record duration. Unknown metadata keys remain denied.

YS-01–YS-06 provide U/H/D positive and invalid-input oracles for numeric endpoints,
null/omission/default distinctions, bool/fraction/overflow rejection, source/node
scope and hierarchy, replacement preservation, immutable historical data and
practiceability. Shared SCHEMA-01/02 supply NFC/code-point and unknown-key cases;
BINDING-01 supplies immutable source-version behavior. Existing authorization,
state/version, foreign/wrong-parent, atomic-denial and race suites apply to C03/
C04 and C18 rather than being waived by the new fields. No contradictory
accept/reject oracle was found in this focused re-review.

The proposed version/fragment practiceability and engineering bounds remain
explicitly distinguished from owner requirements. They require the separate
architecture/security and owner dispositions appropriate to the contract;
this test-design pass does not approve product choices on their behalf.

Owner review and architecture/security re-review of proposed defaults remain
separate gates. Evidence for production implementation must identify current
case counts, revisions, layers, outcomes and persisted-state checks; none has
been executed as part of this documentation review. SEC-07 remains open.
