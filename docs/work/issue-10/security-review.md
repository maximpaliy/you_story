# Independent security design review — Issue #10

- Reviewer: independent security-review agent; not the design/test-design author
- Date: 2026-10-25
- Material: Issue #10 design, HTTP contract, test design and OpenAPI candidate;
  approved Issue #6 contract; ADR-008/009/011; merged PR #25's exact
  `005_identity` database design, SQL and independent security disposition
- Baseline: main `ca99acd`; PR #25 merged and issue #9 closed
- Verdict: **scoped integration/API design pass on the corrected merged baseline**;
  the final merged-baseline reassessment below is authoritative. This is not
  runtime evidence, owner API approval or risk acceptance.

## Historical draft findings — superseded by merged-baseline reassessment

The following findings and first reassessment describe an initial stale checkout
before merged PR #25 was discovered. In particular their proposed permanent,
unconsumed allowlist rows, new DDL and empty-session preflight are **not current
implementation requirements**. They cannot override the reviewed, merged 005
one-shot admission, nullable legacy-invalid session and existing lock/clock rules.

### SR10-01 — Preallowlist authority is not yet represented

Blocking before the affected implementation. The current design proposes
deployment-config preallowlisting and a trusted-policy decision passed to
finish_web_login, while the accepted function contract supplies no such input.
It correctly marks that conflict unresolved. Do not add a caller-selectable
allowlist boolean, unlisted overload or eighth control-plane table by inference.
AUTH6-09 requires both invitation and subject-preallowlist admission.

The lead's alternative is sound in principle: keep owner-controlled admission
rows in the existing invitation control table, discriminated as bearer invitation
or subject preallowlist. Require all of the following in the concrete design,
DDL review and real-role tests:

- Canonical issuer and bounded exact subject are authority; never email, name or
  domain. Unique issuer/subject preallowlist key and kind-conditioned CHECKs
  reject ambiguous rows or consumed preallowlist rows.
- Token-digest lookup only considers bearer-invitation kind. A synthetic digest
  on a preallowlist row cannot be redeemed as an invitation or exposed as a
  token. Preallowlist lookup only uses canonical verified issuer/subject.
- Preallowlist rows remain unconsumed. Presence/eligibility is locked and
  rechecked through atomic finalization; removal blocks new provisioning but
  cannot revive/disable existing accounts implicitly. Any indefinite expiry is
  explicit owner-controlled setup data, not a client-supplied lifetime.
- Existing active identities ignore supplied invitation/admission data; disabled
  identity/user/tenant denies all branches. Subject/bootstrap uniqueness and
  invitation winner behavior remain atomic with session creation.
- No runtime direct table grant, admission-management endpoint or new runtime
  function is introduced. finish_web_login derives admission internally with
  its unchanged reviewed inputs. Exact manifests and wrong-kind tests cover
  every new constraint and lookup branch.

This implements already approved subject-preallowlisting without granting the
HTTP caller a new policy decision. The independent architecture reviewer must
confirm the accepted storage boundary; security review does not grant owner
approval of material architectural changes.

### SR10-02 — Callback error representation needs one precise rule

Clarification required before contract approval. Issue #6 requires a generic
HTML retry page for all callback failures. The HTTP draft specifies HTML for
400 but does not explicitly declare 409/429/503 or callback framework/500 output.
Make every failure on the exact callback GET an identically generic no-store
HTML page with fixed `/login` retry link and full HTML policy; statuses may
preserve already_authenticated/rate/service distinctions and Retry-After, but
must not expose provider/subject/eligibility details. Do not fall through to a
JSON framework exception on that route. Unsupported methods must remain 405
without invoking callback logic.

### SR10-03 — Stored-input test claims must match the minimal profile

Clarification required in test design. The HTTP contract deliberately stores or
renders no provider name or user-authored profile text. WEB-03's current proposed
test description nevertheless refers to an actual stored profile presentation
source and expected literal text. For this slice, seed provider/preference/control
canaries and prove they are unselected and absent, exercise actual reflected
error/form paths and template contexts, and explicitly label stored text-rendering
journeys as belonging to later features. Do not create a new persistence surface
to make a test description true or report an unused XSS sink as executed coverage.

## Boundaries retained by the draft

The draft preserves the approved narrow callback GET exception, one-shot
browser-bound claim before exchange, encrypted verifier erasure at claim,
transaction-ID AEAD binding, PKCE/nonce/state separation, strict maintained-library
OIDC validation, fixed HTTPS provider endpoints and no provider-directed URLs.
It does not accept cookie, CSRF, origin or CSP weakening.

Atomic finalization includes identity/tenant creation, necessary invitation
consumption, user issuance budget, session write and transaction success. A
previously committed claim remains consumed after failure. Separate catalog
transactions and pending state preserve module ownership and a usable profile/
logout on reconciliation failure; normal GET/session lookup does not retry it.

The proposed profile response is a least-result resolver projection rather than
a new owner-table query, containing only current user/tenant UUIDs and readiness.
It excludes provider subject, names/email, session UUID, token/CSRF data, private
preferences and arbitrary target IDs. Actor authority must come from the sole
trusted identity issuance boundary and be checked by direct public-port tests,
not merely route validation, frozen dataclasses or a provenance string.

The seven-table/no-runtime-table-access model, immutable applied migrations,
separate runtime/owner credentials and explicit extension of architecture/SQL/
artifact registries are retained. New actor issuance or function calls must be
registered narrowly; removing the health-only gate wholesale is unacceptable.

## Implementation gates that this review cannot clear

Before SQL execution, independently review exact column/CHECK/FK/index inventory,
function overload inputs/least-results/ACLs/search paths and the lock hierarchy.
In particular prove invitation-attempt denial counters commit without partial
identity writes, issuance-budget rollback, admission/capacity reconciliation,
bound cleanup and absence of deadlocks under both deterministic race orders.
The current conceptual transaction description is not approval of arbitrary DDL.

Choose and pin maintained OIDC/crypto/template/browser dependencies, establish
strict duplicate/type/key/time handling beyond library defaults, and run real
PostgreSQL/runtime-role, provider, HTTP and HTTPS-browser adversarial evidence.
The sole ActorContext issuer and rejection of forged public-port contexts need
actual code review and source/wheel mutations. Enforce outer response policy on
early errors, strict duplicate-cookie/header/body parsing, secure cookie clearing,
no account switching, expiry equality and no logout/touch resurrection.

Positive-canary telemetry evidence must cover every enabled app, server access-log,
proxy, trace and retained-test-artifact sink; suppressed application logging alone
does not prevent callback query leakage. No production credentials, real-user
data, deployment or privacy-risk acceptance follows from this design review.
SEC-01/05/06/07 and issues #9/#10 remain open for their implementation evidence
and independent security/code review.

No runtime tests were executed for this review. The proposed OpenAPI artifact
was not present at initial review and requires reconciliation after generation.

## Historical focused reassessment — 2026-10-25, before baseline correction

Reviewed the revised design, HTTP contract, test design and generated
`openapi.candidate.json`. The three initial findings above are retained as review
history and are now **resolved at this design stage**:

- **SR10-01:** The design replaces the unresolved configuration decision/finish
  flag with discriminated owner-only rows in the existing invitation table.
  Kind-conditioned subject/consumption constraints, canonical issuer/subject
  uniqueness, wrong-kind bearer exclusion, finite/infinite owner-selected expiry,
  locked admission checks and unchanged finish signature are explicit. Existing
  active identity is considered first; preallowlist admission never consumes the
  supplied bearer invitation or its attempt bucket. No new table/runtime grant
  or admission-management API is introduced. This preserves the security
  boundary of already approved preallowlisting; exact DDL must still demonstrate
  each constraint and both negative lookup branches through real-role tests.
- **SR10-02:** Every exact callback GET failure, including early parsing,
  middleware and 409/429/503/500 cases, uses the same generic HTML retry renderer
  with CSP/no-store; 429 retains Retry-After. The OpenAPI candidate agrees on
  HTML for all listed callback failure statuses. Unsupported methods remain
  non-dispatching 405 and do not become another callback exception.
- **SR10-03:** WEB-03 now distinguishes actual stored-canary exclusion and
  reflected-input rejection from test-only template escaping/mutation controls.
  It explicitly does not claim a shipped stored-text round trip. No new profile
  persistence or rendering sink has been added to manufacture such coverage.

The candidate's own-profile schema contains exactly user_id, tenant_id and
catalog_pending/ready provisioning_state, forbids additional properties and
requires session-cookie authentication. Its form-only logout, finite body caps,
closed destination enum, unknown/duplicate field rejection and callback query cap
match the prose contract. The candidate is separate from the active generated
health-only contract; it does not prove routes are implemented or exposed.

No further blocking finding was identified in this **slice/API design**. The
implementation gates listed above remain mandatory: exact SQL/function/ACL/lock
review, dependency pins and maintained-library behavior, real PostgreSQL/provider/
HTTP/HTTPS-browser evidence, actor provenance and artifact mutations, telemetry
canaries, owner approval of new API choices, and independent implementation
security/code review. This scoped pass does not mark those gates completed or
authorize deployment, accept residual risk, close a security finding or complete
issues #9/#10. No authentication runtime tests ran during this reassessment.

## Authoritative merged-baseline reassessment — 2026-10-25

Reviewed the corrected Issue #10 design/test design against
`docs/work/issue-9/auth-foundation-design.md`, its independent security review
and the actual merged `005_identity.sql`; reread the unchanged HTTP/OpenAPI
candidate. The corrected feature design reuses existing 005 without new DDL,
wrapper overloads, direct-table grants or applied-migration changes.

**Verdict: scoped integration/API design pass.** The stale-baseline findings and
first pass above are superseded where they proposed database/admission changes.
No remaining design blocker was identified for the corrected feature slice.

The following are now the exact database/security assumptions for #10:

- Admission is the merged owner-only invitation representation: nullable kind
  (`bearer`/`allowlist`, legacy NULL-as-bearer) and permitted_subject. Unknown
  subjects with a supplied digest select only bearer admission; an invalid
  supplied bearer does not fall back to an allowlist. With no supplied digest,
  an eligible exact issuer/subject admission may be selected. Successful
  bootstrap **consumes** that one-shot allowlist inside the same finalization
  unit. Known active identities require neither path. Do not substitute the
  historical permanent/unconsumed preallowlist proposal.
- Reuse nullable external_identity_id/csrf_digest legacy handling: old sessions
  remain invalid and untouched. No empty-session-table preflight, backfill,
  reinterpretation or legacy revival is introduced. Original 000–005 hashes
  remain unchanged, and existing migration/role/constraint evidence remains
  prior #9 evidence rather than a newly executed #10 result.
- Preserve the shared bounded advisory lock, clock_timestamp sampling after
  blocking advisory/row waits, fixed-second durations, exact expiry equality,
  and existing complete least-result wrapper signatures. Network calls remain
  outside DB transactions/locks. Cleanup runs only once through the operation's
  IP limiter stage, with combined <=100 transaction candidates and <=100 counters.
- Commit ordinary finish invalid/limited/unavailable discriminants so the
  protected outer invitation-attempt budget survives normal denial. Successful
  identity/admission/session/issuance/finalization authority remains atomic;
  infrastructure SQL abort fails closed. A previously committed claim is never
  restored, and fail terminalization uses a separate bounded transaction.
- Conditional readiness uses the existing private digest-targeted wrapper,
  only after typed catalog-pair success and a public-port check that immutable
  actor identity/tenant matches validated private session evidence. No raw
  session-digest HTTP endpoint, target/state input, ordinary-request retry or
  catalog write from identity is introduced.
- The resolver intentionally returns no csrf_digest. Trusted identity derives
  expected HKDF CSRF from valid bearer/session UUID for rendering/validation;
  persist the approved digest at issuance and test that stored value using
  owner-only fixture inspection. Keep the ADR-009 domain-separated,
  session-UUID-bound fixed-length digest comparison in constant time; there is
  no need to widen resolver outputs or grant control-table access. Missing or
  malformed proof, wrong session and expired/revoked authority must fail before
  logout dispatch.

SR10-02/03's corrected callback HTML and truthful canary/template test scope
remain valid: every GET callback failure uses generic no-store HTML with CSP,
and stored provider/preference values are exclusion probes rather than a claimed
shipped stored-text rendering journey. The candidate's three-field own-profile,
session-cookie-only authority and form-only logout remain appropriately narrow.

The remaining implementation work requires exact adapter/provenance/catalog SQL
registry and crypto/browser dependency review, followed by the complete real
PostgreSQL/provider/HTTP/HTTPS-browser tests and independent code/security evidence
review. Reusing unchanged 005 does not require manufacturing a new SQL approval
gate; any actual database change or defect would require separate additive
review. Owner approval is still required for the new concrete profile/API choices.

Issue #9 is already closed following merged PR #25; #10 is not a reverse gate on
that database foundation. Global SEC-01 provisioning integration and SEC-05/06/07
feature evidence remain open. This review ran no runtime tests and does not
complete #10, close those findings, authorize production/real-user data, accept
security risk or claim the prior 217-test foundation run as new verification.
