# Independent architecture review — Issue #9 authentication database delta

- Date: 2026-10-22
- Reviewer: `/root/architecture_review`, independent of the design author
- Material: `auth-foundation-design.md`, `auth-foundation-test-design.md`, accepted ADR-005/008/011, the approved Issue #6 authentication contract and its architecture review, and the existing 000–004 foundation
- Verdict: **pass for the specified database-only delta**. Separate security/test-design gates and final implementation evidence remain required.

## Findings and disposition

1. **AF-AR1 — The previous five-table/authentication-design blocker is stale. Resolved.** Accepted ADR-011 expressly authorizes the exact seven-table control-plane category and fixed authentication wrappers. The new design correctly updates the inventory without representing Issue #6 design approval as SEC-05 runtime evidence. `user_preference` remains private with FORCE RLS; no eighth exception or direct runtime control-table grant is introduced.
2. **AF-AR2 — Unknown preallowlisted identities need an admission representation without precreated authority. Resolved.** Nullable admission-kind/subject metadata in the existing owner-controlled invitation table distinguishes bearer admission from issuer/subject-bound allowlist admission. Legacy NULL kinds retain bearer interpretation without backfill. Finish consumes the matching admission only inside the identity/session atomic unit. A random undistributed allowlist digest is not a caller credential, no caller boolean authorizes provisioning, and no identity triple is created before validated finish. Review the exact DDL/check/index and failure cases during code review.
3. **AF-AR3 — Additive session linkage must not silently reinterpret existing sessions. Resolved.** Revision 005 preserves all original migration artifacts and adds nullable external-identity/CSRF linkage. Legacy-incomplete sessions resolve to no tuple and are not touched or associated by a privileged backfill. The same-schema composite foreign key preserves user linkage. Ordinary schema/index/constraint validation may scan rows; it does not authorize bespoke privileged data traversal or migration of existing tenant data.
4. **AF-AR4 — Failure budgets and authority need different rollback boundaries. Resolved in design.** Invitation-attempt consumption precedes the protected issuance subtransaction; ordinary eligibility/issuance failure preserves that attempt while rolling back invitation consumption, the identity triple, user-issuance budget, session and transaction success. Infrastructure-level transaction abort is correctly distinguished and cannot promise durable counters. The committed claim remains consumed. Real PostgreSQL fault/concurrency evidence must prove these boundaries.
5. **AF-AR5 — Ready targeting must preserve ADR-008 actor provenance. Pass with the explicit adapter boundary.** The internal `mark_catalog_ready(bytea)` wrapper narrows its database target to one valid linked active session and accepts no caller user/tenant/state. The future Issue #10 public command must still require immutable validated ActorContext, verify it agrees with that session linkage, and call only after typed catalog success. No digest-ready public API or generic state setter is approved. This internal signature does not authorize a public-contract change or catalog-table access from identity.
6. **AF-AR6 — Capacity and cleanup must remain bounded per HTTP operation. Resolved in design.** The exact two reserved rows live inside the seventh table and count toward its physical cap. Cleanup runs only once through the IP-start/IP-callback limiter stage, with at most 100 indexed rows from each store, rather than repeating a batch in every downstream wrapper. Full admission fails closed without live-row eviction; normal session resolution performs no cleanup, provisioning or limiter access.

## Architecture assessment

The fixed SECURITY DEFINER wrappers remain identity-owned, schema-qualified and
least-result, with safe search paths and exact signature/EXECUTE inventories.
Internal bootstrap, clock, cleanup and capacity helpers are not independently
runtime-executable. The existing tenant-context function remains security-invoker.
There is no raw-SQL or arbitrary target/state API and no cross-module mapping or
foreign-schema migration. Database digests and opaque AEAD ciphertext are
storage inputs; this delta does not implement cryptographic primitives, claim
OIDC validation or introduce an authentication provider adapter.

The coarse transaction-scoped auth-control lock is an acceptable initial
serialization choice for the stated modest single-application scope. Clock time
is sampled after acquisition, deadlines use exact equality semantics, waits are
bounded, and no provider/network call occurs while held. Tests must retain real
independent connections and observed lock barriers. The owner-only clock helper
is a real-clock wrapper in shipped SQL; temporary deterministic test replacement
must be restored and catalog-checked, with no runtime clock input/override.

Start/claim/finish/fail transitions preserve binder authority and one-shot
ciphertext delivery. Finish rechecks original expiry and binding before any
identity/session authority. Session resolution/revocation and deterministic
session-cap enforcement share the reviewed atomic lifecycle boundary. These are
design findings; passing review is not evidence that SQL already implements them.

## Gate and completion limits

No blocking architecture-design finding remains for this delta. Obtain the
separate independent security and test-design reviews before implementation,
then reconcile actual function bodies, signatures, ACLs, additive upgrade and
fault/concurrency evidence during independent code review. A checksum refresh
alone cannot approve a new privilege or query path.

HTTP remains exactly `/live` and `/ready`. No auth route, login callback,
ActorContext issuer, catalog repository/orchestration, worker, new deployable or
cloud resource is authorized by this review. Those implementation boundaries
remain assigned to Issue #10, with their own provenance/predicate/browser/provider
and security evidence. ADR-008 catalog-provisioning evidence remains open until
implemented; SEC-01/SEC-05 and the complete Issue #9 cannot be claimed closed
merely from this database-delta review.

## Scope and dependency reconciliation

2026-10-22: The approved backlog makes Issue #9 (MVP-06) a prerequisite for
Issue #10 (MVP-07), and explicitly prohibits exposing login/product behavior in
#9. The approved Issue #6 test design assigns its AUTH6 groups to MVP-07 except
shared role/pooling/catalog-foundation evidence. ADR-008's implementation-evidence
section assigns #9 the role/policy/context/pool/migration/bootstrap and
**then-present schema** matrix, and assigns new actions/HTTP paths to each later
feature's cumulative matrix.

Accordingly, #10's OIDC/browser/cryptographic integration, ActorContext issuance
and login-only catalog orchestration are not additional completion prerequisites
for #9. Requiring them first would introduce an unapproved #9↔#10 dependency
cycle. Existing catalog/grant shape, constraints, RLS and database isolation are
#9 foundation evidence; the future executable catalog public command and its
login journey are #10 evidence.

Once the complete implemented database foundation, including revision 005 and
its bootstrap/session functions, passes the reviewed then-present adversarial,
upgrade, concurrency/mutation, security/code and canonical artifact checks, #9
may advance to owner review and completion under its own issue acceptance.
Global SEC-01/SEC-05 and the future feature matrices remain cumulative/open;
this does not waive them or authorize any authentication/product exposure.
Earlier statements that those future matrices remain open describe their
separate feature/security gates, not a technical blocker requiring #10 before
#9. Final evidence still pending in this rolling review must pass independently.
