# Proposed HTTP contract — Issue #11

Status: approved by the owner on 2026-10-26, including author search and
ADR-013. Additive to the baseline docs/api/openapi.json; generated active
contract now includes these routes.
All endpoints require the existing cookie-authenticated validated actor. No
caller-selected tenant/user, Authorization alternative or on-read provisioning.
All objects reject additional properties; repeated/unknown query/form fields,
duplicate JSON keys, nonfinite JSON values, and unsupported request bodies fail.

## JSON routes

| Method/path | Input | Success |
| --- | --- | --- |
| GET /api/v1/catalog | none | 200 Catalog; aggregate ETag |
| GET /api/v1/catalog/references | none | 200 {sources,instruments}; only Yousician v1 and guitar/piano, exact published schemas/practiceable types |
| GET /api/v1/catalog/entries | text?,author?,source_key?,instrument_id?,entry_type?,ancestor_id?,page_size?,cursor? | 200 Page |
| GET /api/v1/catalog/entries/{entry_id} | none | 200 Entry; entry ETag |
| GET /api/v1/catalog/entries/{entry_id}/children | page_size?,cursor? | 200 Page |
| GET /api/v1/catalog/entries/{entry_id}/ancestors | none | 200 {items: Entry[]}, root-to-parent, max 2 |
| POST /api/v1/catalog/entries | parent_entry_id? (null=root),source_key,instrument_id,entry_type,name,metadata | 201 Mutation; Location to new entry |
| PATCH /api/v1/catalog/entries/{entry_id} | expected_entry_version; name?,metadata?; at least one mutable field | 200 Mutation |
| POST /api/v1/catalog/entries/{entry_id}/move | expected_entry_version,new_parent_entry_id | 200 Mutation |
| POST /api/v1/catalog/entries/{entry_id}/tombstone | expected_entry_version | 200 Mutation |

Catalog={id:UUID,version:positive integer}.
Entry={id,catalog_id,parent_id,source_key,source_definition_version,instrument_id,
type,name,metadata,state,version}; parent_id nullable; state active/tombstoned;
source_definition_version positive integer, immutable. Other IDs are UUIDs.
Metadata exactly follows ../issue-8/yousician-content-schema.md, including
creation defaults and explicit full replacement fields. No arbitrary metadata.
Mutation={catalog:Catalog,entry:Entry}. Page={items:Entry[],next_cursor:string|null}.
References sources=[{key:"yousician",version:1,definition:{types,parent_rules,
metadata_rules,practiceable_types}}], instruments=[{id,key,name}] for guitar/piano.
Concrete definition schema must be included in the OpenAPI candidate before
implementation; no executable JSON schemas or private fields in definitions.

All writes require exactly one strong If-Match: "catalog:<uuid>:<version>".
It refers to the current own catalog, including on entry routes. Missing ->428;
malformed, weak, wildcard or list ->422; authorized mismatch ->412.
GET catalog and Mutation return that aggregate ETag. GET detail uses
"entry:<uuid>:<version>"; it cannot substitute for aggregate If-Match.
Existing target writes also require positive integer expected_entry_version;
missing ->428, malformed ->422, stale authorized value ->412. All versions are
JSON integers excluding booleans, <=9223372036854775807. No If-None-Match/304
semantics in this slice; private responses always no-store.

Search text and optional author are NFC trimmed <=200 code points each; empty
means absent. Text matches a literal case-insensitive substring of entry name
OR containing song author. Author matches only the containing song author.
For versions/fragments use their authorized song ancestor; for songs use their
own author. Null author does not match a nonempty author filter. Combine text,
author and other filters with AND; preserve entry-name ordering. Author is
included in cursor binding and available in the HTML search form. source_key only yousician; entry_type
song/version/fragment; instrument UUID must be published guitar/piano. Unknown
registered-reference filter values ->422. Private ancestor missing/foreign ->404.
Ancestry excludes self. page_size integer 1–100 default 50. Cursors <=2048 chars
bind actor/operation/normalized filters/order with 15-minute expiry; malformed,
changed, expired or wrong-binding ->422 invalid_input. Sort search by name C
collation/UUID ascending; children by created_at/UUID ascending. No totals or
stable snapshot guarantee. Entry IDs always resolve inside actor's personal
catalog. Tombstones readable by detail/ancestors but absent from active lists.

JSON mutation body max 16384 bytes, exact application/json with optional UTF-8
charset, query max 8192 bytes. Unsafe requests require existing same-origin/
Fetch Metadata rules and X-CSRF-Token matching session-bound CSRF. No token
endpoint: JSON clients use the token rendered into authenticated catalog forms.
Enforce streamed and declared size bounds before deserialization. No body on GET.

## HTML routes

GET /catalog has the entry-search filters above; show root browse when no
filters, links to details and create-song form. GET /catalog/entries/new accepts
only optional parent_entry_id and instrument_id; derives type from authorized
parent, or offers root instrument. GET /catalog/entries/{entry_id} shows detail,
breadcrumbs, children and action forms. GET /catalog/entries/{entry_id}/edit
shows editable fields. POST /catalog/entries creates; POST
/catalog/entries/{entry_id}/edit, /move, /tombstone perform the named actions.
All success writes redirect 303 to /catalog/entries/{id}. Forms are strict
form-urlencoded <=16384 bytes, include csrf and expected_catalog_version;
existing target forms also expected_entry_version. Render separate typed
metadata controls, never a free-form JSON metadata textbox. Parent/scope create
fields match JSON; edit only name and exact metadata replacement. Move supplies
new_parent_entry_id; tombstone no editable fields. No query inputs on POST.
Missing session on private HTML GET ->303 /login; on writes/API ->401.
Conflict pages show a fixed message and reload link without echoing submitted
input. Home adds a catalog link without changing authentication behavior.

## Failure and header contract

Reuse existing error envelope {error:{code,message,correlation_id}} and fixed
safe messages. 401 unauthenticated; 403 forbidden for provenance/CSRF; 404
resource_not_found for missing/foreign/wrong-parent private selectors; 409
conflict for owned lifecycle/graph incompatibility; 412 version_conflict; 428
precondition_required; 422 invalid_input; 413 payload_too_large; 415
unsupported_media_type; 503 unavailable; unexpected 500 generic internal_error.
Unsupported methods ->405 with Allow and no dispatch. Bodyless GET input
violations ->422. Preserve existing 404/405 framework behavior outside new routes.
Authentication and unsafe provenance/size/representation checks precede parsing;
authorize all well-shaped private selectors before existence-dependent domain
checks and preconditions. HTML GET unauthenticated redirect remains narrow.
Every response has no-store/correlation/security headers from existing policy;
HTML receives exact nonce CSP and form policy. No 304, credentialed CORS,
private cache validators reused across actors, or error-detail leakage.

## Scoped owner decision

Approve this inventory, field sets, errors/bounds, aggregate ETag plus entry
precondition, HTML workflow and the scoped catalog defaults in design.md.
ADR-010 remains proposed for unrelated practice/characteristic/statistic work.
No deployment or residual risk approval is requested.

## Exact reference-definition representation

Replace the abstract definition notation above with this closed response shape:
sources items have key,version,definition only. definition contains types (array
of type keys), parent_rules (array of {parent_type: string|null,child_type:string}),
metadata_rules (array of {entry_type:string,fields:Field[]}), and
practiceable_types (array of type keys). Field is exactly {key:string,
kind:"text"|"integer",nullable:boolean,required_on_create:boolean,
required_on_replace:boolean,min:integer|null,max:integer|null,
default:string|integer|null}. Text bounds count normalized code points; integer
bounds are inclusive. A null default with required_on_create=true means no
creation default (level); null otherwise is the nullable default. No enum,
expression, nested schema, extra keys or executable content. All arrays have
fixed v1 bounds: types=3, parent_rules=3, metadata_rules=3, fields<=2,
practiceable_types=2. Instruments has exactly 2 items, sources exactly 1.

V1 types are song/version/fragment. Rules are null->song, song->version,
version->fragment. Song author is text nullable, optional create/required replace,
1–200 when non-null, default null. Version level integer non-null required on
create/replace, 0–15, default null meaning absent default. Fragment
length_seconds integer nullable optional create/required replace, 1–2147483647,
default null; notes_count integer non-null optional create/required replace,
0–2147483647, default 0. Name remains a common entry field, 1–200 NFC trimmed
code points. Practiceable types are version and fragment.

## Browser policy approval amendment

Owner decision also includes proposed ADR-013, limited to successful authenticated
200 HTML GET /catalog, /catalog/entries/new, /catalog/entries/{entry_id}, and
/catalog/entries/{entry_id}/edit: Referrer-Policy same-origin. All failures and
other response classes preserve existing policy. Same-origin referrers may
include catalog queries; do not log raw URLs/queries/Referer at any enabled sink.
No third-party assets or cross-origin referrer are permitted. See the ADR for
privacy implications and required verification.

## Cursor key and snapshot details

Cursor integrity does not conceal its readable encoded payload. Treat it as
private; never log or send it to another origin. Maximum decoded payload 1500
bytes. Replacing the sole active key immediately invalidates all existing
cursors (generic 422 invalid_input); expiry equality is expired. Multi-statement
navigation reads share one READ ONLY REPEATABLE READ snapshot. Pagination
across requests still has no snapshot guarantee.

## Owner approval — 2026-10-26

The owner approved the MVP contract after adding author search: “Great, looks
good for MVP, approved”. This approves the exact issue-11 contract including
author search, scoped catalog defaults and ADR-013 as presented. Independent
author-search design/security/test delta review passed. Implementation and
verification may proceed; deployment and unrelated ADR-010 work are not included.
