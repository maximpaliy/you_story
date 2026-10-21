# MVP-05 authorization test design

Status: proposed design, not executed tests. Policy oracle: authorization-spec.md
A–F. Case IDs below are stable; commands C01–C23 and queries Q01–Q13 are the
coverage inventory. Concrete test code belongs to the implementing slices.

## Fixtures, layers and oracles

Actors A and B have distinct users/tenants and valid active sessions; invalid
actors cover absent, revoked, expired and inactive-account sessions. A owns two
catalog trees and two practice sessions (one draft, one completed); B has an
isomorphic tree/session/record/statistic set. Use two branches within A's single
catalog, not two provisioned personal catalogs. Fixture IDs include foreign
existing, random nonexistent, wrong same-tenant parent and malformed UUID.
Definitions include global published source versions V1/V2, private definitions
for A/B, incompatible scopes, active/retired definitions and all six value kinds.
V2 introduces a statistic absent from V1 and replaces another with a distinct
identity/bounds; V1 remains immutable. A V1 record has one stored value and one
eligible omitted value; live entry later changes/tombstones. Maintain catalog,
session and record versions and an empty session.

Layers: U=real owner public use case with trusted actor (not HTTP route);
H=production-equivalent HTTP adapters/auth/browser middleware; D=real PostgreSQL
migrations/app_runtime, FORCE RLS and transaction-local context; S=static/config/
composition; B=real browser for time-zone input and browser policy integration.
U and H execute all applicable command/query cases, D proves persisted effects
and isolation for private paths. Mocks alone never establish isolation. C01 uses
the reviewed provider harness/negative cases from Issue #6, not live Google.

Each success checks exact allowlisted result AND affected durable state; deny
cases compare before/after owner-visible rows across all participating modules,
including versions, snapshots, assignments and statistics. No partial rows or
changes on denial, conflicts, cancellation or injected transaction failure.
Reads assert exact authorized IDs/order/fields, not only status or row count.
Use barriers for races, not sleeps; enumerate both permitted serialization
orders and require lifecycle/ownership invariants in final durable state.

## Parameterized cases applied to the entire inventory

- AUTH-{ID}-ALLOW: each row's valid input yields its documented result. Run for
  every C/Q ID, including positive empty/zero-statistic controls where allowed.
- AUTH-{ID}-ACTOR: every authenticated row rejects absent/invalid actor; direct
  callers cannot forge ActorContext. C01 is the explicit pre-auth exception.
- AUTH-{ID}-FOREIGN and AUTH-{ID}-MISSING: substitute each private selector and
  each nested private reference independently. Both yield resource_not_found,
  identical stable error shape/cache/header class and no mutation/disclosure.
  Q01/Q02/C14 have derived ownership: assert they act on A only rather than
  accepting a foreign target field. C01/C02 follow explicit identity cases.
- AUTH-{ID}-FIELDS: exhaustive allowed-field schema tests plus each forbidden
  tenant/owner/visibility/grant/status/version/snapshot/definition field and
  unknown nested key. Assert invalid_input and unchanged state. Expected version
  preconditions are legitimate inputs, never resulting-version assignments.
- AUTH-{ID}-VERSION: each existing-resource write rejects stale/missing required
  versions; test each aggregate/resource version separately; no partial writes.
- AUTH-{ID}-PARENT: every child action/query rejects a same-tenant wrong parent,
  not only foreign parents. Apply to entry ancestry, assignments, record/session,
  statistic/record and entry history relationships where those selectors exist.
- AUTH-{ID}-STATE: exercise allowed and denied lifecycle rows E, including
  completed-session mutation denial for C15/C18–C23 and same-state C16/C17.
- AUTH-{QID}-SERIALIZE: assert field allowlist with secret/foreign canary values
  present in storage; never include identity/control-plane secrets or B's data.
- AUTH-{QID}-PAGE: every paginated query: default/1/100 bounds, 0/101 rejection,
  tie-break order, no duplicates across unchanged-data pages, tampered or wrong
  actor/query/filter cursor rejection; concurrent movement explicitly not a
  snapshot guarantee. Include foreign private IDs in filters and cursors.

Applicability is derived from each row's selector/precondition fields; a row
without such a field must instead reject client attempts to introduce it. The
review checklist must reconcile case expansions to all rows and each reference
position; a zero-case expansion or unclassified row fails the inventory check.

## Named row-specific cases and owning evidence

| Policy rows | Named cases and required expected outcomes | Layers / implementation owner |
| --- | --- | --- |
| C01 | LOGIN-BOOTSTRAP: invitation consumption, identity/tenant/catalog provisioning atomic; repeat login not per-request provisioning. LOGIN-REPLAY: issue #6 state/nonce/PKCE/issuer/audience/signature/expiry and replay cases deny without orphan accounts/catalogs | H,D plus Issue #6 design; MVP-07 implementation |
| C02 | LOGOUT-SELF: A revokes only current A session; second A session and B unaffected; revoked session denied on next private operation. LOGOUT-CSRF: ADR-009 pre-dispatch denial leaves session unchanged | U,H,D,B / MVP-07 |
| C03–C06 | ENTRY-GRAPH: correct hierarchy succeeds; wrong scope, cycle and tombstoned parent fail. ENTRY-MOVE: subtree remains valid and prior snapshot ancestry unchanged. ENTRY-TOMBSTONE-CHILD: active child blocks; child-first tombstone succeeds, history remains. ENTRY-RACE: concurrent child create/move and parent tombstone cannot leave active child under tombstone | U,H,D / MVP-08, MVP-11 history |
| C07–C09 | DEF-PRIVATE: B cannot read/assign/edit A definition; schema/type/scope immutable. DEF-RETIRE: existing assignments readable/removable, new/change assignments denied. DEF-SCHEMA: exercise type bounds, enum duplicates, bool-as-int and normalization | U,H,D / MVP-09 |
| C10–C11 | ASSIGN-SCOPE: owned entry plus B definition -> not_found; owned incompatible definition -> conflict. ASSIGN-PARENT: wrong entry relationship denied; retired definition removal succeeds, assignment change denied | U,H,D / MVP-09 |
| C12–C13 | CUSTOM-PRIVATE: actor customization does not mutate source fields/another user. CUSTOM-CREATE-RACE: expect_absent admits at most one creation. CUSTOM-CLEAR: clears own customization on tombstone but retains definitions and entry | U,H,D / MVP-09 |
| C14–C17 | SESSION-DEFAULT: omitted end is +1800 elapsed seconds; explicit end retained, changed default never rewrites stored session. SESSION-RANGE: end<=start denied; start edit does not shift end. SESSION-EMPTY: empty complete/reopen allowed. SESSION-NO-AUTO: passing end changes no status. SESSION-IDEMPOTENCY: same key/payload returns original, changed payload conflicts, A/B keys isolated | U,H,D / MVP-10 |
| C18–C19 | RECORD-CAPTURE: snapshot from authorized server entry, optional stats empty succeeds; B entry or wrong parent denies atomically. RECORD-HISTORY-EDIT: original entry rename/move/tombstone leaves snapshot fixed and draft notes/duration corrections possible. RECORD-RETARGET: entry/session/snapshot substitution rejected | U,H,D / MVP-11 |
| C20 | STAT-LATE-ELIGIBLE: omitted V1-applicable active statistic added to V1 record succeeds. STAT-NEW: V2-only statistic rejected despite current entry update. STAT-RETIRED: historical eligible retired definition denies addition. STAT-IDENTITY: replacement with new ID cannot alter old value's bounds/meaning; client version selection rejected | U,H,D / MVP-11 |
| C21–C22 | STAT-ORIGINAL: corrections validate original definition even after retirement; wrong record/session statistic ID denied. STAT-REMOVE: remove only target value, retain snapshot/other values | U,H,D / MVP-11 |
| C23 | RECORD-REMOVE: remove owned draft record and exclusive children, preserve entry/definitions/other records. RECORD-REMOVE-ROLLBACK: injected failure leaves all rows/versions intact | U,H,D / MVP-11 |
| C15–C23 | SESSION-RACE: child mutation vs complete with same SV permits at most one commit; reopen preserves original eligibility. STAT-RACE: add vs retirement serializes to valid pre-retirement addition or rejection, never post-retirement bypass | U,D / MVP-10/11 |
| Q01–Q03 | READ-AUDIENCE: profile/catalog self-only, reference reads require authentication; global manifest cannot accidentally include private definitions/control plane. PROFILE-LEAK: provider sub/token/invitation fields never serialized | U,H,D,S / MVP-06/07/08 |
| Q04–Q08 | CATALOG-READ: active search excludes tombstones, direct own tombstone readable; ancestry/assignments correct; private definition leaks and reference/private mixed-ID confusion denied | U,H,D / MVP-08/09 |
| Q09–Q12 | CALENDAR-READ: correct captured day/session/record membership; no records from wrong same-tenant parent or B; snapshots/statistics only through authorized record | U,H,D / MVP-10/11 |
| Q13 | HISTORY-BOTH: day->session->record and entry->record journeys return exact records; entry rename/move/tombstone does not lose immutable-ID history or expose B; inclusive date bounds and 366-day max | U,H,D,B / MVP-12 |

## Cross-cutting evidence

TZ-01: Europe/Amsterdam spring gap local time rejected, autumn repeated time
requires offset choice; round-trip offset must match IANA zone. Across both DST
transitions default end is +1800 elapsed seconds. TZ-02: midnight crossing appears
once under local start day; changing viewer Tokyo/Amsterdam has no grouping
effect. Draft zone/timing edits update derived day, completed edits denied.
Run U/H/D and B local-input cases in MVP-10/12 with pinned tzdata evidence.

LEAK-01: compare foreign-existing and nonexistent selectors/filter IDs using the
same error schema, status, permitted headers/cache/redirect behavior and response
size class; counts and cursor results reveal no foreign existence. Use bounded
repeated timing samples under controlled fixtures and record distributions;
this is regression evidence, not a claim of constant-time database operations.
Avoid absolute timing assertions in normal CI; suspicious differences require
investigation before signoff. Include early validation vs lookup precedence and
ADR-009 forbidden-response precedence.

DB-01: reuse ADR-008 / Issue #5 design and MVP-06 real-role evidence for missing,
mismatched/stale context, pooled reuse, query predicate inspection, owner bypass
and separate predicate/RLS mutations. Extend its private table/query-site manifest
to every newly implemented row; no action-level permission may rely on RLS alone.
AUTH-MUTATION: remove a use-case parent/action check while SQL/RLS stay intact;
same-tenant wrong-parent/completed-state cases must fail. Remove tenant scoping
and RLS independently using reviewed ADR-008 mutations; reject masked tests.

DORMANT-01: production OpenAPI/route/composition inventories contain no sharing,
media, export, session-delete, account-delete or background execution root;
app_runtime has no dormant media privileges; visibility/grant activation input
fails. No tests implement deferred Android/Telegram/offline behavior.

## Evidence and completion

Each implemented case records policy ID, layer, command/target, fixture revision,
source commit, runtime DB role/version, runner exit status, nonzero executed
case count, failure/skip counts and sanitized state oracle output. Evidence
contains no sessions/OIDC secrets or user content. Distinguish designed vs run,
pass vs skipped; a zero-test run never satisfies a row. Reviewers reconcile
C01–C23/Q01–Q13 and private query/table/composition inventories. These are design
requirements, not a claim any application or database test has executed now.

## Focused review remediation cases

SCHEMA-01 (U/H): NFC name lengths 0/1/200/201; notes/goals 0/10000/10001;
combining-character equivalent inputs normalize identically, tag duplicate and
50/51 count checks, tag lengths 0/100/101. Assert exact accepted normalized output
or invalid_input with no state change. SCHEMA-02: all numeric kinds at min/max
and one beyond, min>max definition rejection, bool vs integer, 38/39 total and
18/19 fractional decimal digits, nonfinite values, duplicate/unknown enum keys,
text bound edges, metadata unknown/missing required keys, omitted vs null and
empty update. SCHEMA-03: page sizes 0/1/50/100/101 and date ranges 366/367 days.
Use property generators bounded by each definition's scope and boundary rules,
fixed recorded seeds plus shrinking/replay artifacts; model oracle evaluates
schema and immutable bounds independently from production validators.

RACE-DEF (U/D): C09 vs C10 under barriers; assignment can commit before retirement
and remain readable, or fail after retirement with no assignment/version change.
RACE-ENTRY (U/D): C06 or C05/C04 vs C18; committed record must have one coherent
pre-transition snapshot if record linearizes first, otherwise tombstone denies
creation or move/edit yields one coherent post-transition snapshot. No hybrid
ancestor/name/definition capture. RACE-CUSTOM: C12 vs C06 similarly permits only
pre-tombstone customization or post-tombstone rejection. RACE-COUNT: statistic
count 99, two concurrent additions; at most one succeeds to 100 under shared
SV/RV, never 101; explicit 101st addition fails atomically. Retrying with refreshed
versions must still enforce count. Each race requires valid controls for both
serialization orders, not treating a single stale-version rejection as evidence
of every referenced-resource guard.

BINDING-01: root configured V1, child inherits V1 after default advances to V2;
metadata edit still validates V1. Mixed-version move denied; no silent upgrade.
C03/C04 schema expansion is explicitly blocked until the reviewed initial source
contract supplies level and other exact source fields; do not claim these tests
are complete or run before that contract exists.

ORDER-01: derive exact expected tuples from F's NFC/C-byte order and numeric
version/UUID rules. Include case variants, accented and combining forms, equal
names, versions 2/10, same session timestamp with different record UUIDs, and
page size 1 across ties. Assert all components/directions for Q03/Q13, cursor
binding to full tuple and no skip/duplicate under unchanged data. Query source
keys must be explicitly serialized even when scope components are absent.
