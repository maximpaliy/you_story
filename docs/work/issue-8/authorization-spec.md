# MVP-05 authorization specification

Status: review draft, 2026-10-21. This consolidates owner decisions in README.md.
New field schemas and classifications below are proposed defaults, not claims of
prior owner approval. No route names, production code or deployed API is changed.
The approved architecture remains authoritative; conflicts block affected work.

## A. Shared enforcement contract

A1. Every product operation except the explicitly separated login flow requires
an active authenticated user and trusted immutable ActorContext. Only identity
can construct it, using validated session/account state. Client user/tenant IDs,
headers or callback payloads cannot construct or override it. Private resources
must match the actor's tenant; customizations additionally match actor user.
An inactive account or revoked/expired session cannot supply a valid actor.

A2. The owning use case authorizes operations even when called directly through
its public interface. Authorize every supplied parent, child and referenced
private ID, including same-tenant wrong parents. Cross-module checks use owner
public ports, never shared ORM/table access. Normal SQL uses actor predicates;
FORCE RLS independently applies ADR-008. Neither replaces action authorization.

A3. UUID targets are selectors, not editable identities. Ownership, visibility,
grants, lifecycle state, timestamps, versions, snapshots and captured definition
identity are never generic writable fields. Command rows are exhaustive input
allowlists; unknown fields at any object level fail. Omission means unchanged
on update; null clears only explicitly nullable fields. Create defaults apply
only on creation. All mutations and their side effects commit atomically.

A4. Proposed error contract: absent/invalid authentication -> unauthenticated;
well-shaped absent or foreign private targets, including private filters and
wrong-parent children -> resource_not_found; malformed schema -> invalid_input;
forbidden/unknown fields -> invalid_input; known owned invalid lifecycle or
incompatible scope -> conflict; stale expected version -> version_conflict.
HTTP adapters map these to 401, 404, 422, 422, 409 and 412 respectively; missing
required version -> 428. Browser HTML authentication may redirect under its
reviewed identity contract instead of JSON 401. ADR-009 pre-dispatch provenance,
CSRF and representation failures retain their own errors and precedence. Schema
shape checks may precede lookup, but no existence-dependent validation message
is emitted until the referenced private resources are authorized. Foreign and
missing targets share status, stable error body and cache policy. Errors exclude
names, counts, definition details and foreign IDs beyond the request itself.

A5. Resource mutations require an expected version. Session is the aggregate
concurrency gate: ALL record/statistic writes also require expected_session_version,
lock/recheck the authorized session, require draft, and increment its version.
Existing record writes additionally require expected_record_version and increment
it. Complete/reopen lock the same session. A concurrent child mutation and
completion cannot both commit using the same session version. Catalog hierarchy
writes serialize against catalog version (expected_catalog_version); entry
updates also check expected_entry_version. All successful catalog writes bump
catalog version, and changes to an existing entry bump its version. Definition
and customization updates use their own expected version. New customization
creation explicitly requires absence (not an unchecked upsert). Versions are
opaque positive integers in input; clients cannot assign resulting versions.

A6. Authorization-dependent state checks and writes share one unit of work.
Owner public ports provide transaction-scoped guards, not unlocked check-then-use
booleans. Record creation guards the selected entry and its catalog/definition
binding against concurrent edit/move/tombstone until the coherent snapshot
commits. Customization writes similarly guard the entry's active state.
Characteristic assignment guards active definition against retirement; statistic
addition/initial capture guards authoritative retirement state. Owner ports must
lock/recheck or use equivalent serializable conflict detection, with consistent
documented lock order and bounded conflict handling. A write may succeed only
if it linearizes before the competing retirement/tombstone; otherwise it fails
atomically. No cross-module raw table access is authorized by these guards.
Concrete transaction and lock-order proof remain implementation evidence.

## B. Concrete field schemas (proposed defaults)

| Field | Contract |
| --- | --- |
| name | Unicode NFC, trim surrounding whitespace, 1–200 Unicode code points; plain text |
| notes, description, goals | Nullable plain text, NFC, at most 10,000 code points; empty accepted; null clears |
| identifiers | UUIDs for resources; reference keys are case-sensitive registered keys, max 100 ASCII letters/digits/underscore/hyphen |
| tags | At most 50 NFC trimmed nonempty strings, each max 100 code points; reject duplicates after normalization; array replacement |
| personal metadata | No arbitrary keys in MVP; allowed object is empty until named fields receive review |
| source metadata | Exact source-definition-version allowlist, types and bounds; required fields retained on update; no arbitrary nested keys |
| entry order | Read-only server stable order for MVP; no reorder command |
| duration | Positive integer elapsed seconds, max 604800 (7 days), not bool/fraction; no claim it equals session wall duration |
| integer value | Signed 64-bit integer excluding booleans, within immutable declared inclusive bounds |
| decimal value | Finite base-10 string, max 38 digits total and 18 fractional digits; immutable declared bounds; reject NaN/infinity |
| boolean value | JSON boolean only |
| text value | Plain text max 10,000 code points, additionally bounded by definition |
| duration statistic | Nonnegative integer seconds, immutable definition bounds, max signed 64-bit |
| enum value | One immutable registered string key; 1–100 choices, keys max 100 chars |
| characteristic specification | One of the six value kinds above, optional applicable bounds (text length 0–10,000, numeric min/max, enum choices); no executable schema; value always required on assignment |

Scope for a private characteristic is source_key + instrument_id + entry_type;
all are immutable. Name/nullable description may change; meaning/specification
cannot. No command changes statistic type, unit, bounds or choices; any such
change creates a distinct statistic identity. Display labels on previously
recorded values remain captured, regardless of current labels.

Every record has at most 100 statistic values, one per definition identity.
C18 and C20 enforce the same aggregate bound while holding the record/session
concurrency gate. Q11/Q12 may include the whole bounded set; concurrent additions
cannot exceed it. Definition bounds must have min<=max, defaults must satisfy
bounds, enum keys must be unique, and unknown specification fields are rejected.

Source-binding proposal: a new root uses the server's explicitly configured
published default source version; a child inherits its parent's immutable
version. Create/move validate all affected edges against that version, not the
current default. Moves across differing source-definition versions are rejected
in MVP, including an affected subtree containing mixed versions. Existing entry
edits validate metadata against the stored version, never silently upgrade it.
The initial Yousician metadata schema (including exact level type/bounds) is not
presently defined in approved documents. C03/C04 remain blocked until a reviewed
initial source-definition contract names all required fields, types and bounds.
Do not guess a Yousician level scale merely to fill this gap.

## C. Definition classification and historical eligibility

Proposed reviewed-global manifest categories: instrument reference rows, source
keys, immutable published source-definition versions and their statistic
specifications. Read audience is authenticated product users; no anonymous
reference endpoints. Publication is reviewed app_owner setup/migration work,
not a user command. Do not exempt any actual table from RLS until its exact
schema/table identity is reconciled with ADR-008's manifest and reviewed in the
foundation issue. Identity's five-table control plane remains its separate
reviewed exception, not global product reference data.

User-created characteristic definitions, assignments, customizations, catalogs,
entries, sessions, records and their children are tenant-private. Statistics
recorded by a user are private even if their definitions are global. A private
characteristic never becomes global through a field update.

Proposal for historical eligibility: record creation captures an immutable
reference to the published source-definition version used by its selected entry,
plus source/instrument/entry type and applicable policy context in the snapshot.
Published versions are retained, never edited/deleted in place. Later additions
resolve statistic IDs from that version's applicable set; record the exact
immutable definition ID on each value. Do not copy the entire available set.
A statistic introduced only in a later source-definition version is ineligible,
even if it currently applies to the live entry. No current-entry lookup can
expand historical eligibility. A globally retired statistic cannot receive a
new value, even if historically eligible. Existing values remain readable,
correctable/removable in drafts under their original definition. Publication
must not backdate additions to an old version. Immutable membership, not a
client-supplied time/version, establishes eligibility. This mechanism is a
reviewable architecture clarification, not an already approved storage change.

## D. Command matrix

All rows inherit A–C. `CV/EV/SV/RV/DV/UV` mean expected catalog/entry/session/
record/definition/customization version. Inputs listed are exhaustive; optional
fields have `?`. Required references are authorized before domain validation.
For source metadata, update is full-object replacement to avoid ambiguous merges.

| ID | Command and client input | Authorization and state | Result |
| --- | --- | --- | --- |
| C01 | Complete login: code+state OR provider error+state | Pre-auth exception: validated transaction, issuer/sub, invitation and session policy under ADR-007/008 and Issue #6; no caller actor | Approved atomic identity/tenant/bootstrap/session flow only; exact OIDC wire fields remain owned by #6 |
| C02 | Logout current session: none | Valid current session, CSRF where browser; no supplied session ID | Revoke current session only; repeated logout with no valid session has no mutation |
| C03 | Create entry: catalog_id,CV,parent_entry_id?,source_key,instrument_id,entry_type,name,metadata | Own personal catalog; active authorized parent in same catalog/source/instrument; registered hierarchy and definition | New active entry, server ID/order/version and source-definition binding |
| C04 | Update entry: entry_id,CV,EV,name?,metadata? | Own active entry and catalog; at least one mutable field | Update details only; no definition/type/source/instrument/parent changes |
| C05 | Move entry: entry_id,CV,EV,new_parent_entry_id | Own active entry and active new parent; same catalog/source/instrument, compatible graph, no cycle | Move subtree without changing identities/snapshots; root reparenting and cross-catalog moves unsupported |
| C06 | Tombstone entry: entry_id,CV,EV | Own active entry; zero active direct children under same hierarchy lock | Tombstone only; no implicit cascade/hard delete/restore |
| C07 | Create characteristic: source_key,instrument_id,entry_type,name,description?,specification | Actor tenant; valid published reference scope | New private active definition; server identity |
| C08 | Update characteristic: definition_id,DV,name?,description? | Own active definition; at least one supplied mutable field | Presentation only; no meaning/scope change |
| C09 | Retire characteristic: definition_id,DV | Own active definition | Retired; existing assignments retained, no new/change assignment values |
| C10 | Set characteristic: entry_id,CV,EV,definition_id,value | Own active entry and own active definition; exact compatible scope | Atomic assignment create/replace; bump entry/catalog version |
| C11 | Remove characteristic: entry_id,CV,EV,definition_id | Own active entry and actual assignment; own definition may be retired | Remove assignment only; bump entry/catalog version |
| C12 | Set customization: entry_id,UV OR expect_absent,tags?,goals?,metadata? | Own active entry; customization belongs to actor; choose exactly one precondition | Create/update actor customization only; new defaults tags=[],goals=null,metadata={} |
| C13 | Clear customization: entry_id,UV | Own entry and existing actor customization; entry may be tombstoned | Delete customization only |
| C14 | Create session: start_at,time_zone,end_at?,notes?,idempotency_key | Actor tenant; valid timing; idempotency scoped actor tenant+operation+canonical payload | Draft; default end=start+30 elapsed minutes; replay returns original result, mismatched payload conflicts |
| C15 | Update session: session_id,SV,start_at?,end_at?,time_zone?,notes? | Own draft; at least one supplied mutable field; resulting timing valid | Update supplied fields and recompute local start date; never silently shift stored end |
| C16 | Complete session: session_id,SV | Own draft; valid data; zero records allowed | completed; same-state request conflicts |
| C17 | Reopen session: session_id,SV | Own completed | draft; no recapture/reassociation; same-state request conflicts |
| C18 | Create record: session_id,SV,entry_id,duration,notes?,statistics? | Own draft session; independently authorize active practiceable own entry | Server snapshot and eligibility capture; statistics max 100 unique eligible definition IDs/values; empty allowed |
| C19 | Update record: session_id,record_id,SV,RV,duration?,notes? | Own draft and actual record membership | Edit details only; live entry need not remain active/practiceable |
| C20 | Add statistic: session_id,record_id,SV,RV,definition_id,value | Own draft/record; historical eligibility C; definition not retired; no existing value for same definition | Capture immutable definition/display data; duplicates conflict |
| C21 | Update statistic: session_id,record_id,statistic_id,SV,RV,value | Own draft; actual full parent chain; validate original definition, even if retired | Value only |
| C22 | Remove statistic: session_id,record_id,statistic_id,SV,RV | Own draft; actual full parent chain | Delete value only |
| C23 | Remove record: session_id,record_id,SV,RV | Own draft; actual membership | Atomic record/snapshot/statistic removal; no catalog/definition changes |

No additional product command exists for profile editing, catalogs, reference
publication, grants, visibility, session deletion, media, exports or offline sync.
Login initiation/authenticated home use the identity/browser contracts, not an
implicit tenant command; personal-catalog provisioning is first/pending-login
only. No workers, management CLI, scheduler, async consumers or tenant-data
migration callbacks are introduced. Reviewed global setup is not runtime access.

## E. Lifecycle tables

| Resource | Allowed transition | Restrictions |
| --- | --- | --- |
| Session | create -> draft; draft -> completed; completed -> draft | No automatic time-triggered transition, delete or cancel; completed rejects all child/details writes |
| Entry | create -> active; active -> tombstoned | Active-child check atomic with concurrent move/create; retained ancestors still display in snapshots |
| Characteristic | create -> active; active -> retired | No restore/delete; retired assignments readable/removable, not assigned/changed |
| Statistic definition | published -> retired | Controlled reference setup only; membership/specification immutable; retired existing values correctable |
| Record | create/update/remove under draft session | Association and snapshot immutable while retained; removal is explicit authorized exception |

## F. Time and query contract

start_at/end_at are RFC3339 offset-qualified timestamps, with second precision;
time_zone is a valid IANA identifier (max 100 chars). Reject offset/zone mismatch
at the supplied instant. UI local-time entry must reject DST gaps and require
an offset choice for folds; it submits the resolved timestamp. End is strictly
after start. Defaults add 1800 elapsed seconds in UTC, not wall-clock minutes.
No implicit duration cap is applied to session windows. Persist UTC instants,
captured zone and derived start local date. Cross-midnight sessions belong once
to start date. Browser travel never regroups history; draft timing/zone edits may.

Common query input P: page_size integer 1–100, default 50; opaque authenticated
cursor max 2048 chars bound to actor, operation, normalized filters and order.
Reject altered/cross-actor/cross-filter cursors generically without querying
foreign data. Stable keyset order includes UUID tie-breaker. Pages are not a
snapshot across concurrent edits; document possible movement, never foreign data.
No totals by default; any later count inherits identical authorization/filtering.
All tuple components sort ascending unless explicitly marked descending. Names
use stored NFC text in case-sensitive UTF-8 byte order (PostgreSQL C collation),
not locale-dependent ordering; UUID ties compare unsigned 128-bit values.
Q03's key is (source_key,instrument_key,entry_type,definition_key), with absent
scope components sorting as empty strings, then numeric version, then UUID.
Q13 sorts both session start and record UUID descending. Cursors encode the
entire sort tuple. Source/version integers sort numerically, never as text.
Filters have exact allowlists; search text max 200 code points, literal text
rather than query syntax. Date ranges are inclusive local dates, max 366 days.
Use resource_not_found for well-shaped foreign/nonexistent private filters.

Returned-field sets: Profile={user_id,display_name}; Catalog={id,name,version};
Entry={id,catalog_id,parent_id,source_key,instrument_id,type,name,metadata,state,
version}; Characteristic={id,scope,name,description,specification,state,version};
Customization={entry_id,tags,goals,metadata,version}; Session={id,start_at,end_at,
time_zone,local_date,notes,status,version}; Record={id,session_id,entry_id,duration,
notes,version,snapshot,statistics}; snapshot contains approved source/instrument/
ancestor/type/name/schema and eligibility binding; statistics expose id,
definition_id,captured type/unit/label/bounds and value. No tokens, identity
provider subject, invitation state, ownership/grant internals or other users'
customizations. API serializers use these allowlists, not ORM dumps.

| ID | Input beyond trusted actor | Output/order and authorization |
| --- | --- | --- |
| Q01 | none | Profile of actor only |
| Q02 | none | Actor Catalog; no on-read provisioning |
| Q03 | source_key?,instrument_id?,entry_type?,P | Published reference keys/names, version, schema and applicable immutable statistic specifications; order key/version/UUID; authenticated-only reviewed global manifest |
| Q04 | entry_id | Entry, including own tombstone for historical navigation |
| Q05 | entry_id,direction=children or ancestors,P for children | Own authorized entry; children active-only, order server sibling order/UUID; ancestors full authorized chain bounded by registered hierarchy depth |
| Q06 | text?,source_key?,instrument_id?,entry_type?,ancestor_id?,P | Active Entry items; actor scope before filtering; name/UUID order; ancestor must be own accessible entry |
| Q07 | definition_id OR source_key?,instrument_id?,entry_type?,P | Own Characteristic, including retired for existing assignment display; list order name/UUID; no implicit mixed global/private lookup |
| Q08 | entry_id | Authorized Entry's assignments with own definition detail and actor Customization; tombstone reads allowed |
| Q09 | local_date,P | Actor Session items whose captured local_date matches; start_at/UUID ascending, regardless of viewer zone |
| Q10 | session_id | Own Session |
| Q11 | session_id,P | Own session's Record items; server created_at/UUID ascending |
| Q12 | session_id,record_id | Record only after same-tenant and actual-parent authorization |
| Q13 | entry_id,date_from?,date_to?,P | Own entry including tombstone; own Record items matching immutable selected-entry ID; dates use containing session's local_date; descending session start/record UUID |

## G. Review and approval boundary

This draft proposes concrete defaults for all listed actions, not implementation
approval. It needs independent architecture/security/test-design review, owner
review of material changes (notably historical eligibility capture), and detailed
implementation evidence later. Identity/security designs referenced here are not
replaced. SEC-07 remains open until the appropriate implementation reviews.
