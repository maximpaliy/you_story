# Issue #9 approved-authentication database delta

Status: independently reviewed database-delta design; architecture, security
and test-design reviews passed. Implementation evidence and final code/security
review remain required; no authentication HTTP exposure is approved here.
Baseline: merged foundation 000_security through 004_media; accepted ADR-011,
current ADR-008 and owner-approved Issue #6 auth-session-contract.md (2026-10-22).

## Corrected scope

The previous claim that Issue #6 is incomplete is stale: its design and ADR-011
amendments are now approved. That is not SEC-05 runtime closure. This delta
implements its database isolation/function foundation in #9 without exposing
login, callback, logout, profile, catalog, media or practice behavior. HTTP routes
remain exactly /live and /ready; no background process or auth CLI is added.

#9 owns the seven control-plane tables, exact privileged database wrappers,
linked session/CSRF storage, atomics, ACLs and real-role evidence. #10 owns
CSPRNG/digest/AEAD/HKDF implementations, signed browser binding, provider crypto,
allowlisted deployment configuration, cookie/CSRF/origin handling, HTTP routes,
trusted ActorContext issuance and login-only catalog orchestration. No production
ActorContext issuer exists in this database-only delta. Low-level SQL wrappers
are private identity infrastructure, not product ports accepting request fields.
No fake OIDC verification, generic SQL escape or caller-supplied actor is added.

Catalog ensure/readiness orchestration remains #10: it must use a reviewed
catalog public port, explicit predicate registry and ordinary tenant-context
transaction, then conditional identity ready transition. This delta supplies the
narrow identity ready function described below but never invokes it from health,
session resolution, middleware, worker or generic requests. ADR-008 provisioning
runtime evidence remains explicitly open until its catalog implementation passes.

## Additive schema and legacy safety

Add only identity-owned 005_identity.sql; do not rewrite/checksum-normalize any
000..004 artifact. Empty-to-head and a populated 004 fixture upgrade must pass.
No migration UPDATE/backfill/scan derives from existing tenant/control-plane
rows, weakens RLS or grants runtime table access. Existing sessions gain nullable
external_identity_id UUID and csrf_digest bytea; NULL means legacy-invalid and
resolver always fails without touching. New writes by finish require both;
CHECK csrf_digest IS NULL OR octet_length(csrf_digest)=32. Add composite unique
external_identity(id,user_id) and composite session FK (external_identity_id,
user_id) -> external_identity(id,user_id). This is a same-identity-schema FK,
not a cross-owner coupling. Existing null associations pass without backfill or rewriting them; ordinary
schema-constraint validation may scan existing rows; legacy sessions are never silently associated/revived.
The original session issued_at/created_at remain; newly issued rows set both
identically, last_seen_at identically and absolute expiry exactly +30 days.

Two new tables complete the exact seven control-plane inventory (user, tenant,
external_identity, invitation, login_session, login_transaction, auth_rate_limit).
All are app_owner-owned with no RLS by explicit ADR-011 exception and zero
PUBLIC/runtime direct table/sequence privileges. user_preference remains private
and forced-RLS; global catalog reference classifications are unchanged.

login_transaction columns: id UUID PK; state_digest bytea UNIQUE; nonce_digest,
binder_digest bytea; pkce_challenge text; encrypted_verifier bytea nullable;
client_config_id text; invitation_digest bytea nullable; destination text enum
home/calendar/catalog; status enum pending/claimed/succeeded/failed/expired/
invalidated; created_at, expires_at timestamptz; claimed_at timestamptz nullable.
All digests are exactly 32 bytes, challenge exactly 43 ASCII base64url characters,
config exactly google-web (trusted deployment maps this ID to its exact Google
client/callback); ciphertext is bounded 1..4096 bytes while present. No user/tenant
or decrypted verifier columns. Index binder_digest/status/expires_at and indexed
expiry/id cleanup ordering. Claimed/terminal rows never retain ciphertext.
Deadline is <= created_at+600 seconds; client binder deadline can only shorten it.

Auth_rate_limit columns: scope text, subject_digest bytea, window_start
timestamptz, count bigint, expires_at timestamptz; composite PK
(scope,subject_digest,window_start). Ordinary rows have a closed five-scope enum,
32-byte key, saturated count and DB-derived windows. Two private reserved rows
use distinct internal scope values __transaction_capacity/__counter_capacity,
fixed zero digest and epoch window, carrying actual reservation counts; only
owner helpers touch those rows. They are excluded from ordinary subject counters and cleanup but included in
the physical counter-table capacity count. New table initialization inserts only these two empty-table
rows. There is no eighth configuration/allowlist table. Add nullable
invitation.admission_kind text CHECK IN ('bearer','allowlist') and nullable
permitted_subject text. Legacy NULL kind is treated as bearer, without backfill.
New bearer entries have NULL permitted_subject; new allowlist entries have a
nonempty ASCII subject <=255 bytes and canonical issuer. Owner-controlled
allowlist entries retain a random opaque 32-byte token_digest but its raw token
is never distributed or used as admission. A partial unique index on
(issuer,permitted_subject) WHERE admission_kind='allowlist' AND consumed_at IS NULL
prevents competing pending admission entries. Existing consumed fields capture
its one-shot bootstrap just as for bearer invitations. finish with no supplied
invitation may select an unconsumed unexpired allowlist row bound to its fully
validated issuer/subject and consume it in the same bootstrap/session atomic
unit. No precreated user/tenant or nullable identity linkage is necessary. Known
active identities need neither admission path. Only controlled owner setup may
create/alter these records; runtime has no admission-management function and
finish accepts no allowlisted boolean or arbitrary user/tenant target. This
implements approved unknown-subject preallowlisting inside the existing identity
admission store and needs explicit peer review of the exact DDL checks.

## Exact external wrapper contracts

All wrappers are identity-owned SECURITY DEFINER, fixed
search_path=pg_catalog,identity, schema-qualified references and explicit
PUBLIC EXECUTE revoke. Only app_runtime receives each exact signature; no
unlisted overload, helper EXECUTE or generic setter/query function is allowed.
Existing current_tenant_id remains security-invoker, not part of the seven.
Digest inputs are bytea validated at 32 bytes; trusted server UUIDs are never
interpreted as proof of authorization. Input current-time is never accepted.

| Name and SQL input types | Least result |
| --- | --- |
| start_web_login(uuid,bytea,bytea,bytea,text,bytea,text,bytea,text,timestamptz) | result text (ok/invalid/in_progress/unavailable), id uuid, expires_at timestamptz; ID/expiry only on ok |
| claim_web_login(bytea,bytea,text) | id uuid, nonce_digest bytea, encrypted_verifier bytea, pkce_challenge text, client_config_id text, invitation_digest bytea, destination text; zero rows on generic failure |
| fail_web_login(uuid,bytea) | boolean; only changes matching claimed transaction to failed, never reopens |
| finish_web_login(uuid,bytea,text,text,uuid,bytea,bytea) | result text (ok/invalid/limited/unavailable), user_id uuid, tenant_id uuid, session_id uuid, provisioning_state text, absolute_expires_at timestamptz, window_end timestamptz; success fields only on ok, window_end only on limited |
| resolve_web_session(bytea) | user_id uuid, tenant_id uuid, session_id uuid, provisioning_state text, absolute_expires_at timestamptz; zero rows for every invalid state |
| revoke_web_session(bytea) | boolean; revokes matching linked active current session only |
| consume_auth_limit(text,bytea) | allowed boolean, window_end timestamptz; no current count or account metadata |

Argument order for start is transaction UUID,binder,state,nonce digests,
challenge,ciphertext,config ID,optional invitation digest,destination,binder expiry.
Finish order is claimed UUID,binder digest,canonical validated issuer,subject,
new server session UUID,session digest,CSRF digest. Issuer must be the canonical
https://accounts.google.com; subject nonempty ASCII <=255 bytes. This validation
is defense-in-depth, not OIDC verification. Private low-level bootstrap cannot be
independently runtime called. Scope/config/destination errors return the wrapper
generic invalid result (or the same empty failure shape where specified), never
echoing supplied values.

Separate mark_catalog_ready(bytea) -> boolean accepts only a valid session digest,
resolves linked active identity/user/tenant under lock, derives the target itself,
and conditionally changes catalog_pending to ready (idempotent at ready). It has
no caller user/tenant/state target and cannot revive disabled state. Its private
adapter must derive this digest from validated identity session evidence, never
request JSON. It does not prove catalog completion itself: trusted login-only
orchestration must invoke it only after catalog success. This has the same
compromised-runtime trust boundary as other owner wrappers, not a generic state
setter. Final review must explicitly approve this narrowed targeting signature.

## Clock, locking, transitions and bounded state

Use database UTC time from clock_timestamp() once after acquiring locks per
operation, refreshing it after any further potentially blocking row lock before
checking authority/expiry (including races with controlled owner disabling).
Never trust caller time or a transaction-start timestamp that can
pre-date lock waiting. Equality is expired. Acquire a fixed transaction-scoped
PostgreSQL advisory auth-control lock before any control-plane/capacity mutation;
all external wrappers and private helpers use the same serialization rule.
This intentionally coarse first-increment lock gives deterministic binder,
invitation, user/session, issuance and capacity linearization. Local bounded
lock_timeout/statement_timeout limit waiting; failure grants no authority. No
network call occurs while held. Refining concurrency later needs independent
review; bypassing this lock from any wrapper fails tests. Owner setup is outside
the running application and cannot race fixture mutations in evidence tests.

Start blocks an unexpired claimed/succeeded binder,
invalidates prior pending for that binder, reserves capacity and inserts exact
provided UUID. Duplicate UUID/state fails with no replacement/mutation of prior
row. Deadline min(DBnow+600,binder_expiry), requiring future expiry and <=10min.
Failure rolls back invalidation/reservation as well as insert. Claim atomically
matches pending state,binder,config and expiry, copies ciphertext into least
result then clears it and sets claimed_at/status before returning. A second
claim returns no payload; fail cannot reset or retrieve ciphertext.

Finish rechecks claimed binder and original unexpired authority after lock;
looks up existing active identity plus active user/tenant, ignoring invitation
for known active identity. Disabled linkage always fails. Unknown identity
requires matching unexpired bearer invitation or issuer/subject-bound owner
allowlist admission; invitation eligibility and new triple
creation are atomic. IDs for new user/tenant/external identity are server DB UUID
values; no HTTP-target IDs. Same consumed invitation+same issuer/subject may
resolve the existing triple but never replays an already-finished transaction.
Conflicting/replayed/wrong-issuer invitations have one invalid result with all
authority/window fields NULL.

Invited attempt budget is consumed for new-provisioning attempts, before final
eligibility. Preserve this budget even on ordinary eligibility failure using a
nested exception subtransaction for subsequent bootstrap/session writes. Final
issuance budget, identity/invitation changes, new linked session and transaction
success all share that inner atomic unit: any later failure rolls those back.
Normal failure returns its safe discriminant with no authority fields; claim remains consumed and fail_web_login terminalizes
in a separate transaction. Infrastructure transaction abort cannot promise
persisted attempt counters; it fails closed and never commits authority.

Finish derives 30-day absolute/7-day idle validity from DBnow. Under serialized
user issuance it counts only currently valid linked active sessions; at >=10
revokes deterministic oldest(created_at,id) until admitting new session keeps
at most ten. Session UUID/digest conflicts fail entire issuance atomically.
Resolve requires non-null exact external identity linkage and CSRF digest,
active identity/user/tenant, no revocation, now<absolute and now<last_seen+7days;
then atomically touches monotonic last_seen without changing absolute/created.
Invalid/legacy session gives zero fields/no touch. Revoke linearizes with resolve
and sets revoked_at once; resolver never un-revokes. No cleanup/provisioning/rate
counter side effect occurs on resolve/revoke/ready marking.

Counters: IP-start/IP-callback 20/600s, binder-start 5/600s,
invitation-attempt 10/3600s, user-issuance 10/600s. Epoch-aligned windows,
saturate at limit+1; equality enters next window, expires_at window-end+24h.
Private finish calls use bound invitation/user IDs transformed to trusted digest
keys; public limiter cannot reset/list/delete counters. Hard caps 100000 login
transaction rows and 200000 total counter-table rows include tombstones and its
two protected reserved rows; counter reservation starts at two. Protected
reservations reconcile to actual rows. Before admission clean at most 100
indexed eligible transactions and 100 counters, freeing matching reservations.
Transactions become deletion eligible original expires_at+24h, counters at
window-end+24h; cleanup may terminalize expired claims and always clear expired
ciphertext, never reopen. Still-full admission fails safely (adapter maps to
503), no live-row eviction, no unbounded table scan/cleanup. Sessions still
resolve. Cleanup occurs only consume_auth_limit scopes IP-start/IP-callback, once
before each start/callback operation's remaining stages. Other scopes and
start/claim/finish/fail/resolve/revoke/ready do not perform cleanup, avoiding
multiple 100-row batches inside one HTTP operation. Direct private SQL calls
without the IP scope do not get cleanup but still enforce capacity. No cleanup
on /live,/ready, ordinary session resolver or product GET.

## Migration/review and completion

Manifest explicitly registers new CP rows, additive columns/FKs, exact function
signatures/security/search-path/ACLs, reserved row seeds and new migration head.
Control-plane DDL constraints use nullable legacy-compatible checks; no tenant
history/backfill occurs. Tests retain original checksums and populate legacy
session before upgrade to prove unchanged bytes/invalid resolution. Recovery is
transaction rollback then rerun 005; no downgrade deleting issued credentials.

Security/code review must reconcile actual wrappers and all evidence, not infer
SEC-01 or SEC-05 closure from schema creation. #10-only crypto/HTTP/browser and
catalog orchestration evidence remain explicitly pending. No statement in this
delta claims those later requirements passed.

### Test clock boundary

A private owner-only `_auth_now()` helper may wrap clock_timestamp for
deterministic fixture tests. It is not runtime-executable, has no caller time
argument and is always called after lock acquisition. The disposable owner test
fixture may temporarily replace this helper to arrange exact boundary instants,
then restore its reviewed body; catalog/function-definition checks must prove
restoration. Production migration body always uses real database time. No test
clock setting or public override ships in runtime code.

The future #10 identity public ready command still requires validated immutable
ActorContext and checks its actor/tenant against validated session-digest linkage
before invoking private mark_catalog_ready. The digest-targeted DB wrapper is
not a public digest-ready API or authority to bypass catalog success.

Same-consumed-invitation/same-subject idempotence is the existing active identity
path: it resolves the original triple and does not reconsume invitation or its
attempt budget. It still requires a different valid claimed transaction to issue
a new independent session. Neither an invitation retry nor a finished transaction
can replay a session issuance. No stand-alone bootstrap function is exposed.

### Safe failure representation and durable budgets

The exact start and finish result discriminants above represent already-approved
409/429/503/generic-failure cases internally; they are not new HTTP operations
or authority/account metadata. Start invalid states have NULL ID/expiry;
in_progress carries no binder/state detail; unavailable carries no capacity count.
Every finish identity/invitation/linkage/expired-claim failure is `invalid` with
all other fields NULL. Invitation-attempt or user-issuance denial is `limited`
with only denying window_end (no scope/key/count); capacity denial is unavailable
with no other fields. Successful finish has the original least authority tuple
and NULL window_end. Ordinary denied finish returns normally, preserving the
outer attempt budget and committing no inner authority changes. Trusted caller
commits normal failure then invokes fail in a separate transaction; it must not
rollback normal denial as though it were a SQL exception. Infrastructure SQL
errors still abort safely and cannot promise counter persistence.

consume_auth_limit returns allowed/window_end normally; zero rows means
unavailable (capacity/store failure) rather than inventing a window or skipping
limits. No failure includes issuer, subject, token/digest, account existence,
provisioning state or user/tenant/session identifiers. #10 maps only these safe
categories to approved HTTP outcomes. Independent security/architecture review
must agree this concrete representation matches the approved contract before
implementation begins.

Bounded transaction cleanup selects at most 100 total rows across two indexed
candidate classes: expired pending/claimed rows needing ciphertext clearing and
rows whose original expiry is at least 24h old eligible for deletion. Ordered
expiry/ID selection combines candidates then limits the total to 100, not 100
per class. Only actual deletion releases transaction reservations; mere terminal
status/ciphertext clearing does not. Partial expiry indexes cover pending/claimed
rows; ordinary counter expiration is separately indexed and limited to 100.
