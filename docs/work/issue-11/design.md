# Issue #11 implementation design

Status: owner-approved on 2026-10-26; independently reviewed; implemented,
with verification and implementation review recorded separately.
Baseline main `4c6ac30`; accepted ADR-002/003/005/008/009/011/012 apply.

## Scope and policy

Implement C03–C06 and Q02–Q06 from Issue #8 authorization-spec.md, restricted
to catalog behavior, together with yousician-content-schema.md. The latter's
exact normalization, integer bounds, null/default/replacement semantics are
normative. The owner accepted its version/fragment practiceability default;
song remains navigation only. Source definitions are immutable published data.
Roots bind the explicitly configured Yousician v1; children inherit their
parent's binding. No automatic upgrades or mixed-version moves.

The only catalog is the personal catalog provisioned by login. Queries never
provision it or alter session readiness. Missing catalog returns 404; HTML
explains readiness and links home without an automatic retry command.
No catalog name column exists: return {id,version}, and use fixed UI heading
“Personal catalog”, not a persisted or editable name. This intentionally narrows
the proposed Q02 response in Issue #8. Entry wire state is active/tombstoned;
map existing database literal tombstone explicitly.

## Module and persistence design

Catalog public typed commands/queries validate trusted actor provenance through
identity.public.require_validated_actor, including direct callers. Delivery uses
only public ports. Catalog application/domain own source-policy validation;
infrastructure owns all mappings/SQL. Existing login provisioning remains intact.
Extend exact composition, SQL-site, migration/schema and wheel manifests rather
than weakening foundation gates. Never edit applied migrations 000–005.

Add reviewed migration 006 owned solely by catalog: seed deterministic reference
IDs for Yousician, guitar/piano and immutable definition v1; add constraints for
NFC trimmed names, allowed metadata types/bounds, immutable entry scope fields
(catalog/instrument/type as well as existing identity/source binding), lifecycle
and immutable published definitions. Retain the existing explicit global-table
manifest and SELECT-only runtime reference grants; no new global RLS exception.
Songsterr is synthetic fixture data only, owner-seeded in tests and rolled back
or cleaned; no production seed, default, route or UI option. Tests exercise its
different graph through policy interfaces without making it user-creatable.

All private SQL retains explicit actor tenant predicates plus FORCE RLS. Verify
the own personal catalog and owner grant; no visibility/grant command exists.
All hierarchy mutations lock the actor catalog row first, authorize all supplied
private IDs next, compare expected versions, then lock entries in ascending UUID
order. Re-read lifecycle/ancestry under that gate. This serializes child creation,
move and tombstone. Move only within same catalog/source/instrument/definition,
reject cycles and excessive depth; root reparenting unsupported. Tombstone only
an active leaf; no delete, restore or cascade. Every successful mutation bumps
catalog once and existing target entry once. Failed writes roll back everything.
No subtree payloads or edits to descendants are accepted. Bounded lock timeout
and statement timeout map to safe 503; no automatic command retries.

Reads use one transaction with actor predicates throughout. Entry detail can
return an owned tombstone. Search and children return active entries only.
Ancestors return a bounded root-to-parent chain, with each ID authorized and no
recursive unbounded traversal. Search text matches literal case-insensitive substrings of entry name OR the
containing song author. A separate optional author filter matches only the
containing song author; combine it with text and all other filters using AND.
For songs use their own author; for versions/fragments resolve their song
through the authorized ancestry in the same read snapshot. Null author never
matches a nonempty author filter. No author is copied onto child metadata.
Normalize/trim both inputs with a 200-code-point limit; empty means absent.
Escape SQL LIKE wildcard syntax. Include normalized author in cursor binding. Ancestry filter includes proper descendants, not self.
Name sorting uses PostgreSQL C collation, UUID tie-break; children use created_at
then UUID because no editable sibling-order field exists. All query pages use
limit+1, no total counts. Use tenant-first indexes for name ordering and parent
lookup; bounded 3-level ancestry joins, parameterized SQL, max 100 returned rows,
2-second statement and lock timeouts. Performance must be measured with the
approved test-strategy workload; no service/infrastructure addition.

## Cursor and concurrency

Use canonical versioned HMAC-SHA256 cursor tokens with separately injected
>=32-byte key and domain label; no default key. Payload binds actor user/tenant,
operation, normalized filters, complete ordering tuple and 15-minute expiry.
Reject malformed, tampered, expired or different-binding tokens with one generic
422 invalid_input before a private query. Cursor max 2048 ASCII chars, strict
base64url/schema parsing; IDs/names in a cursor are never authority. No snapshot
pagination promise across concurrent edits. Missing signing setup fails feature
startup closed, never falls back to unsigned cursors.

Catalog aggregate ETag is the write concurrency gate; entry version is an
additional required target check. See exact wire preconditions in HTTP contract.
Authorize targets before comparing versions; foreign/missing must both yield
404 regardless of supplied stale versions. Server generates all identifiers,
timestamps, resulting versions and definition bindings. Unknown fields including
owner/tenant/visibility/state/type changes fail closed at every object level.

## Browser and security

Reuse #10 session, CSRF/provenance, outer response headers, nonce templates and
ADR-012 successful native-form policy. HTML forms carry server-rendered expected
versions and CSRF, validated as strictly as JSON; no session IDs or tenant fields.
Render catalog search/browse, entry details with breadcrumbs, create/edit/move/
tombstone forms and explicit accessible conflict/empty/error states. Stale forms
never auto-resubmit; require reload/review. Escape all names, author and error
content; no unsafe HTML, external assets, scripts or interpolated URLs.

No raw text, cursor, metadata or resource identifiers added to logs. Error bodies
use fixed safe messages and existing correlation IDs. No CORS, bearer-token,
sharing, bulk-create or privileged setup endpoint. SEC-01/06/07 implementation
evidence remains required. This design accepts no residual security risk.

## Gates

Independent architecture/security/test-design reviews precede production code.
Recorded owner approval covers only this catalog subset of ADR-010 proposals and exact
HTTP contract. Then implement, run canonical PostgreSQL/browser/property/API/
architecture/wheel checks, compare OpenAPI with unchanged baseline, and obtain
independent code/security/evidence reviews. Do not infer #11 runtime passes from
#10's 638 tests or mark the issue complete at design approval.

## Explicit browser-policy amendment

Reusing ADR-012 does not authorize additional native-form pages. Proposed
[ADR-013](../../architecture/decisions/013-personal-catalog-browser-policy.md)
adds only the four named successful authenticated catalog HTML page patterns
to same-origin Referrer-Policy. Catalog queries introduce same-origin referrer
privacy exposure absent from ADR-012's queryless pages. Owner approval must
explicitly include this amendment; log-sink canary and actual Chromium evidence
are mandatory before completion. No deployment/risk waiver is inferred.

## Review clarifications: storage, reads and cursor rotation

Migration constraints for every source are universal: valid ownership/FKs,
immutable scope, NFC common names, object metadata and terminal lifecycle.
Yousician graph/metadata limits are source-definition-specific, never unconditional
SQL checks on all entries. An owner-controlled validation trigger dispatches on
immutable published source/version to a reviewed policy; it rejects unknown
bindings rather than treating them as Yousician. The fixture installs a distinct
Songsterr policy/definition in the disposable DB and exercises persistence as
runtime without enabling production admission. No source-specific trigger bypass.
Definitions configure maximum depth; production Yousician is 3, fixture graph
has its own reviewed bound. This fixture-only seam is covered by exact schema/
artifact manifests and no production Songsterr default or creation workflow.

Multi-statement read queries run READ ONLY REPEATABLE READ transactions. Detail,
ancestor authorization and returned ancestry use the same snapshot; cycles and
missing authorized parents fail safely. Mutation UoWs retain READ COMMITTED plus
catalog-first locks. Tests interleave reads and moves across connections and
prove a coherent old/new tree, never a mixed chain.

HMAC cursor payloads are readable base64url, not encrypted; consumers must treat
them as private data and never log or send them to other origins. Encoded input
max 2048 ASCII bytes and decoded canonical payload max 1500 bytes; reject before
JSON parsing if exceeded. Only one active signing key: replacement invalidates
all outstanding cursors immediately with generic invalid_input. No key IDs,
old-key acceptance, silent fallback or automatic persistence. expiry <= server
UTC now is expired; issuance time is trusted server time. Fixed 15-minute TTL,
no refresh-on-read and no authority from cursor IDs. Private catalog logging
suppression and no cross-origin referrer are mandatory pre-exposure controls.

## Owner approval — 2026-10-26

The owner approved the MVP contract after adding author search: “Great, looks
good for MVP, approved”. This approves the exact issue-11 contract including
author search, scoped catalog defaults and ADR-013 as presented. Independent
author-search design/security/test delta review passed. Implementation and
verification may proceed; deployment and unrelated ADR-010 work are not included.
