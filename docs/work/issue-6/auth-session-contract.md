# Web authentication and session contract — Issue #6

Status: independently reviewed design; ADR-011 amendments approved by the owner
on 2026-10-22 and reconciled in ADR-008/009. Existing ADR-007 choices are
preserved. This is documentation, not running authentication or a deployed API.

## 1. Boundaries and approved baseline

Google only, Authorization Code with PKCE S256, scopes exactly openid/profile;
no email, offline access or refresh token. Verified (issuer, subject), never name,
email or domain, identifies the internal user. Google ID/access tokens and code
are discarded after validation; no browser token or localStorage credential.
Use trusted identity public ports; app_runtime never accesses control tables
or assumes app_owner. No linking/provider changes, user admin session controls,
mobile/Telegram tokens or destructive-action endpoints exist in this increment.
Those cannot inherit a generic reauthentication permission from this design.

Session cookie: __Host-you_story_session; Secure; HttpOnly; SameSite=Lax;
Path=/; no Domain; Max-Age=2592000, matching Expires permitted. No insecure
production fallback. Server deadlines remain authoritative. Production origin
comes from validated deployment configuration, not request/proxy headers.
Every environment has a distinct Google client and exact registered callback.

## 2. Login surface and temporary browser binding

GET /login renders a no-store form; no user/tenant/catalog/session is created.
It may issue __Host-you_story_login, a signed fixed-schema browser-binding
envelope carrying version=1, a 32-byte CSPRNG unpadded-base64url nonce, integer
issued_at and expires_at=issued_at+600, plus HMAC-SHA256 with the preauth key and
separate domain label you-story:login-cookie:v1. Use canonical length-prefixed
encoding, not ambiguous delimiter concatenation or arbitrary JSON. Cookie is
HttpOnly/Secure/SameSite=Lax/Path=/, no Domain, initial Max-Age=600. Binder digest
means the nonce digest, not the envelope serialization. Verify signature and
shape and original expiry on GET/start/callback; cap cookie length at 512 bytes.
Auth timestamps use DB UTC time; database unavailable means no new auth flow. It grants no product
access. A valid unexpired existing envelope is retained on rendering another form;
its signed expiry makes that deadline recoverable without another table.
Form includes a stateless pre-auth CSRF proof: HMAC-SHA256 with a deployment
secret, domain-separated over binder digest, canonical origin, issuance time and
600-second expiry; output is a signed fixed-schema token, not the binder itself.
The key is securely injected with no committed/default value; unavailable key
fails closed. Pre-auth proof is delivered only in the form, never URL/log/storage.
This proof does not replace authenticated-session CSRF or OIDC state/nonce/PKCE.

POST /auth/google/start: enforce ADR-009 origin/representation/body limits and
that proof plus binder before command dispatch. Body is form-urlencoded, max
4096 bytes; sole fields proof, destination and optional invitation token.
Reject duplicate/unknown fields. destination is an enum home/calendar/catalog,
never a URI; default home, server map to fixed relative paths. No query fragments,
external hosts, protocol-relative URLs or client-controlled callback/client IDs.
A currently authenticated browser receives already_authenticated (409) and keeps
its session; it must log out explicitly before another login. No silent account
switch or identity linking.

Serialize start/claim/finalize on the binder digest. Create one pending login
transaction per binder, invalidating any prior pending one ONLY if no unexpired
claimed or succeeded transaction exists for that binder. A claimed/succeeded
transaction blocks another start (generic login_in_progress 409) for its original
10-minute window. Failed transactions permit a fresh start. A claimed flow must
recheck its unexpired authoritative binding during atomic identity/session
finalization; expiry or loss of authority denies all identity/session writes.
A successful binder cannot issue a second session in that window, even if the
browser has not yet received its cookie. Logout clears the login binder as well
as its current session; expired binders get a new login form. A lost successful
response may therefore require waiting at most the remaining 10-minute window
before a fresh flow; no retry endpoint recovers raw tokens. Then redirect (303) to the fixed Google HTTPS authorize
endpoint. PKCE verifier/state/nonce each have 32 OS-CSPRNG bytes, encoded unpadded
base64url; state/nonce are 43 chars and PKCE S256 uses the verifier. Persist only
state/nonce/binder digests and PKCE challenge plus an authenticated-encrypted
PKCE verifier. Before encryption, trusted identity application code generates a
fresh transaction UUID using the server UUID generator; it is never accepted
from HTTP/form input. Envelope uses an established AEAD implementation with random
nonce and transaction ID/client ID as associated data; key injected securely,
separate from database credentials. No cryptographic implementation from scratch.
Pass that same UUID and ciphertext to start_web_login, which inserts the exact
UUID and returns it unchanged. A duplicate UUID fails without changing an
existing transaction; never upsert or substitute a different UUID after encryption.
If creation is retried with a new UUID, re-encrypt with that UUID's associated
data and a fresh AEAD nonce. No reservation or ciphertext-update function is added.
Return destination and optional invitation digest are server-bound to transaction.
Expiry is now+600 seconds, based on database time. Browser binder cookie is not
rotated during start, so tabs share it; newest pending start wins only before
a claim. Once claimed, no overlapping flow on that binder may start.
Do not extend the original binder expiry on render/start: if less than 10 minutes
remain, the transaction deadline is the earlier binder or transaction deadline;
a fresh binder is issued only on a fresh form after expiry. Preauth proof carries
the original binder expiry and cannot outlive it.
Reuse of a submitted start proof cannot restore an invalidated transaction.
Do not put invitation tokens or destination in state or redirect URLs.

## 3. Durable transaction exception (accepted ADR-011)

The pre-ADR-011 baseline listed five control-plane tables. Accepted ADR-011 adds
identity.login_transaction as a sixth: UUID, state_digest UNIQUE, nonce_digest,
binder_digest, PKCE challenge, encrypted_verifier, client_config_id,
invitation_digest nullable, destination enum, status, created_at/expires_at,
claimed_at nullable. No linked client-supplied user/tenant IDs. Status is pending
-> claimed -> succeeded or failed; pending -> expired/invalidate also terminal.
Claimed transactions can never return to pending, including timeout/crash.

This is an explicit reviewed amendment, not a disguised RLS exemption or reuse
of linked session rows as anonymous sessions. app_owner owns it; no tenant RLS;
PUBLIC/app_runtime have no direct table/sequence access. Section 8 additionally includes identity.auth_rate_limit as a seventh table
for cross-replica bounded counters. Update exact table and ACL inventories from
five to seven under the approved amendment. Existing
five remain unchanged. No generic state update or all-tenant function is added.

Narrow fixed security-definer contracts (fully qualified objects, fixed safe
search_path, explicit runtime execute only) create/invalidate a binder's pending
transaction; atomically claim a state digest with binder/expiry; return ONLY its
UUID, nonce digest, encrypted verifier, challenge and bound config/invitation/
destination needed by this callback; terminalize that claimed transaction.
Wrong state/binder/status/expiry return identical failure shapes and no payload.
No lookup by arbitrary user, listing or replay reset exists. A client-config
identifier must match deployment allowlist, never arbitrary provider metadata.

## 4. Callback and provider validation

GET /auth/google/callback is the only narrowly reviewed authentication GET
mutation exception to ADR-009: browsers return from Google with code/state on
an exact registered HTTPS URI. Pre-validation control-plane writes are limited to bounded rate counters,
transaction claim/terminalization and cleanup; no identity or session authority
is granted by them. Only a valid bound claim AND full OIDC validation may
bootstrap identity, issue session or enter the approved login-only catalog path; all other GET/HEAD/OPTIONS remain nonmutating.
HEAD cannot execute callback. GET /login sets only anti-CSRF browser binding.
No cookie-authenticated domain command is reachable through callback parameters.
Callback needs the matching binder, state and either code OR provider error;
reject duplicates, both, missing values, oversized query (>8192 bytes) and unknown
security fields. Permitted callback extras: scope, authuser, prompt, iss, error_description,
error_uri; ignore untrusted descriptions/URLs, never render or follow them.
If iss is supplied, require the configured Google canonical issuer.

Atomically claim before contacting token endpoint. Invalid binder/state does not
consume another browser's pending transaction. A valid claim consumes it even
if provider denial, token timeout or validation subsequently fails. Single claim
wins concurrent callbacks; all others fail with no code exchange/session side
effects. Do not retry ambiguous token exchanges; user starts a fresh flow.
Token exchange: fixed HTTPS Google token endpoint, exact configured redirect
and client, supplied authorization code plus decrypted matching PKCE verifier;
verify S256 challenge first. Timeouts 5 seconds connect/10 seconds overall, no
redirect following; TLS verification stays enabled. Never accept caller URLs.

Validate ID token via maintained OIDC library: RS256 only with recognized kid,
Google HTTPS JWKS, signature, issuer exactly https://accounts.google.com or
accounts.google.com normalized to the canonical HTTPS issuer, audience includes
our exact client ID, and azp equals it when present or multiple audiences exist
(require azp for multiple audiences). Require nonempty bounded subject, exp,
iat; nonce digest matches transaction. Reject unsigned, symmetric-algorithm,
expired, future-issued or not-yet-valid tokens (nbf when present); clock leeway
60 seconds: exp is valid only when now < exp+60; iat/nbf may be at most now+60;
iat must be >= now-660. Require NumericDate finite integers excluding booleans,
array/string audiences of valid nonempty client IDs and strict claim types. JWKS cache at most
one hour or shorter provider cache max-age; unknown kid triggers one bounded
refresh, with no token-provided jku/x5u fetch. Do not use stale keys beyond TTL;
refresh/network failure fails closed. Subject max 255 ASCII bytes; display name
is optional escaped presentation only, max 200 normalized Unicode code points.
OIDC nonce and state are not substitutes for each other.

All callback failures return one no-store generic failure page with a fixed
retry link to /login, no automatic restart and no raw exception/provider detail.
Do not clear a new binder during an old callback; invalid/old callbacks cannot
change a currently valid session cookie or revoke a victim session. Never put
code, state, tokens or invitation in redirected paths, error bodies or telemetry.

## 5. Invitations, identity bootstrap and catalog readiness

Generate invitation bearer tokens as 32 OS-CSPRNG bytes, digest-only in invitation
storage, one use, expiry 24 hours, canonical Google issuer permitted. Expiry equality is invalid;
issuer/subject preallowlist entries are controlled setup data, not email rules. Distribution
is out of band by the controlled owner process; no invitation admin/send endpoint
or new email collection. Accept token only via login-start POST. Do not consume
it at start/provider failure. Callback passes its bound digest to approved
bootstrap only after provider validation. Known active identity may log in
without consuming a provided invitation; the invitation remains available.

For new identity: a preallowlisted issuer/subject or valid unexpired matching
invitation is required. Bootstrap atomically consumes invitation where needed and
creates exactly one user/personal tenant/external identity; otherwise none. Keep
ADR-008 same-consumed-invitation/same-subject idempotent bootstrap semantics;
this does not authorize replaying a claimed OIDC transaction or issuing another
session from a replay. Different subjects racing one invitation cannot both win.
Disabled identity/user/tenant always fails and cannot be revived by invitation.
Allowlist removal blocks unknown/new provisioning, not existing active users;
disable account or revoke sessions for existing access withdrawal. No product
user command manages allowlist, invitation or disabling in MVP.

Identity bootstrap (or existing identity resolution), invitation consumption
where needed, session creation, issuance-limit consumption and successful
transaction finalization MUST share one database transaction using narrowly
reviewed identity owner functions; a public caller cannot commit bootstrap alone
and continue issuance from an unvalidated tuple. Any failure rolls back these
identity/session/invitation writes. A claim is committed separately before
network exchange; after issuance failure it remains consumed and is terminalized
as failed in a separate bounded cleanup/error transaction. Login-transaction claim remains terminally consumed independently;
a fresh login is safe after failure. Do not return a cookie before commit.
If an unavoidable post-commit network/cookie failure loses the token, the orphan
session grants nothing without its bearer; a fresh login creates an independent
session, subject to limits. No raw token is stored for retry recovery.

Catalog provisioning remains a SEPARATE tenant-context transaction through
ensure_personal_catalog, first or pending-account login callbacks ONLY. Exactly
one catalog/grant pair; success then conditional identity mark-ready. Failure
leaves active identity/session and catalog_pending; minimal home/profile/logout
work, catalog/practice fail provisioning_pending (409), no automatic per-request
retry, worker or retry endpoint. A later fresh login for pending account retries.
Catalog failure does not unconsume identity invitation or pretend the whole
identity/catalog flow rolled back. Disabled accounts never become ready/active.

## 6. Session issuance, validation and revocation

Session bearer is 32 OS-CSPRNG bytes, unpadded base64url (43 chars), digest stored
using SHA256(domain || zero || raw bytes); never bearer-equivalent reversible
session storage. Cookie parser accepts exactly one correctly shaped cookie;
duplicate/ambiguous names, malformed/empty/oversized values are invalid auth.
Do not accept session bearer in URL, form, Authorization header or storage.

Session row has server UUID, user/tenant/identity linkage, digest, created_at,
last_seen_at, absolute_expires_at=created_at+30 days, revoked_at nullable,
CSRF digest. Database time is authoritative; validity requires now < absolute
expiry AND now < last_seen_at+7 days, no revocation and all linked lifecycle
states active. Exact equality is expired, no expiry leeway. Resolve/touch is one
atomic conditional owner-function operation; failed lookup returns no fields and
never refreshes inactivity. Successful authenticated product requests update
last_seen_at to monotonic current database time, never change created/absolute
expiry. Assets, anonymous probes and unauthenticated/failed-session calls do not
touch; valid-auth later domain denials do touch. No sliding cookie Max-Age renewal;
authenticated responses do not reset expiry to another 30 days.

Multiple device sessions are independent. Proposed bounded active limit is 10
per user, enforced under a user lock; successful issuance at limit revokes the
oldest active session deterministically (created_at/UUID), except the newly issued
session, in the issuance transaction. No session-list/admin UI in MVP. Browser
session fixation is defeated by generating new bearer at successful login; never
promote a login binder/session ID from request. Invalid/expired old cookie is
ignored as identity input, not reassigned or revived. Active logged-in start is
rejected as in section 2; an in-flight callback discovering an authenticated
browser fails already_authenticated without switching/revoking it.

POST /logout is ADR-009 CSRF/origin-protected; revokes ONLY current session,
clears same scoped cookie using Max-Age=0 and an expired Expires. No GET logout.
After revoke commit, subsequent resolver operations must fail. A missing/invalid
session on repeat logout gets generic unauthenticated/no mutation (browser may
show signed-out page); arbitrary request cannot revoke another session.
An already-authorized in-flight domain transaction may commit if it linearized
before revocation. This is not global cancellation of work. A resolver/touch
that races logout cannot un-revoke or extend a revoked session; write predicates
must recheck revocation/deadlines atomically. Future privilege changes must rotate
session+CSRF and revoke old credentials atomically, but no privilege-change API
is introduced now.

## 7. CSRF token re-rendering (accepted ADR-009 amendment)

ADR-009 requires a stable session token delivered in authenticated HTML and only
its digest persisted, but independently random raw tokens cannot be reconstructed
for later page renders from that digest. Propose replacing only its generation
rule: derive 32 bytes via standard HKDF-SHA256 from the raw 32-byte CSPRNG session
bearer, salt=internal session UUID bytes, info=you-story:csrf:v1. Encode unpadded
base64url; persist/compare the existing domain-separated session-bound CSRF digest.
Raw token exists transiently only during server rendering/request validation and
in the approved hidden HTML field. It is NOT stored in another cookie, URL,
localStorage, token endpoint or database plaintext. The server already receives
bearer cookie on valid requests; learning CSRF output must not reveal the bearer.
Rotation changes bearer and session UUID, hence CSRF; expiration/revocation
invalidates it. This is a reviewed cryptographic design amendment, not a claim
that HKDF output is a new independent OS-CSPRNG draw. All other ADR-009 controls,
fixed-length comparison, token formatting and route applicability stay intact.

## 8. Abuse bounds, operational dependency and logs

Rate counters use fixed windows aligned to database Unix time, interval
[window_start,window_start+window_size), with equality starting a new window.
For a start request, consume IP-start (20/10min) before proof checks; after valid
binder/proof consume binder-start (5/10min), then create transaction. For callback,
consume IP-callback (20/10min) before claim. Malformed/failed/replayed callbacks
consume that IP budget but never a verified user's budget. A denied scope stops
processing; later scopes are untouched. The denying counter increments to N+1
(and may saturate there), no writes to identity authority. Retry-After is the
ceiling seconds to that denying window's end, at least 1; use the same public
429 shape regardless of underlying private state.

After validated OIDC and a locked invitation lookup identifies a bound candidate,
consume invitation-attempt budget (10/hour) before deciding its eligibility; use
the bound invitation digest, not unverified subject. Invalid supplied digest has
the same failure and may consume its own bucket, never another invitation/user.
This budget is consumed on attempted new provisioning success OR failure to
avoid inconsistent failure-only counters. Existing active identities ignoring
an invitation do not consume its budget. Only after provider+account validation
consume user-issuance budget (10/10min) in the final identity/session transaction;
a rollback does not consume it. Limits do not revoke or lock out existing sessions.
Do not trust arbitrary forwarding headers or account names to select limit keys.

Shared atomic state across replicas is identity.auth_rate_limit: scope enum
(IP-start/IP-callback/binder-start/invitation-attempt/user-issuance), keyed subject
digest, DB-derived window_start, saturated count, expires_at, unique scope/key/
window. IP keys use an injected deployment HMAC key; no raw IP storage. This
seventh table uses the same app_owner/no-direct-runtime/no-RLS exception; only a
fixed consume function with validated scope/derived window, no counter-list/reset
API. Subject key derivation is confined to trusted identity code, not product
input. No Redis service. Missing limiter/key/store fails login with bounded 503;
normal valid-session DB resolution needs neither provider nor rate counter.

Cleanup is lazy eligibility, NOT a guaranteed wall-clock erasure deadline:
pending/claimed rows expire at their original 10-minute deadline regardless of
cleanup. Claim atomically returns then clears persisted encrypted_verifier so a
crash leaves no stored verifier. The sole returned ciphertext lives only during
the bounded callback; no new function can retrieve it after claim. Expired claimed
rows are terminalized/erased on cleanup, never reopened. Terminal/expired rows
become deletion-eligible 24 hours after their original expiry; counter rows after
window-end+24h. With zero traffic, non-secret tombstones may remain longer; do not
promise deletion at exactly 24h. On valid start/callback operations, process at
most 100 indexed eligible transaction rows and 100 counter rows per operation.
No cleanup on ordinary GET login page or domain/session resolver requests.

Proposed hard admission caps per environment: 100000 transaction rows and 200000
counter rows, including tombstones. Fixed owner functions reserve capacity and
release it on deletion atomically via two protected reserved capacity rows in the
rate table, outside ordinary subject-window counters. No generic capacity-write
API, and actual row-count/reservation reconciliation is catalog-tested. Cleanup
runs before new admission; if still at capacity, reject new auth work with generic
503 rather than evict live transactions or bypass counters. Existing sessions
remain usable. Exact cap settings are engineering defaults, not product limits.
This bounds storage even after distributed abuse or a long no-traffic period.

Token endpoints/config/JWKS allow fixed Google hosts only. Read runtime secrets
via secure configuration (Google client secret where required, AEAD key and
preauth proof key); no values in source, logs, docs or environment dumps. Missing
credentials are an implementation environment prerequisite, not a reason to
weaken auth. Validate keys/config before serving auth routes.

No logging of query strings/callback URLs, code/state/nonce/verifier, session/
invitation/CSRF binders/tokens, ID/access tokens or provider payloads at app,
reverse-proxy, tracing or exception levels. Emit only event category, success/
failure class, random correlation ID and bounded counters; internal user UUID
only under approved telemetry/privacy policy. Referrer-Policy no-referrer and
no-store for all auth HTML/redirect/errors including 429/503. Do not place
provider images/URLs/scripts in rendered profile; names always escaped.
Retention and capacity follow the lazy eligibility/admission rules above; no
worker or hidden GET/domain provisioning side effect is added.

## 9. Finish boundary

No runtime, credentials, routes or infrastructure are created by this document.
Issue #6 design requirements are complete: the documented test design and
contract passed independent reviews, and owner-approved amendments are
reconciled with ADR-008/009. SEC-05 remains open for
MVP-07 implementation evidence and independent security/code review. Existing
ADR-008 tenant isolation and ADR-009 browser controls remain independent gates.

## 10. Privileged function inventory (proposed exact boundary)

All functions use schema-qualified identity names, safe fixed search_path,
app_owner ownership, revoke PUBLIC EXECUTE and explicit app_runtime grants only
for the external wrappers listed here. No function accepts current time, raw
session/invitation tokens or caller-selected user/tenant/owner IDs. Digest inputs
are fixed-length byte strings, config/destination/scope inputs closed enums.

| Runtime callable identity function | Typed input / least-result output |
| --- | --- |
| start_web_login | server_generated_transaction_uuid,binder_digest,state_digest,nonce_digest,challenge,encrypted_verifier,configured_client_id,invitation_digest?,destination,binder_expiry -> same transaction UUID+effective expiry OR generic start failure |
| claim_web_login | state_digest,binder_digest,configured_client_id -> claimed UUID+nonce digest+one encrypted verifier+challenge+bound config/invitation/destination; same generic failure for all invalid states |
| fail_web_login | claimed UUID+binder_digest -> terminal success/failure only; never resets claim |
| finish_web_login | claimed UUID+binder_digest,validated canonical issuer/subject,server session UUID+session_digest+csrf_digest -> minimal linked user/tenant/session UUIDs+provisioning state+absolute expiry OR generic failure |
| resolve_web_session | session_digest -> active minimal actor user/tenant/session tuple+provisioning state or identical invalid result; atomically touches if valid |
| revoke_web_session | session_digest -> success/invalid only, current linked session only |
| consume_auth_limit | closed scope+trusted derived subject digest -> allowed or limited+window-end; fixed window/cap from DB configuration |

finish_web_login alone orchestrates existing bootstrap helpers, invitation checks,
user issuance limit and session/finalization commit; internal low-level bootstrap
helpers are not independently executable by runtime after the narrowed amendment.
Terminal failure may be recorded separately after rollback, but never leaves a
new identity/invitation consumption committed without its session write.
Bounded cleanup/capacity reservation are private helpers of these wrappers, not
generic runtime delete/counter setter routines. Exact SQL overload signatures
and no-unlisted-functions tests must reconcile this named inventory. Existing
ADR-008 catalog-ready transition and context functions remain separately reviewed,
not broadened. Ordinary profile queries do not get privileged table access.
