# Issue #9 authentication database test design delta

Status: independent test-design review passed for the database delta.
Architecture/security design review passed; execution evidence remains pending.
Design: auth-foundation-design.md, approved ADR-011/Issue #6 contract; existing
foundation suite remains mandatory. Tests use real PostgreSQL as app_runtime;
owner connections only arrange/inspect synthetic fixtures and migrations.
No provider/HTTP/cryptographic test double is called auth-runtime evidence.

| Case | Required positive, boundary, negative and failure evidence |
| --- | --- |
| A01 exact catalog | Seven and only seven control-plane tables; private preference RLS unchanged; zero direct PUBLIC/runtime control-table access; exact7 wrappers+mark-ready+existing context, ownership, SECURITY DEFINER/search_path, every overload/argument/result/EXECUTE ACL; direct internal helper execution and owner SET ROLE denied |
| A02 additive upgrade | Preserve original000..004 checksums; empty-to005 and populated004-to005; old session row values unchanged, new nullable linkage/CSRF null, resolver returns no tuple/no touch; new composite FK/length checks; failure at every005 phase rolls DDL/ledger back, retry exact catalog; runtime cannot migrate |
| A03 start | Exact server UUID roundtrip; expiry=min(DBclock+600,binder deadline), no deadline extension; closed config/destination/digest/ciphertext/challenge validation; newest pending wins, prior ciphertext cleared; duplicate ID/state must not mutate existing rows; unexpired claimed/succeeded binder denies start; failed/expired original window allows next; no identity/session/invitation authority writes |
| A04 claim | Matching state/binder/config succeeds once with least payload then persisted ciphertext null; wrong binder/state/config/status/missing/expired all same zero result/no payload; two connections race at barrier, only one result and no second verifier read; fail terminalizes only matching claimed row, never reopen; original-expiry equality and lock-wait-over-expiry deny |
| A05 invited finish | Previously committed claim and validated synthetic issuer/subject yield exactly one active user/tenant/external identity/session; invitation consumed only successful new provisioning; exact linkage, digest/CSRF only, immutable absolute+created deadlines; unknown/disabled identity/user/tenant, wrong/replayed/expired/mismatched invitation return same invalid status and null fields and no partial rows |
| A06 known identity | Controlled existing active identity ignores supplied invitation and its attempt budget; active linkage required; arbitrary caller user/tenant/owner/allowlisted boolean has no accepted function signature; unknown subject without invitation/allowlist fails; approved issuer/subject-bound owner allowlist row bootstraps once without bearer invitation, consumes atomically and cannot match different subject; rollback leaves it available |
| A07 atomic failure | Inject unique/FK/check failure or test trigger after invitation consumption, triple creation, issuance counter, session insert and successful status update; each failure returns invalid with no authority fields, rolls authority/user-issuance budget back, leaves original claim consumed and invitation-attempt budget retained on normal generic failure; separate fail terminalization; no token retry/recovery operation |
| A08 concurrent identities | Two subjects/claimed binders race one invitation: at most one new triple/session; same external subject racing callbacks converges to one user/tenant/external identity; same-consumed-invitation/same-subject does not create duplicate, finished transaction never replayable; duplicate session UUID/digest cannot commit bootstrap-only state |
| A09 session expiry/touch | Exact external/user/tenant linkage and active state; NULL legacy/CSRF, revoked, disabled, unknown, wrong links all zero result/no touch; DBnow==absolute or last_seen+7days invalid; successful touch monotonic, created/absolute immutable; lock-wait past expiry invalid; no client time argument |
| A10 revoke/cap | Resolve/revoke concurrent linearization barriers; revoked sessions never refreshed/revived; independent sessions untouched; repeated unknown/revoked gives same invalid shape; owner-arranged ten valid prior sessions or issuance in a second fixed window allows next issuance to revoke deterministic oldest(created_at,id), skips invalid old sessions, new session never selected; independently user-issuance11 same fixed window denied without authority writes |
| A11 counters | All five scopes exact caps/windows; count saturatesN+1; equality begins next window, DB-derived window-end no caller clock; independent subjects/scopes; invitation attempts include failed eligibility, known identity ignores invitation; denying stage does not consume later budgets; invalid/private reserved scope denied; no reset/list/delete function |
| A12 capacity/cleanup | Actual row-count versus protected reservations including terminal rows; two reserved rows excluded ordinary scopes/cleanup but included physical200000 cap; atomic concurrent admission at cap admits only capacity; full rejects safely no live eviction/session-resolution interference; at most100 eligible transactions/100 counters via IP-start/IP-callback limiter only per auth operation, no second cleanup in start/claim/finish; expiry+24h equality eligibility, no traffic no promised deadline, expired claim never reopens; all deletion/reservation adjustments atomic |
| A13 ready boundary | Session-derived target only; catalog_pending->ready, ready idempotent, disabled/expired/wrong linkage deny; no caller user/tenant/state overload; no catalog table read/write; session resolver/health/failure never provision or mark-ready; no product route/issuer/catalog ensure present |
| A14 artifact/privacy | Exact /live,/ready OpenAPI unchanged; no auth routes/adapters/jobs/executables; safe errors/logs exclude digest/ciphertext/state/binder/issuer/subject/query/SQL/DSN sentinels with observed positive logging sentinel; wrappers never return digest/attributes beyond exact least-result manifest |

Use independent concurrent connections, explicit row/advisory lock barriers and
observed lock state rather than sleeps to prove expiry/claim/finish/revoke races.
DB clock tests arrange stored deadlines under owner fixtures; exact equality
may use the reviewed private owner-only _auth_now helper replacement in a
disposable database followed by body restoration/catalog assertion. Wrappers
never gain a test-only current-time parameter or runtime clock override. Capture server versions, committed claim
state, immutable row postconditions and role per assertion. Required integration
cases fail when PostgreSQL unavailable, never skip or substitute SQLite/owner.

Mutation controls must prove the oracle fails when removing binder/expiry/status
checks, resetting claim, returning verifier twice, broadening function audience or
result, bypassing identity-active linkage, allowing legacy session resolution,
removing composite FK, omitting cap reservation, rolling back attempt budget or
leaving authority committed after failed finish. Remove each single guard while
others stay intact so defense layers cannot mask it. Positive baseline and
well-formed nonmatching probes ensure generic rejection is not a false pass.
All mutating test code remains fixture-only, never an installed SQL bypass.

## Scope and evidence gaps

The prior #6-design blocker is corrected by accepted ADR-011 and approved
contract. SEC-05 runtime/OIDC/AEAD/HKDF/browser evidence remains #10. This delta
cannot close it or claim authentication is safe to expose. Catalog ensure/
ActorContext issuer/login orchestration and their production SQL predicate
registry are not implemented here; ADR-008 provisioning evidence remains open.
Unknown preallowlisted subjects use owner-controlled subject-bound admission
metadata within invitation, not an eighth table, caller boolean or precreated
identity triple. Exact checks/index and generic failure/non-enumeration are tested
for wrong/expired/consumed allowlist entries; no runtime allowlist management is
registered. Catalog orchestration remains the explicit future-slice boundary.

Independent reviewers must reconcile the final implemented scope and all
pass/fail/skip counts to this plan. Exact function-overload and SQL-site manifests
must update only after review; hash refresh alone cannot authorize a broad SQL
path. Prior tenant pool/RLS/migration/architecture mutation suites remain green.

Exact start result is status+nullable ID/expiry; exact finish result is status+
original five nullable success fields+nullable window_end. Tests distinguish
normal invalid, limited and unavailable representation without privacy metadata.
Normal failure is committed, preserving invitation-attempt counts; issuance
inner unit rolls back before a failure row is returned. Test callers that roll
back normal denial must be caught. All invalid identity states have identical
status and NULL outputs. limited alone carries denying window_end, unavailable
no fields. These are approved-failure internal representations, no product HTTP
contract expansion. claim/resolve invalid paths still return zero rows.
