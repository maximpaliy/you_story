# Independent architecture review — Issue #8

- Latest focused review: 2026-10-21
- Reviewer: independent architecture-review agent
- Materials: authorization-spec.md, yousician-content-schema.md, test-design.md,
  README.md; AGENTS.md, ADR-002/005/008/010 and relevant approved architecture
- Verdict: pass for the specified MVP authorization design after remediation

This review evaluates design, not application behavior or executed test results.
It does not close SEC-07's implementation-evidence gate or authorize production
deployment. Owner approval is recorded separately by the lead; this reviewer
cannot supply it on the owner's behalf.

## Findings and final dispositions

| ID | Severity | Initial finding | Final disposition |
| --- | --- | --- | --- |
| AR8-R1 | Medium | Record creation lacked a consistency boundary with entry edit/move/tombstone. | Resolved. A6 requires transaction-scoped owner guards and coherent snapshot capture until commit; RACE-ENTRY specifies pre/post-transition outcomes and rejects hybrid captures. Actual lock-order/transaction proof remains implementation evidence. |
| AR8-R2 | Medium | Source-version selection and mixed-version ancestry were implicit. | Resolved. B specifies configured published default for roots, parent-version inheritance for children, immutable stored-version validation and rejection of mixed-version subtree moves. BINDING-01 exercises these rules. |
| AR8-R3 | Medium | Definition retirement races lacked a governing serialization rule. | Resolved. A6 requires authoritative state guards for characteristic assignment and statistic addition/initial capture; RACE-DEF and STAT-RACE enumerate valid ordering outcomes. Owner public ports do not permit raw cross-module table access. |
| AR8-R4 | Medium | Initial source metadata lacked exact fields/types/bounds, particularly Yousician level. | Resolved in focused review. yousician-content-schema.md defines exact per-node keys, hierarchy, optional author, level 0–15, nullable measured fragment length, creation-default zero note count, integer bounds and full-replacement rules. YS-01–YS-06 replace the former schema placeholder. No missing-source-schema block remains in this specification. |

## Source contract assessment

The concrete schema preserves Song -> Version -> Fragment while treating author
as song metadata rather than adding a new parent/entity. A fragment's unknown
measured length is represented by null, never inferred from practice duration.
An initial zero note count is explicitly not evidence of zero musical notes.
Replacement requires explicit keys so omitted measurement/count fields cannot
silently erase values or reset them to creation defaults. These distinctions
are adequately bounded for the MVP and introduce no hierarchy or authorization
bypass.

Initial practiceability is configured as version/fragment, with song serving as
navigation/grouping. This does not conflict with approved architecture/ADR-002,
which delegate practiceable node types to the source definition; the approved
product definition requires recording against the Yousician catalog but does
not mandate that song nodes themselves are practiceable. It remains an explicit
engineering policy default rather than a retrospective claim of earlier owner
instruction. Published-policy enforcement and the named song-denial/positive
version-fragment cases make the behavior reviewable. Future changes must follow
the immutable source-version rules rather than silently reinterpret old records.

Optional author and representational numeric bounds are conservative concrete
validation defaults, not claims about upstream Yousician maxima. No author or
fragment measurement field is newly copied into historical snapshots; the
accepted minimal snapshot remains unchanged. There is no need for additional
media, author-identity, bulk-create or future-content architecture in this issue.

## Overall architecture assessment

The command/query inventory, owning-use-case authorization, trusted actor
provenance, private-parent resolution, independent predicates/RLS and shared
session aggregate concurrency gate fit the approved modular monolith. Personal
customizations stay private and separate from source catalog data. Historical
statistic eligibility is established by immutable source-definition membership,
not today's live catalog state. The owner public-port/unit-of-work guard contract
preserves module boundaries while making concurrent checks meaningful.

Actual global table identities must reconcile with ADR-008's reviewed manifest
in the database foundation. Initial OIDC/session wire behavior remains owned by
Issue #6. Those are explicit implementation/integration dependencies rather than
new unresolved product decisions inside this authorization matrix.

## Documentation synchronization before issue closure

README.md, ADR-010 and status.yaml still contained earlier missing-schema and
pending-review wording at the time of this focused read. The lead should update
those dispositions to match the reviewed source contract and separately recorded
owner decision. This is a durable-record consistency task, not an additional
architecture decision or a request for repeated owner approval.

No architecture closure blocker remains in the reviewed contract itself. Later
implementation must still prove its transaction/lock ordering, database role
separation, query/table manifests, runtime authorization and adversarial cases.
No application, SQL or browser test was executed by this review.
