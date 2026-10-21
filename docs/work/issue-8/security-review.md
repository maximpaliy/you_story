# Independent security review — Issue #8

- Review date: 2026-10-21
- Reviewer: independent security-review agent
- Material: authorization-spec.md, test-design.md and the minimal Yousician
  content contract, reconciled against owner
  decisions, SEC-07, AGENTS.md and ADR-008/009
- Verdict: pass after remediation for the authorization design, including the
  initial Yousician source-contract expansion; implementation evidence remains gated

This is a document/design review, not runtime security evidence or owner approval
of proposed defaults. No security risk is accepted and SEC-07 is not closed.

## Findings and dispositions

### SR8-R1 — Authorization-state races (Medium, resolved in design)

The initial A5 protected session/catalog mutations but did not establish protected
check-and-use of another resource's mutable authorization state. Assignment versus
characteristic retirement, record creation versus entry changes/tombstoning,
statistic addition versus retirement and customization versus tombstoning could
otherwise pass an unlocked precheck before a conflicting commit.

A6 now requires one unit of work, transaction-scoped owner-port guards,
lock/recheck or equivalent serializable detection, consistent documented lock
ordering and atomic failure. It defines permitted linearization outcomes without
authorizing cross-module table access. Test design adds RACE-DEF, RACE-ENTRY and
RACE-CUSTOM alongside STAT-RACE, with both orders and coherent snapshot oracles.
Concrete transaction, lock-order and cancellation/deadlock behavior still require
implementation evidence; no such proof is claimed by this review.

### SR8-R2 — Creation-only statistic count bound (Medium, resolved in design)

The initial C18 creation limit could be bypassed by repeated C20 additions, while
record queries return all statistic values. Section B now gives both commands a
shared aggregate limit of 100, one per definition, protected by session/record
concurrency checks. RACE-COUNT covers 99 plus two competing additions, explicit
101st rejection and refreshed-version retry. This supplies a consistent bounded
collection contract; runtime enforcement remains to be demonstrated.

### SR8-R3 — Superseded summary wording (consistency, resolved)

README now introduces the consolidated specification and test design and labels
the previous review record as historical. Newly introduced-statistic eligibility
is no longer presented as an undecided product question in the opening summary.
The source-specific mechanism remains a proposed implementation/design detail,
not retrospectively owner-approved architecture.

## Positive assessment

The specification now enumerates C01–C23 and Q01–Q13, with trusted actor provenance,
same-tenant wrong-parent checks, allowlisted mutable fields, action/lifecycle
enforcement independent of RLS, aggregate concurrency preconditions, retained
historical association/definition identity, scoped authenticated cursors and
explicit browser-policy failure precedence. Tests name direct-use-case, HTTP,
real-role PostgreSQL, no-partial-write, non-enumeration and independent mutation
evidence rather than relying on route checks or passing status codes alone.

## Final focused source-contract review

The prior missing-source-schema security qualification is resolved in design.
yousician-content-schema.md now specifies the exact Song/Version/Fragment
metadata allowlists, required fields, null/default behavior, normalization and
integer/length bounds. It distinguishes creation defaults from full replacement
requirements, so updates cannot silently reset observed note counts or measured
lengths. Per-entry ownership, parent resolution and version preconditions still
apply; the illustrative nested representation does not create a bulk mutation
or mass-assignment capability. Author is nullable plain text, not a new identity
or authorization resource. Fragment note counts are integers rather than a text
sink, and all displayed author/name data remains subject to ADR-009 contextual
escaping. No source field is added to historical snapshots by implication.

YS-01 through YS-06 cover these contracts' positive/negative boundaries, unknown
keys, omitted/null replacement differences, hierarchy, snapshot preservation and
configured practiceability. The version/fragment-only practiceability proposal
is safely constrained by published server policy; it is not represented as a
previously explicit product decision. A future choice to change it requires the
normal source-contract approval/versioning process, not a client override.

No new blocking authorization finding was identified in this focused review.
The source qualification can be removed from Issue #8's design-review status.
This recommendation does not mark test cases executed, waive owner review of
proposed defaults or authorize an otherwise gated implementation slice.

## Remaining gates and scope

- Initial Yousician metadata is now specified and independently security-reviewed.
  C03/C04 no longer have the previous missing-schema design blocker. Their
  implementation must enforce the reviewed contract and produce the named
  real-database and HTTP evidence; this review is not executable proof.
- Global/private categories are policy proposals. Actual schema/table identities
  and grants must be reconciled with ADR-008's reviewed manifest before any RLS
  exemption is implemented; absence still means private by default.
- Owner review is required for material proposed contracts/architecture details,
  including historical eligibility binding; independent architecture and
  test-design verdicts remain separate requirements.
- Implementing slices must prove real transaction/role/predicate/RLS behavior,
  HTTP/browser integration and inventory coverage and obtain independent security
  and code review. No application tests were executed in this document review.
- No further sharing, media, export, Android/Telegram or offline feature design
  is requested. Their current denial/foundation rules remain in force.

With the separate architecture/test-design reviews and required owner acceptance,
Issue #8 may finish its design scope. SEC-07 must remain open for implementation
evidence in the affected slices; closing a design issue cannot close that finding
or establish production deployment readiness.
