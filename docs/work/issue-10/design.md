# Issue #10 — Google sign-in implementation design

Issue: https://github.com/maximpaliy/you_story/issues/10 (`MVP-07`).
Status: implemented against the owner-approved HTTP contract and ADR-012.
See [verification](verification.md) for actual runtime evidence and limits.

## Requirements and authority

Implement the complete vertical login/profile/logout slice on merged #9 /
[PR #25](https://github.com/maximpaliy/you_story/pull/25), main `ca99acd`.
Issue #9 is closed. Its reviewed authentication database boundary already exists;
this issue supplies provider/crypto/public-port/browser integration and login-only
catalog provisioning. The initially supplied checkout was behind main and has
been updated to its exact signed commit before final review.
Authoritative lifecycle and numeric limits are the owner-approved
[Issue #6 contract](../issue-6/auth-session-contract.md), ADR-007/008/009/011,
and Issue #7 browser controls. This design does not replace those contracts.
Only the accepted own-profile Q01 and authentication subset of Issue #8 are
needed; proposed content/practice policies in ADR-010 are not implemented.

AGENTS.md requires independent architecture/security/test-design reviews before
implementation and owner approval for externally visible API contract changes (obtained on
2026-10-26 for this contract).
The backlog explicitly says its approval does not approve an API contract.
The existing auth lifecycle needs no repeat owner decision. The new profile
URI, fields and error/status representation are made concrete in
[http-contract.md](http-contract.md) and [openapi.candidate.json](openapi.candidate.json)
as the approved review artifacts. The active generated contract is
`docs/api/openapi.json`; both contain the same approved endpoint inventory.

## Slice boundaries and sequence

1. Review this design and the issue-level test design independently. Obtain
   owner approval of the exact HTTP contract before registering new routes.
2. Implement typed private adapters for the existing `005_identity` wrappers;
   preserve their exact signatures, discriminants, result fields, ACLs and clocks.
   Reuse #9's existing database tests and extend through actual public ports.
3. Implement catalog's login-only idempotent catalog/grant command and its
   actor-bound SQL registry, then call the existing identity ready wrapper through
   a validated actor/session-matching public command. No Yousician data/features.
4. Implement Google adapter, login orchestration and browser delivery together;
   preserve health/readiness behavior and the existing foundation checks.
5. Run cumulative checks and adversarial/browser suites; obtain independent
   implementation security/code reviews and evidence review before #10 completion.

#10's integration evidence is not a reverse prerequisite for closed #9.
Cumulative SEC-01/05/06/07 gates remain open for the implemented feature scopes.
No new schema migration, admission policy or SQL wrapper is planned for this
slice. A discovered database defect would require a separately reviewed additive
fix, never edits to applied 000–005. No live Google account, paid infrastructure
or real user data is needed for synthetic verification. Production OAuth
registration/secrets and deployment require separately authorized environment setup.

## Application and composition

Identity public immutable contracts expose start/complete login, resolve current
session, own profile, logout current session, and a callback-only conditional
catalog-ready operation. Inputs are typed validated command values; they never
include client-selected current user, tenant, session UUID or actor context.
The Google provider port is extensible, but only Google is registered. No
generic provider selector or provider URL can arrive from HTTP.

Identity application logic depends on public protocols for persistence, provider,
cryptography and clocks. Infrastructure owns PostgreSQL, HTTP/OIDC libraries,
crypto and the sole production ActorContext issuer. Composition wires adapters;
delivery calls public ports and never SQL or module-private implementations.
ActorContext remains immutable and cannot be deserialized, constructed by a
request model, or minted in delivery/shared/domain code. Only a successful
validated session resolution or committed login finalization supplies its trusted
user/tenant tuple. Provenance must be validated by the issuer, not a string an
HTTP caller can choose. Public use cases must reject forged context instances;
Python object construction tricks are not authentication authority.

The composition root, not identity, orchestrates the catalog public command
after committed login. Identity never imports catalog private code or queries
catalog tables. Catalog returns a typed success; identity requires the validated immutable
actor plus its private resolved-session evidence, verifies matching user/tenant
linkage, and calls existing mark_catalog_ready(session_digest). The SQL wrapper
revalidates active linkage and derives its target without caller IDs/state. The callback is the only wired caller. A later login retries
pending provisioning; profile/session resolution never performs provisioning.

Update `composition.json`, SQL registrations, source and wheel checks with
explicit new roots, ports and statement sites. Keep fail-closed absence checks
for every other worker, adapter, endpoint and privileged capability. Replace
the exact health-only route inventory with the approved exact inventory; do not
disable that gate or allow arbitrary routes/imports. No public/test actor factory, test
provider, test clock, key override endpoint or owner DSN enters the wheel.

## Existing database boundary and adapter plan

Reuse the merged [authentication database design](../issue-9/auth-foundation-design.md),
exact `005_identity.sql`, schema/SQL manifests and
[verification](../issue-9/auth-foundation-verification.md). The reported 217-test
foundation evidence belongs to #9; no rerun or #10 runtime pass is inferred.

The seven control-plane tables and all wrapper signatures already exist:

| Wrapper | Adapter obligations |
| --- | --- |
| start_web_login | Trusted UUID generated before encryption; binder/state/nonce digests, challenge/ciphertext, fixed google-web config, optional bound invitation digest, closed destination and signed binder deadline. Map ok/invalid/in_progress/unavailable without leaking fields |
| claim_web_login | Bound state/binder/config only; commit before network; zero rows is generic invalid; sole ciphertext returned and erased in DB |
| fail_web_login | Terminalize only this claimed UUID/binder in a separate transaction; never reset/recover a claim |
| finish_web_login | Validated canonical issuer/subject, claimed UUID/binder and freshly generated session UUID/token/CSRF digests; commit ordinary ok/invalid/limited/unavailable results; success fields only on ok, window_end only on limited |
| resolve_web_session | Digest only; successful minimal user/tenant/session/provisioning/absolute-expiry tuple or zero fields; issuer only accepts this exact typed trusted result |
| revoke_web_session | Current validated session digest only; commit before clearing cookies; other device sessions unaffected |
| consume_auth_limit | Trusted derived scope/key; allowed/window_end, zero rows means unavailable; retain saturated denial counters, map window-end to Retry-After |
| mark_catalog_ready | Private session-digest targeting only after typed catalog success and public actor/session match; no HTTP ready/digest endpoint or arbitrary IDs/state |

Maintain the safe existing `search_path=pg_catalog,identity`, owner-only helpers,
exact runtime EXECUTE grants and zero direct table/sequence access. Own-profile
projects only user_id and provisioning_state from the existing resolver tuple;
tenant_id remains internal. No profile SELECT function/grant or new fields.
No profile-name column/storage retention decision is introduced.

Admission metadata already uses nullable `admission_kind` (bearer/allowlist) and
`permitted_subject` in invitation. Preserve legacy NULL-as-bearer behavior and
reviewed one-shot subject-bound allowlist consumption in finish's atomic unit.
Known active identity ignores admission. For unknown subjects, a supplied
invitation digest selects only bearer admission; without one, finish may select
a matching owner-created subject admission. An invalid explicit bearer cannot
fall back to the subject allowlist. Synthetic
allowlist digest must never become an independently redeemable bearer token.
No permanent/unconsumed allowlist redesign, extra control table, HTTP owner setup
or caller boolean bypass. Existing NULL external_identity_id/csrf_digest sessions
remain invalid without touch; do not require an empty table, backfill, rewrite
or revive legacy records. New finish writes require linked identity and CSRF.

## Transactions, races and bounded state

Preserve #9's shared advisory auth-control lock and DB clock sampled/refreshed
*after* blocking locks, exact equality expiry and fixed-duration seconds. No
per-subject alternative locking scheme or transaction-start clock is introduced.
No provider/network exchange occurs with this database lock held.

IP-start budget precedes proof checking; valid proof then binder-start budget,
then start. Callback consumes IP-callback before claim. Cleanup occurs only
once in that operation's IP-stage limiter wrapper: <=100 total transaction rows
across expiry/erasure/deletion candidate classes, and <=100 counters, indexed.
The downstream wrappers never repeat cleanup. Missing admission store/key fails
new login closed; ordinary existing-session resolution needs neither provider
nor limiter. Retention remains lazy eligibility, never guaranteed wall-clock
24-hour deletion.

Claim commits before code exchange and clears stored verifier. All identity,
admission consumption, session, user-issuance budget and success state commit
inside finish's protected inner atomic unit. A normal denial must still be
committed so its outer invitation-attempt counter survives; do not map invalid
or limited to an exception that rolls back the whole SQL call. Infrastructure
SQL abort fails closed without promising counter persistence. After normal or
exception failure, fail_web_login terminalizes in a separate bounded transaction.
Never send a session cookie before a committed successful finalization.

The existing lock serializes session touch/revoke and deterministic oldest
session eviction at ten active devices. Integration tests retain direct SQL
controls but additionally prove real login/cookie/public-port outcomes. An
active browser cannot start or complete an account switch; recheck valid-session
exclusion at callback dispatch after state parsing and before any issuance.
Fresh login creates new bearer/session UUID/CSRF; no promotion of a binder or
request ID. Ordinary profile requests never renew cookie Max-Age.

Catalog ensure uses an actor-bound tenant transaction with explicit predicates
and FORCE RLS, separate from committed identity issuance. Its unique personal
catalog and owner grant converge on one complete pair; pair failure rolls back
that catalog transaction. Typed success permits the subsequent validated
actor/session-ready command. Either failure preserves the active session and
catalog_pending. The external pending result hides whether the pair committed;
a later fresh login retries idempotently, never profile/middleware/worker.

## Provider and cryptographic adapters

Pin maintained OIDC/JWT, AEAD/HKDF and template libraries within the approved
Python stack; review their supported key/claim behavior before choosing exact
versions and updating the frozen lockfile. Do not implement JWT/AEAD/HKDF from
scratch. Explicitly validate strict claim types and duplicate claims in addition
to library checks. No use of token-supplied jku/x5u or arbitrary discovery URLs.

Use the exact fixed Google authorize/token/JWKS URLs; TLS verification enabled,
redirects disabled, 5-second connect/10-second overall bound, bounded response
sizes, <=1-hour JWKS TTL and one bounded unknown-kid refresh. Signatures RS256
only; enforce all issuer/aud/azp/sub/nonce/NumericDate/time rules in Issue #6.
Code/state/nonce/verifier/access/ID tokens never survive callback processing.

Session, state, nonce, binder and invitation entropy is 32 OS-CSPRNG bytes.
Canonical unpadded base64url and domain-separated SHA256 digests follow the
approved contract. Signed fixed-schema binder/proof use canonical length-prefix
encoding and distinct labels; preserve original DB-derived expiry across tabs.
Generate transaction UUID before AEAD encryption and bind that exact UUID/client
as associated data. HKDF derives stable session-bound CSRF only from the valid
bearer plus session UUID. At issuance persist the approved CSRF digest. The
existing resolver intentionally returns no csrf_digest: subsequent validation
derives expected HKDF output from the validated bearer/session UUID, computes
the approved domain-separated session-UUID-bound digests for both submitted and
expected CSRF values, then compares those fixed-length digests in constant time.
Tests verify the
persisted issuance digest independently as owner; do not widen resolver results
or control-table grants to read it during requests.

Secrets are separately injected keys and Google client credentials with no
defaults, logging or committed examples. Validate canonical configured origin,
callback/client and key lengths before auth service startup; never derive them
from Host/forwarding headers. Existing sessions need only runtime DB and the
session derivation code, not provider connectivity.

## Browser delivery and privacy

Use contextual template autoescaping; no string-built HTML or safe-marked input.
Hidden proof/CSRF is rendered only in the matching form. All responses pass
one outer security-header policy, including framework/middleware errors. Enforce
the exact ADR-009 CSP as amended by owner-approved ADR-012, with an
independent fresh 32-byte nonce per HTML response;
no scripts/styles are required by this slice. Preserve no-store on auth and
private responses, correct media types, no-referrer, nosniff, frame denial,
permissions/COOP and production HSTS.

Before parsing unsafe bodies validate route method/auth boundary, strict origin
or fallback Referer, Sec-Fetch-Site, exact declared content type, content-length
and streamed byte cap. Reject duplicate/unknown form fields and duplicate cookie
names. No credentialed CORS or alternate bearer scheme. Callback GET is the
sole approved narrow authority exception; HEAD must never dispatch it.

Render semantic forms/labels, heading/landmarks and a fixed accessible retry
link. Minimal home/profile shows signed-in state and catalog readiness, links
to profile, and a protected logout form; pending state keeps both usable.
No provider image or URL is embedded. Request/provider errors never echo input.
Raw callback query strings must also be suppressed at server/proxy/access-log
boundaries; positive-canary evidence must include each enabled sink.

## Approval and evidence limits

Owner approval authorizes the named API choices, not a security risk or waiver
of implementation findings. Existing 005 SQL/reviews are reused unchanged; no
new SQL engineering approval is requested. Typed adapter/actor provenance,
private catalog statement registry and crypto/browser dependencies must still
receive exact implementation review and full integration evidence. Design review
cannot establish runtime safety or complete #10.
