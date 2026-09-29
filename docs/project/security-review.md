# Independent Security and Privacy Architecture Review

- **Review date:** 2026-09-26
- **Reviewer:** Independent security-review agent (not the architecture author)
- **Scope:** `docs/project/product-definition.md`,
  `docs/project/architecture.md`, and ADRs 001–004 as proposed on the review
  date.
- **Review type:** Design-time threat model and security/privacy gate review.
  This is not an implementation assessment, penetration test, legal opinion, or
  production authorization.
- **Overall result:** **Conditional architecture pass with open findings. Human
  architecture approval may proceed; test design follows that approval and must
  incorporate this review. Security-sensitive implementation and every
  production deployment remain blocked as detailed below.**

## 1. Security objectives and protected data

The design must protect:

- Google identity bindings, application sessions, bearer tokens, Telegram
  links, and account-recovery or linking artifacts;
- private catalogs, preferences, goals, tags, notes, practice history,
  statistics, instruments, and calendar activity;
- user-created audio/video, object identifiers, signed URLs, checksums, and
  derived metadata;
- secrets, signing material, service identities, deployment credentials,
  backups, logs, and audit records; and
- integrity and availability of catalog/history relationships, immutable
  snapshots, account deletion, export, and recovery operations.

The principal security objectives are strict tenant isolation, authenticated
and authorized access, confidentiality of private media and sensitive metadata,
integrity of confirmed history, recoverability, and an honest, executable
privacy lifecycle. Availability matters, but it must not override isolation or
erasure commitments.

## 2. Threat actors and assumptions

Threat actors include an unauthenticated internet user; an authenticated user
attempting cross-tenant access; an attacker controlling a browser, mobile
client, Telegram message, webhook request, upload, or leaked signed URL; a
compromised dependency or CI workflow; and a mistaken or malicious operator.
Automated abuse (credential/session replay, enumeration, expensive uploads, and
resource exhaustion) is in scope. Compromise of Google, Telegram, or GCP itself
is not designed away, but provider responses, least privilege, auditability,
and revocation must limit impact.

The review assumes HTTPS is terminated only by trusted GCP infrastructure,
private Cloud SQL connectivity is actually enforced, production and
non-production projects and identities are separate, and PostgreSQL RLS is
available. These assumptions require deployment evidence; prose alone does not
satisfy them.

## 3. Trust boundaries and principal attack paths

1. **Browser / API boundary:** Browser input, cookies, CSRF tokens, IDs, filters,
   uploaded metadata, and rendered catalog/user text are untrusted. Relevant
   threats are OIDC login CSRF, session fixation/theft, CSRF, XSS, IDOR,
   injection, mass assignment, enumeration, and denial of service.
2. **Android / API boundary:** A mobile application is a public client and
   cannot protect a client secret. Relevant threats are authorization-code and
   bearer-token interception, malicious redirect handlers, replay, insecure
   device storage, and cross-tenant object access.
3. **Google / identity boundary:** Provider assertions become an internal user
   only after issuer, audience, signature, expiry, nonce, state, redirect URI,
   and stable `sub` validation. Email is display data, never authority.
4. **Telegram / webhook and linking boundary:** Telegram updates and user IDs
   remain untrusted until webhook authenticity and replay controls succeed.
   Linking crosses from a strongly authenticated web session to a Telegram
   identity and is an account-takeover boundary.
5. **Application / PostgreSQL boundary:** The application supplies the tenant
   context used by repositories and RLS. Connection pooling, background work,
   migrations, nested objects, and privileged roles can turn one context error
   into cross-tenant disclosure or modification.
6. **Application / object-storage boundary:** Signed URLs temporarily move byte
   transfer outside the application. Guess-resistant names do not replace
   authorization. Upload type/size spoofing, malware, polyglots, overwrite,
   leaked URLs, orphan objects, and incomplete deletion are in scope.
7. **CI/CD / GCP control-plane boundary:** GitHub identities, workflow changes,
   dependencies, images, migrations, operators, Secret Manager, IAM, and
   infrastructure definitions can affect all tenants. Supply-chain compromise
   and privilege escalation have system-wide impact.
8. **Operational-data boundary:** Logs, metrics, traces, alerts, backups, PITR,
   quarantined objects, and restore environments are additional copies of user
   data. Access, retention, region, export, and deletion rules must cover them.

## 4. Positive controls in the proposed architecture

The review supports the architecture's internal user identity keyed by provider
and stable subject; server-derived tenant context; service authorization plus
non-bypassable RLS; personal-only catalog policy with dormant grants; immutable
history snapshots; private object storage and authorized media intents;
server-side sessions and CSRF protection; PKCE for public mobile clients;
separate runtime, migration, and administrative roles; Workload Identity
Federation; environment separation; and explicit security and adversarial test
handoffs. ADRs 001–004 accurately identify their principal security trade-offs.

These controls are design commitments, not verified controls. Findings below
define the missing decisions and evidence.

## 5. Findings and required actions

Severity reflects impact and likelihood before the stated mitigation. A finding
is closed only when its evidence is linked from this document or its tracking
issue. “Before implementation” means before production code for the affected
surface; “before deployment” includes any environment containing real user
data.

| ID | Severity | Finding / risk | Required action and acceptance evidence | Owner / due gate | Status |
|---|---|---|---|---|---|
| SEC-01 | **High** | Tenant isolation depends on transaction-local RLS context, but the exact fail-closed mechanism for pooled connections, background jobs, migrations, and privileged roles is unspecified. Stale or absent context could expose every tenant. | Define the database roles and grants, `FORCE ROW LEVEL SECURITY`/owner behavior, transaction-scoped context setup and reset, fail-closed policy for missing context, worker convention, and migration exception path. Provide migrations plus integration tests for read/write/join/child/guessed-ID access, reused pooled connections, missing context, jobs, and runtime-role bypass attempts. | Identity/data owner; **before implementing tenant-backed repositories** | Open — implementation blocker |
| SEC-02 | **High** | The provisional account-deletion approach retains snapshots under an “anonymized principal,” but fields allowed in snapshots, free text, indirect identifiers, linkage, backups, exports, legal basis, retention, and re-identification risk are unresolved. Merely replacing an owner ID is pseudonymization, not necessarily anonymization. | The human owner must approve a data inventory and final delete/export/retention policy. Define direct and indirect identifier removal, free-text handling, unlinkability criteria, catalog/customization/history behavior, identity revocation, backup expiry, audit records, user-visible semantics, and a verification procedure. Call retained data “de-identified” or “pseudonymized” unless an evidence-based anonymization standard is met. | Product/privacy owner; **before account-deletion implementation and before production** | Open — human privacy decision required |
| SEC-03 | **High** | Media is inherently untrusted and the format, size/duration, validation/scanning, serving, retention, region, and deletion policies are undecided. A signed upload URL alone may not reliably enforce all claimed constraints. | Approve allowlists and limits; document what the selected GCS signing mechanism can enforce; use generated non-overwritable keys, quarantine, server-side metadata and streamed-content validation, checksum/finalize idempotency, malware handling, safe response headers, download authorization, rate/quota limits, cleanup, region, and deletion behavior. Add abuse tests, including spoofed MIME/size, overwrite, incomplete finalize, cross-tenant attach/read, replay, and post-delete access. | Media/security owner; **before media implementation** | Open — implementation and deployment blocker |
| SEC-04 | **High** | Telegram linking and webhook authentication are future-facing but not sufficiently specified to prevent account takeover or forged/replayed updates. “Signature/secret path” is not an approved protocol. | Before adding Telegram, define the verified webhook mechanism, secret rotation, canonical request validation where applicable, update deduplication/replay window, one-use linking-code entropy/TTL/attempt limits/atomic consumption, confirmation in the authenticated web session, unlink/revoke flow, and rate limits. Threat-model confused-deputy and user-ID reassignment scenarios and test them. | Telegram integration owner; **before Telegram implementation** | Open — future-client blocker; does not block MVP without Telegram |
| SEC-05 | **Medium** | Web and mobile authentication name sound primitives but omit session/token lifecycle details. Session fixation, long-lived stolen sessions, unsafe redirect handling, and incomplete logout/revocation remain possible. | Specify cookie name/path/domain and lifetime, session ID rotation at login and privilege changes, idle/absolute expiry, server-side revocation/logout, OAuth error and account-linking behavior, redirect allowlist, refresh-token need/storage/rotation, mobile claimed-HTTPS or app-link redirect protection, bearer-token audience/scope, and reauthentication for destructive actions. Test login CSRF, fixation, replay, logout, expiry, and redirect interception. | Identity owner; **before authentication implementation** | Open — implementation blocker |
| SEC-06 | **Medium** | CSRF is required, but XSS/output encoding and browser security policy are not specified. User/source names and notes can become stored-XSS vectors capable of same-origin actions even with `HttpOnly` cookies. | Adopt framework auto-escaping, prohibit unreviewed unsafe HTML, sanitize any supported rich text, apply a restrictive CSP and security headers, validate state-changing content types/origins as appropriate, and define CSRF token binding/rotation. Add stored/reflected XSS and CSRF negative tests. | Web/security owner; **before web UI implementation** | Open — implementation blocker |
| SEC-07 | **Medium** | Authorization requirements do not yet define the complete resource/action matrix, especially grants, ancestry, statistics, customizations, exports, deletion, and media finalize. Inconsistent parent/child checks create IDOR risk. | Produce a deny-by-default authorization matrix and enforce authorization in application use cases, not routes alone. Resolve every child through its authorized parent/tenant and constrain mutable fields to prevent tenant/owner/visibility mass assignment. Generate adversarial tests from the matrix. | Application/security owner; **before affected use cases** | Open — implementation blocker |
| SEC-08 | **Medium** | Backup/PITR, bucket versioning, quarantine, logs, audit data, and isolated restore projects can defeat deletion or expand exposure; access and retention are not finalized. | Create a data-location/retention schedule covering primary data and every copy, with backup encryption/access, restoration controls, expiration, deletion propagation after restore, restore-project teardown, legal/audit exceptions, and user-facing limitations. Test restore and deletion reconciliation together. | Operations/privacy owner; **before production** | Open — deployment blocker |
| SEC-09 | **Medium** | CI/CD and supply-chain measures mention SBOM and scanning but lack enforceable provenance, dependency policy, workflow trust controls, and vulnerability disposition. A compromised build has full application reach. | Pin GitHub Actions by immutable reference, minimize workflow permissions, protect environments and production promotion, restrict WIF claims to repository/ref/environment, lock and hash dependencies, sign/attest artifacts and verify the promoted digest, scan source/dependencies/images/IaC/secrets, and define severity SLAs/exceptions. Preserve evidence for the deployed digest. | Platform/security owner; **before deployment pipeline can promote production** | Open — deployment blocker |
| SEC-10 | **Medium** | Logging excludes several sensitive values, but pseudonym generation, log/trace scrubbing, access, retention, and diagnostic payload handling are undefined. Stable unsalted tenant pseudonyms and exception bodies can still expose or correlate users. | Define keyed/rotatable pseudonyms, centralized allowlist-based telemetry fields and redaction, no request/response bodies by default, access controls, retention, region, deletion rules, and tests that seed canary secrets/PII into errors and inputs and assert they never reach telemetry. | Operations/privacy owner; **before production observability** | Open — deployment blocker |
| SEC-11 | **Medium** | Global abuse controls are not defined for login, search, writes, export, signed URL issuance, upload intents/finalize, and expensive reports. This risks cost exhaustion and availability loss. | Define per-account/IP/tenant quotas and rate limits, request and pagination bounds, timeouts, concurrency limits, idempotency semantics, suspicious-use alerts, and safe error behavior. Test exhaustion and idempotency-key scope (tenant + operation + payload). | Application/operations owner; **before public exposure** | Open — deployment blocker |
| SEC-12 | **Low** | The architecture requests Google `email` by default even though authority uses `sub`; retaining email increases privacy impact and may exceed minimum data needs. | Decide whether the UI truly requires email. If not, remove that scope/storage; if yes, document purpose, visibility, update behavior, retention, and deletion. Never use verification state or email domain as authorization unless separately approved. | Product/privacy owner; **before OIDC consent configuration** | Closed — ADR-007 omits the email scope and storage; adding email triggers renewed review |

No finding is accepted merely by being listed. Critical/high findings block their
affected implementation or deployment as stated; medium findings marked as
implementation blockers also require resolution before their affected code.

## 6. Accepted and deferred risks

### Accepted by this review

None. Risk acceptance belongs to the human owner and must identify the finding,
rationale, compensating controls, affected environment/data, approver, and an
expiry/review date. Architecture status and this review must then link that
record.

### Deferred by product scope (not risk acceptance)

- Android authorization and token storage are deferred until Android work, but
  SEC-05 must be resolved before that client is implemented.
- Telegram is deferred from the MVP; SEC-04 must be resolved before any Telegram
  integration is implemented or exposed.
- Sharing behavior and moderation are deferred, while the dormant schema is in
  scope now. Grants and visibility must remain unreachable through MVP APIs,
  and SEC-01/SEC-07 tests must prove that policy.
- Automated imports, offline mutation sync, recommendations, and transcoding are
  out of scope. Introducing any of them requires an updated threat model.
- Exact production region, HA, media retention, and backup choices are deferred
  to human cost/privacy approval and remain deployment blockers.

### Provisional anonymization decision

The owner's instruction to “assume anonymization for now” is recorded only as a
design hypothesis. It is **not an accepted privacy risk and not evidence that
retained history is anonymous**. The architecture's non-login principal plus
identity removal may reduce direct identifiability, but snapshots, dates,
free-text notes, media, source metadata, and operational copies can permit
re-identification. Until SEC-02 and SEC-08 close, production promises must not
claim anonymization, and real-user account deletion must not rely on this flow.

## 7. Verification required to close the gate

At minimum, the security test design must trace every finding to automated or
manual evidence and cover:

- OIDC state/nonce/PKCE and token validation, login CSRF, redirect abuse,
  fixation, expiry, logout/revocation, and destructive-action reauthentication;
- CSRF and stored/reflected XSS; input validation, mass assignment, injection,
  pagination/request bounds, and rate limiting;
- cross-tenant read/write/list/search/count/join access for every private
  resource, pooled-connection reuse, missing RLS context, jobs, grants, exports,
  deletion, and runtime-role limitations;
- signed URL scoping and expiry plus hostile upload, quarantine/finalize,
  overwrite, orphan cleanup, cross-tenant attachment, malware response, and
  deletion scenarios;
- anonymization/deletion/export across live tables, identity provider mappings,
  media, logs, audit records, backups, PITR restoration, and failed/retried
  workflows;
- IAM/WIF negative cases, secret and telemetry canaries, dependency/image/IaC
  scanning, artifact provenance, rollback, restore, and incident runbooks; and
- Telegram authenticity, replay, linking, unlinking, and abuse tests only when
  that integration enters scope.

Evidence must identify the code/configuration revision and environment. Tests
must use PostgreSQL with RLS enabled; an alternate in-memory database cannot
establish tenant-isolation correctness.

## 8. Gate decision

1. **Architecture review input:** Conditional security pass. The proposed
   modular boundary, identity mapping, tenancy model, private storage pattern,
   and deployment direction are reasonable foundations. Human architecture
   approval may proceed only with the open findings carried as explicit gates;
   this review does not approve ADRs on the owner's behalf.
2. **Test design:** May proceed only after human architecture approval. It must
   incorporate Section 7 and every finding, and independent test-design review
   is still required.
3. **Production implementation:** **Not generally authorized.** Security-sensitive
   components may begin only after the corresponding “before implementation”
   finding is resolved and independently re-reviewed. Non-sensitive scaffolding
   still requires the other project approval gates.
4. **Production deployment or real user data:** **Blocked.** SEC-02, SEC-03,
   SEC-08, SEC-09, SEC-10, and SEC-11, all applicable authentication/isolation
   findings, human privacy decisions, named operator, and the project's other
   deployment gates must be closed.
5. **Re-review triggers:** Material changes to identity, tenancy/RLS, catalog
   sharing, snapshot contents, privacy lifecycle, media, API exposure, clients,
   cloud topology, CI/CD trust, or new import/offline/processing features require
   an updated independent security review.

## 9. Addendum — ADR-005 module/data boundaries (2026-09-27)

Independent security review now also covers ADR-005 and the corresponding
module/data ownership section. The initial review required tenant-consistent
cross-schema references, owner-interface-only read models, protected reporting
projections, controlled `ActorContext` provenance and an explicit multi-module
account-deletion protocol. Those requirements are now architecture commitments.

ADR-005 receives a conditional security pass with no new finding IDs and may
proceed to human approval. This does **not** close SEC-01, SEC-02, SEC-07 or
SEC-08: exact database/RLS evidence, the final privacy policy, the deny-by-
default authorization matrix, and backup/retention/deletion-propagation evidence
remain open at their existing gates. Implementation and deployment authorization
are unchanged, and no risk is accepted by this addendum.

**Subsequent disposition:** The human owner approved ADR-005 on 2026-09-27. This
approval accepts the module/data boundary decision but does not close or accept
any security finding; all gates above remain in force.

The human owner subsequently approved ADR-002 and ADR-003 on 2026-09-27. These
architecture approvals do not close or accept any security finding. In
particular, the privacy-policy gates on retained snapshots and the
tenant-isolation verification gates remain in force.

The human owner subsequently approved ADR-004 on 2026-09-27. This architecture
approval does not close or accept SEC-03 or any other security finding. Media
policy, region, retention/deletion, IAM/CI evidence, production topology, and
deployment gates remain in force.

## 10. Addendum — staged first-increment scope (2026-09-29)

Independent security review assessed proposed ADR-006. Media, account-deletion
and offline behavior are absent from the first increment. The architecture now
requires that its runtime database role have no privilege on dormant media
tables, that no media repository or command adapter be registered, and that no
media route appear in the first-increment API. Negative tests must prove all
three conditions.

SEC-03 becomes a blocker when media implementation begins and before any
deployment that enables media; it does not block a media-free first increment.
Likewise, media-specific retention and region choices activate with that
feature. SEC-02 and SEC-08 remain production gates even without an
account-deletion UI because real-user identity, history, logs and backups still
require an approved lifecycle. SEC-01, SEC-05, SEC-06 and SEC-07 remain at their
first-increment implementation gates, and SEC-09 through SEC-11 remain public-
production gates.

The initial review's gate decision is narrowed only by the conditional SEC-03
scope above. No finding is closed or risk accepted. ADR-006 remains Proposed
pending the owner's database-migration clarification, and any later media,
account-deletion or offline implementation requires security review at its
documented gate.

**Subsequent disposition:** The human owner confirmed on 2026-09-29 that ordinary
additive migrations are allowed and accepted ADR-006's stable-foundation
approach. This does not close or accept any security finding. The first-increment,
feature and deployment gates above remain in force.

## 11. Addendum — web identity and session architecture (2026-09-29)

Independent security review assessed ADR-007. Omitting email closes SEC-12 and
reduces direct-identifier retention; email may be
added only with renewed purpose, consent/scopes and lifecycle controls. Verified
issuer/subject identity, explicit linking, allowlisted provisioning, opaque
server-side sessions, rotation, expiry and revocation are sound foundations.

This does not close SEC-01, SEC-05, SEC-06 or SEC-07. Test design must specify
and verify exact cookie/session persistence, OAuth error and redirect behavior,
CSRF binding, fixation/replay resistance, browser security headers, XSS controls,
tenant context and deny-by-default authorization. No security risk is accepted,
and production implementation remains gated.
