# Issue #8 — MVP-05 authorization design

Issue: https://github.com/maximpaliy/you_story/issues/8

## Status

This decision summary was reconstructed from the conversation on 2026-10-21
because the earlier local Issue #8 files were absent from the current checkout.
It does not claim those earlier files were committed or remotely persisted.
The live issue body has not been reconciled; the earlier GitHub API read was
forbidden. Scope follows the repository's MVP-05 backlog.

The owner accepted the authorization baseline and proposed command inventory,
with the clarifications below. On 2026-10-21 the owner also accepted the proposed
query inventory for MVP. This permits continued design refinement, not production
implementation or SEC-07 closure.

## Detailed draft for review

See [authorization specification](authorization-spec.md) for command/query
fields, lifecycle rules, classifications, errors and concurrency contracts, and
[test design](test-design.md) for named adversarial cases and evidence oracles.
Proposed architecture clarifications are captured in
[ADR-010](../../architecture/decisions/010-mvp-authorization-contract.md).
These are not retrospective owner approval of proposed schemas or runtime
validation. Independent [architecture](architecture-review.md),
[security](security-review.md) and [test-design](test-design-review.md) reports
record focused re-review after remediation: policy/test structure supported;
initial source metadata schema remains explicitly blocked. In particular,
Yousician level type/bounds require a reviewed source contract. New proposed
schemas and material architecture clarifications still need owner review.

## Accepted policy and command direction

- One authenticated user acts within a personal tenant. Trusted ActorContext
  supplies identity/tenant; client input cannot assign them.
- Owning application use cases enforce permissions independently of HTTP routes.
  Explicit repository predicates and FORCE RLS remain independent controls.
- Authorize parent/child relationships, including mismatched same-tenant IDs.
  Unlisted actions are denied; immutable fields cannot be mass assigned.
- Personal catalogs are automatically provisioned by the approved login flow.
  No catalog rename, detail editing or additional-catalog creation in MVP.
- Accepted command families: complete Google login, logout current session;
  create/update/move/tombstone entries; create/update/retire characteristic
  definitions; set/remove assignments; set/clear personal customizations;
  create/update/transition sessions; create/update records; add/update/remove
  recorded statistics. Previously provisional move/retirement semantics still
  require concrete lifecycle rules before exposure.
- A practice record's session, selected entry and server-generated snapshot are
  immutable after creation. Historical edits need not depend on the entry
  remaining live or practiceable.
- Statistic type/boundary changes create a new statistic identity. Existing
  values retain their original immutable definition. Eligibility of a newly
  introduced statistic on an old record is deferred beyond MVP; freezing an entire
  available-definition set at creation has not been approved.
- Sharing, media, account deletion, export and offline behavior stay deferred.
  Preserve only reviewed foundations and dormant-surface restrictions from
  ADR-003/005/006/008; no speculative infrastructure is introduced.

## Accepted MVP query inventory

These are application queries, not final HTTP endpoints. ActorContext is trusted
input separate from the client-supplied fields listed here. Authorization checks
apply to every returned private resource and relationship.

| ID | Query | Client inputs | Authorization/scope |
| --- | --- | --- | --- |
| Q01 | Get own profile | None | Minimal profile for current user |
| Q02 | Get personal catalog | None | Catalog derived from actor's tenant |
| Q03 | List reference definitions | Source, instrument, entry type as applicable | Only definitions available to actor; global/private classification remains to be specified |
| Q04 | Get catalog entry | entry_id | Entry in actor's personal catalog |
| Q05 | Browse entry children/ancestors | entry_id or parent_entry_id; pagination for children | Authorize starting entry and returned ancestry/child relationships |
| Q06 | Search catalog entries | Text, source, instrument, type, ancestry, cursor, page size | Actor-scoped results/counts; authorize private filter IDs |
| Q07 | List/get characteristic definitions | definition_id or scope filters; pagination | Actor-owned definitions and explicitly permitted reference definitions |
| Q08 | Get entry characteristics/customization | entry_id | Authorized entry; only actor's private tags/goals/metadata |
| Q09 | List sessions for calendar day | Local date; pagination | Actor's sessions under the agreed date/time-zone rules |
| Q10 | Get practice session | session_id | Actor-owned session |
| Q11 | List session records | session_id; pagination | Authorized session and actual record membership |
| Q12 | Get practice record | session_id, record_id | Verify session/record relationship; include snapshot and recorded statistics |
| Q13 | Get entry history | entry_id, supported date filters, cursor, page size | Authorized entry and actor-owned historical records; preserve tombstoned-entry history |

No separate table-level read interfaces are implied. Snapshot/statistic reads
can be included in record views. Calendar-to-history navigation composes session
and record queries. Returned fields, bounded filters/page sizes, cursor scope,
date/time-zone behavior and missing/foreign/tombstone responses still need
precise contracts. Proposed private-resource responses remain 401 for absent
authentication and indistinguishable 404 for missing/inaccessible resources,
subject to ADR-009 browser-policy failure precedence and final API review.

## Prior independent review outcomes and remaining work

Three independent agents reviewed the earlier baseline in this conversation;
all supported it as a starting point, with changes required. This summary is
not a new review or a reconstruction of their full reports.

- AR8-01: complete command/query, mutable-field and transition inventory.
  Query scope is now accepted, but precise schemas/state rules remain open.
- AR8-02 / SR8-03: historical association and statistic-definition authority.
  Owner clarifications above address part of the ambiguity; new-statistic
  eligibility capture is now proposed in authorization-spec.md; concrete tests
  and re-review remain necessary.
- AR8-03: explicitly reconcile login/bootstrap/logout and personal-catalog
  provisioning with reviewed identity and control-plane contracts.
- AR8-04 / SR8-02: classify global versus tenant-private definitions, their read
  audience and provisioning against ADR-008's reviewed manifest.
- SR8-01: specify per-command mutable fields, parent chain and lifecycle rules.
- Test review: detailed design was not approved. Required work includes named
  positive/negative cases per action/query, two-tenant and wrong-parent fixtures,
  no-partial-write oracles, direct-use-case and HTTP coverage, real PostgreSQL
  evidence linkage, non-enumeration/count/cursor checks, mass assignment,
  historical semantics and dormant-surface evidence.

Next: refine concrete contracts and test design, then obtain independent
re-review and any required final owner decisions. No outstanding finding is
represented as resolved solely by accepting this inventory. SEC-07 remains open.

## Owner decision — initial session end time (2026-10-21)

- Every practice session has an end time from creation, including draft sessions.
- If omitted on creation, the server defaults the end instant to 30 minutes
  after the start instant. An explicitly supplied end time is permitted.
- The end time may be extended or reduced under the applicable edit policy,
  but must remain strictly after the start. A start-time edit must leave the
  resulting pair valid; do not silently shift an existing end time.
- Thirty minutes is the initial creation default, not an immutable domain
  constraint. A later default change must not rewrite existing sessions.
- The time window and editorial status are separate. Passing the end time
  does not automatically complete the draft or require a scheduler; details
  may be entered afterward under the applicable draft-edit rules.

This replaces the earlier proposal that end time could be absent while draft.
Completion/reopening policies are recorded below; this decision alone does not
approve unrelated lifecycle rules.
Tests must cover explicit/default end time, extension/reduction, invalid ranges
and persistence of the chosen end time across later default changes.

## Owner decisions — lifecycle refinement

- Sessions explicitly transition draft -> completed and completed -> draft
  (reopen). Timing, notes, records and recorded statistics may be mutated only
  while draft. Completing/reopening requires ownership and expected-version
  checks; reopening preserves associations, snapshots and captured definitions.
- The owner prefers discarding empty sessions but explicitly tolerates them if
  removal adds work. MVP retains that fallback: empty drafts and completion with
  zero records are permitted. There is no automatic discard, cleanup scheduler
  or completion-time deletion. Do not describe rejection of completion as
  discarding a session. Whole-session removal remains deferred, particularly
  intended for accidental drafts in later work.
- Add Remove practice record to the accepted command inventory: inputs are
  session_id, record_id and expected_session_version. The actor must own the
  draft session and the record must actually belong to it. Atomically remove
  the record and its exclusively owned snapshot/statistic data, leaving catalog
  content and definitions unchanged. Concurrent completion must prevent a stale
  removal; exact locking/version mechanics remain an implementation design task.
  This intentional removal exception does not permit editing snapshot content
  or reassigning historical associations on retained records.
- Tombstoning a catalog entry is rejected while active children remain. No
  implicit subtree deletion or restore operation in MVP; referenced history
  remains readable. This is the accepted MVP default, not a promise about later
  catalog lifecycle behavior.
- The owner agrees that characteristic definitions need explicit value types,
  ownership and retirement rules, distinct from application-managed references.
  This agreement does not select the still-unspecified type schema, global/private
  classification or exact retirement mechanics.

Newly introduced statistics on old records remain deferred beyond MVP. The owner
now explicitly allows adding a previously omitted value while the containing
session is draft, provided the statistic already existed and applied when the
record was created. Validate against that original immutable definition, not a
client-selected version or today's replacement statistic. Server-side evidence
of historical applicability is required; its storage mechanism remains a design
task. Reopening does not change the record's eligibility baseline.

Retirement prevents adding new values, including to older records, while existing
values remain readable, correctable against their original definition and
removable while the session is draft. Thus historical applicability is necessary
but not sufficient for addition: the definition must also remain available under
the retirement and authorization policies at the time of the command.

Tests must cover complete/reopen, mutation denial while completed, wrong-parent
record removal, cross-tenant removal, atomic removal of owned children, concurrent
completion/removal, accepted empty sessions and active-child tombstone rejection.
These decisions require incorporation into detailed design and independent
re-review; no prior review finding is automatically closed.

## Agreed time-zone policy and query defaults

The owner accepted captured-session-zone calendar behavior. Store start/end UTC
instants and retain the original IANA zone. Default creation zone from the
browser with explicit correction available. Group by start date in the captured
zone; sessions crossing midnight appear once. Travel/browser-zone changes do not
regroup existing sessions. Draft timing/zone correction recomputes the local
date; completed sessions must first be reopened. Default duration is 30 elapsed
minutes, including across daylight-saving changes. Reject nonexistent local
times and require disambiguation of repeated local times. Browser zone is a
convenience default, not trusted authorization input.

UTC instants and retained zone permit a later display/grouping policy change
without altering historical instants, but that remains a deliberate reviewed
UI/API behavior change rather than an automatic migration of existing data.

The owner delegated pagination to reasonable defaults: 50 results by default,
maximum 100, stable ordering and opaque cursors bound to actor/query scope.
The proposed entry-name and notes/comments limits are 200 and 10,000 characters
respectively; exact normalization/counting and field-specific schemas belong in
the detailed contract. No new approval of unrelated validation limits is implied.

Tests must include late addition of an eligible omitted statistic, rejection of
newly introduced or retired statistics, completed-session denial, immutable
eligibility after reopening, DST gaps/folds, cross-midnight grouping, travel,
zone edits and pagination isolation. Product direction is established; concrete
contracts, characteristic/reference classification, test design and independent
re-review remain outstanding.

## Verification

Documentation-only change; no application code or runtime tests changed.

## Minimal Yousician content shape

The owner supplied song author, version level and fragment length_seconds/notes_count
fields. See [source schema draft](yousician-content-schema.md). The owner clarified notes_count as the number of musical notes. Precise field
validation remains to specify; prior source-schema review blockers are not yet
claimed resolved.

The owner agreed to the 200-code-point normalized name limit and clarified that
fragment length_seconds is optional because it requires measurement. notes_count
may initially be 0 because Yousician reveals it only after playing. See the
source draft for explicit unknown/default/update semantics; zero is not proof
of a verified empty fragment.

The owner subsequently explicitly approved optional measured fragment length
(null for unknown) and initial notes_count=0 under those semantics. This scoped
approval does not mark the entire issue or pending source-contract re-review
complete.
