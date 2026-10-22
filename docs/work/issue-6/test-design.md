# Issue #6 authentication/session test design

Status: design only; no executable application tests run. Oracle is
[auth-session-contract.md](auth-session-contract.md), sections 1–9; proposed
amendments require ADR-011 acceptance before implementing them.

## Fixtures and trusted layers

Use real PostgreSQL app_owner migrations/app_runtime functions, FORCE RLS for
private domain tables, and exact auth-control table/function ACL inventories.
Provider harness signs ID tokens with controlled RS256 keys and exposes bounded
fake HTTPS token/JWKS endpoints; no live Google credentials needed to validate
negative cases. Real browser runs login/callback navigation under HTTPS cookie
semantics with canonical-origin proxy configuration. Unit/public-port tests
call identity use cases directly, not merely routes. HTTP tests use production
middleware, not mocks that skip CSRF/origin/auth parsing. Time controls use an
injected test clock through supported test harness, never a production override
or caller-provided timestamps; confirm expiry predicates against DB time.

Actors A/B: active allowlisted identity, unknown identity, disabled identity/user/
tenant variants, valid/expired/consumed/wrong-issuer invitation, catalog_pending
and ready tenants. Browsers X/Y have independent binders; two tabs share X;
transactions T1/T2, active/revoked/idle/absolute-expired sessions, two devices and
10-session-cap boundary. Use controlled code exchange barriers and DB transaction
barriers to enumerate race orders, not sleeps.

For each denial assert response class, no Set-Cookie session replacement,
unchanged identity/session/catalog state except explicitly documented terminal
transaction/counter writes. No orphan identity/grant or secret in response/logs.
For success assert issuer/subject ownership, exact DB rows and versions/state,
actual subsequent authenticated request and role-visible isolation. PID/HTTP200
alone is never sufficient evidence. Capture sanitized proxy, HTTP, DB and trace
canaries to detect secret leakage without storing raw test tokens in evidence.

## Traceable case groups

| ID / contract | Positive control and adverse cases | Layer / required oracle |
| --- | --- | --- |
| AUTH6-01 / 1,2 | Correct scopes/client/HTTPS callback; reject email/offline scope expansion, caller callback/client URLs, proxy Host spoofing and missing config | config/static + HTTP; exact allowlist and fail closed, no redirect to untrusted host |
| AUTH6-02 / 2 | Render login form/binder, valid same-origin POST starts once; missing/duplicate/mismatched/expired proof, Y binder, cross-origin/plaintext/multipart/oversize body deny | public port/HTTP/browser; no pending row before valid proof; no identity mutation on GET form |
| AUTH6-03 / 2,3 | T2 start invalidates T1 for same binder; independent Y unaffected; two tabs share binding, newest pending transaction only | HTTP + DB; valid newest only, old callback cannot clear new cookie or transaction |
| AUTH6-04 / 3,4 | One bound claim succeeds; same/missing/wrong state, absent/wrong binder, expired/invalidated/claimed state deny; two callbacks race and crash after claim | public port/DB + HTTP; at most one exchange and session, no reset to pending; fresh flow required |
| AUTH6-05 / 4 | Valid code+PKCE returns signed token; wrong verifier/challenge, redirect/client mismatch, token endpoint redirect/timeout/TLS errors deny | provider harness + HTTP; bounded exchange, no blind retry or session |
| AUTH6-06 / 4 | RS256 recognized kid accepted; alg none/HS256/wrong signature/unknown key/malicious jku or x5u, stale cache and refresh failure deny | library integration; no attacker endpoint fetch, one bounded key refresh, correct TTL |
| AUTH6-07 / 4 | Canonical/alias issuer normalizes; wrong issuer/audience/azp, multi-aud missing azp, missing subject/exp/iat/nonce, future iat/nbf, old iat and expired exp rejected | token harness; exact leeway boundary +/-1 second with documented expected results |
| AUTH6-08 / 4 | code or provider-denial shape; duplicate state/code, code+error, oversized query, unknown security fields rejected; descriptions/error_uri escaped/ignored | HTTP/browser; generic no-store retry page, no raw detail/URL redirect and no session cookie alteration |
| AUTH6-09 / 5 | New valid invite provisions identity triple once, preallowlisted subject provisions without invite; expired/replayed/wrong-issuer token, disabled variants, conflicting identities deny | DB/public port; atomic identity+session commit or no writes, one winner for A/B competing invite |
| AUTH6-10 / 5 | Same consumed invite+subject bootstrap idempotent internal result, no OIDC transaction replay; existing identity ignores invite without consuming it | DB/HTTP; unique mapping, no duplicate session for replayed callback; fresh legitimate login creates independent device session |
| AUTH6-11 / 5 | Catalog-ready login has no ensure call; pending login ensures pair then marks ready; failures before/after pair preserve pending and session | public ports + DB; separate identity/catalog transactions, exactly one pair under concurrent pending logins, no implicit provisioning on normal requests |
| AUTH6-12 / 6 | Valid cookie resolves A; duplicate, malformed, URL/form/header token and empty values deny; account/identity/tenant disable blocks | HTTP/DB; digest-only storage, fixed least-result function, no context from request tenant fields |
| AUTH6-13 / 6 | Active last_seen advances monotonically, absolute bound fixed; idle/absolute exact equality expired, just-before valid, no cookie sliding renewal | DB/HTTP; assets/failed auth never touch; valid-auth later domain denial does touch as specified |
| AUTH6-14 / 6 | Login issues new bearer/session UUID, rejects active-auth start/callback; device Y unaffected except documented active cap | HTTP/DB/browser; no fixation/account switch, limit 10 deterministic oldest revocation, concurrent issuances never exceed cap |
| AUTH6-15 / 6 | Protected POST logout revokes current and clears exact cookie; GET/CSRF/provenance invalid logout cannot revoke; repeat unauthenticated no-op | browser/HTTP/DB; next lookup fails, other session valid, cookie scope matches issue/clear |
| AUTH6-16 / 6 | Logout vs touch/new request under barriers; pre-revoke authorized work may finish, post-commit resolver fails | DB/public port; no resurrection, deadlines preserved, no blanket cancellation claim |
| AUTH6-17 / 7 | Re-rendered hidden CSRF identical within same session, changes on rotation; known-answer HKDF and domain-bound digest match; cannot use A token in B | crypto/library + HTTP/browser; raw token nowhere else, no extra token cookie/endpoint, revoked session never validates |
| AUTH6-18 / 8 | Boundaries of each fixed window, replica-shared concurrent limits, malformed unverified identity no account lockout | HTTP/DB; allowed Nth, generic 429 N+1, trusted IP parsing, no counter reset/list/table privilege |
| AUTH6-19 / 8 | Missing keys/DB/limiter fail login closed; valid existing sessions unaffected by missing provider endpoint alone | config/HTTP; bounded 503, no development fallback/verification disable |
| AUTH6-20 / 8 | Redaction canaries across success/error/redirect/429/503, fake provider exception and query string | browser/proxy/log/trace; no bearer/code/state/nonce/verifier/invite/token/proof; positive scanner control proves detector works |
| AUTH6-21 / 3,8 | Exact seven control tables, no runtime direct SELECT/DML/sequence access, PUBLIC deny and only named function executes | real-role DB/catalog/static; app_owner unavailable to runtime, no generic privileged function, return shape minimal |
| AUTH6-22 / 8 | >24h terminal and expired transactions cleaned in bounded batches; ciphertext erased at terminal; counters expire; fresh transaction unaffected | DB/public port; per-operation cleanup bound and indexed scan, no worker/GET cleanup/domain mutation |

All case groups map to MVP-07 implementation except shared role/pooling/catalog
foundation evidence in MVP-06/Issue #5; browser controls reuse Issue #7 cases,
not a weaker duplicate. Every resource/function/query site reconciles with
production inventories. No Android/Telegram, linking or destructive-action tests
are claimed run or required before those features are scoped.

## Boundaries, mutations and evidence

Token schema tests cover absent/null/duplicate claims, bool-as-number NumericDate,
wrong JSON shape, 43-char base64url malformed input and size limits. Time oracles
must distinguish provider 60s skew from zero-skew DB deadlines. State claim
expiry uses equality-expired and races have both serialization orders exercised.
Mutation tests independently remove binder, nonce, PKCE, audience/azp, expiry,
revocation and disabled-state checks; the named negative case must fail. RLS or
HTTP routing cannot mask a missing identity use-case check. Reuse ADR-008
predicate/RLS and pooled-context mutation design, extend exact control inventory.

For each run record current commit, fixture/test revision, intended and executed
case counts, pass/fail/skip, DB role/version, browser/tool/tzdata where relevant,
underlying exit status and sanitized state/ordering evidence. No zero-case pass,
hidden retries, live secrets or claims that designed cases have executed.
Implementation tests must include success journeys login->profile->logout and
invitation->pending-catalog->fresh-login->ready. Security/code review of actual
implementation remains necessary after these design reviews.

## Focused review remediation

AUTH6-23 / binding (public-port/HTTP/DB/browser): barrier T1 after successful claim
but before provider response; T2 start on same binder must get 409 without new
transaction. Finish T1 for subject A; no subject B session/cookie can be issued
through T2. Repeat after T1 succeeded but cookie not delivered. At original
expiry, stale T1 finalization must fail all identity/session writes while a new
binder flow may proceed. Failed T1 permits retry, pending T1 may be superseded,
independent browser Y remains independent. An active session appearing between
start/callback must not be replaced. These are distinct from single-state replay.

AUTH6-24 / AEAD: valid envelope decrypts and challenge matches; flip ciphertext,
tag and nonce; swap between T1/T2 or client configs; wrong/missing key, unknown
key version and malformed envelope all fail generically before token exchange.
State remains consumed, persisted verifier already cleared at claim, no bootstrap
or session writes, no secret in errors/logs. Known-answer/reference AEAD positive
control proves the harness is actually testing authenticated decryption.

AUTH6-22 revised retention oracle: claim clears stored ciphertext immediately,
then simulate process death. At deadline equality lookup/finalization fail even
before cleanup; no transition back to pending. After zero traffic for >24h,
tombstones MAY still exist; the next valid start/callback deletes up to 100
eligible rows per table via indexed bounded work, leaves fresh rows untouched,
and large backlogs drain across operations. Exact deletion eligibility is original
expiry+24h (transactions) or window-end+24h (counters), equality eligible. Capacity
99999/100000/100001 and 199999/200000/200001 paths assert atomic reservations,
concurrent admissions never exceed hard cap, rejection never evicts live state,
released rows free capacity and reserved counters reconcile with real table
counts. Ordinary GET/session requests must not perform this cleanup.

AUTH6-18 revised limit oracle: fixed DB-aligned windows test just-before/equality/
just-after boundary and Retry-After=ceil(window_end-now), minimum1. Check exact
consume order: invalid proof consumes IP but not binder; IP-denied request
consumes no binder; binder-denied request creates no transaction. Failed callback
consumes IP only until valid OIDC, then invitation bucket if new provisioning is
attempted; existing identity ignoring invite never consumes its budget. New
provision attempts consume invitation budget on success/failure. User issuance
consumes only for validated identity in final commit, rollback preserves budget.
Concurrent replica N/N+1 cases obey each shared scope; no unverified subject
selects victim user bucket. Per-scope allowed threshold, denying counter
saturation, uniform 429, zero session/cookie side effect and separate capacity503
are checked. Existing valid sessions still resolve when provider/limiter unavailable.

AUTH6-25 / GET exception: HEAD never dispatches callback; failed callback may
only claim/terminalize/counter/cleanup control state, never create identity/session
or invoke catalog ensure. Validated callback is the sole GET authority mutation
exception. Product GETs remain nonmutating; authorization precedes catalog work.

AUTH6-26 / signed binder envelope: valid cookie survives repeated form render
without extending signed expiry; replay form one second before expiry cannot
produce proof/transaction beyond it. Tamper nonce/issued/expiry/version/MAC,
noncanonical encoding, oversized envelope or signature substitution all fail
before state claim. Distinct domain labels prevent using hidden proof as cookie
or vice versa. GET has no need to recover previous hidden proof or persist a
binder row. Expired envelope renders fresh independent binder, never resets an
old transaction. Exercise DB-time equality and no unsigned timestamp acceptance.
AUTH6-21 additionally reconciles all section10 wrappers and rejects runtime
execution of internal bootstrap/capacity/cleanup helpers, unknown overloads and
any general-purpose identity setter. Return-shape tests seed secret canaries in
control rows and assert only listed fields for each wrapper.

AUTH6-27 / start UUID and AEAD ordering: trusted application code generates T's
UUID before encrypting its verifier, passes both UUID and ciphertext to
start_web_login, and receives that exact stored UUID. Claim returns T and its
ciphertext; decryption under T/client associated data succeeds, while another
UUID fails authentication before token exchange. HTTP/form transaction UUID
injection is rejected. Duplicate UUID creation fails without overwriting or
substituting the existing row or ciphertext. Retrying with a newly generated
UUID requires fresh encryption/nonce; reusing old ciphertext under the new UUID
fails the AUTH6-24 oracle. Check the function inventory needs neither a UUID
reservation nor a ciphertext-update operation and still denies direct table
access. Execute through identity public port, production HTTP and real-role DB.
