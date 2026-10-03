# ADR-008: Fail-closed PostgreSQL tenant context and runtime roles

- Status: Accepted
- Date: 2026-09-30
- Owners: Identity/data boundary / human owner
- Work item: GitHub Issue #5 (`MVP-02`)

## Context

ADR-003 requires non-null tenant ownership, scoped repositories, application
authorization and PostgreSQL row-level security (RLS) as defense in depth. The
foundation architecture requires transaction-local tenant context and a runtime
role that cannot bypass RLS. SEC-01 blocks tenant-backed repositories until the
roles, grants, context lifecycle, pooled connections, workers, migrations and
adversarial evidence are exact.

Every normal private-data query is explicitly tenant-scoped in the repository.
RLS is an independent database backstop for an omitted or incorrect predicate;
it is not a replacement for visible application data scoping. Neither layer is
the primary object/action authorization decision, and neither can contain a fully
compromised application that legitimately holds the runtime credential and can
submit arbitrary SQL. The application must derive `ActorContext` from validated
identity and authorize every use case. SQL injection prevention, least privilege
and monitoring remain independent controls.

## Decision

### Database roles

The MVP uses exactly two application database identities:

| Role | Availability | Attributes and purpose |
| --- | --- | --- |
| `app_owner` | Controlled migration/deployment process only | Owns application schemas, tables, functions and RLS policies. It is privileged over those objects but remains `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`. Its credential/IAM binding is never available to the running application. |
| `app_runtime` | Running application only | `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT`; receives only required schema usage, reviewed function execution and table/sequence DML. It cannot become `app_owner`. |

There is no separate migrator role, intermediate object-owner role or identity-
module owner role in the MVP. The controlled migration job authenticates directly
as `app_owner`, applies reviewed schema migrations and exits. Application
instances, developers' runtime profiles, HTTP processes and domain code never
receive, assume or impersonate `app_owner`. Separate deployment/runtime cloud
identities and secret/IAM controls must enforce that operational boundary.

Ephemeral integration databases create the production-named `app_owner` and
`app_runtime` roles from the same bootstrap. Test harness administration uses a
separate cluster-local fixture principal, but all runtime-isolation evidence
reconnects as `app_runtime`; owner results are migration/setup evidence only.

`PUBLIC` receives no application-schema or function privileges. Migrations
explicitly revoke `CREATE` on schema `public`, database `CREATE`, and database
`TEMP` from `PUBLIC` and `app_runtime`; runtime receives only `CONNECT` plus its
listed object privileges. Runtime cannot create or own application objects,
alter tables or policies, grant roles, execute unapproved security-definer
functions, or access dormant `media` objects.

Default privileges are set for `app_owner` with `ALTER DEFAULT PRIVILEGES FOR
ROLE app_owner` for every object kind, especially removal of default `PUBLIC`
function execute. Existing-object ACLs are revoked before explicit runtime
grants. Role membership, database/schema privileges, default ACLs and effective
per-object grants are asserted after every migration.

Cloud SQL identities, deployment permissions and credential rotation are owned
by the platform issues; they must prove that only the controlled deployment
principal can authenticate as `app_owner` and the running service can authenticate
only as `app_runtime`.

### Tenant-bearing tables and policies

Every private table has a non-null `tenant_id uuid`. Primary/unique and foreign-
key shapes include tenant identity wherever a child references a private parent,
so an ID-only relationship cannot cross tenants. Each private table enables and
forces RLS, including tables owned by `app_owner`:

```sql
ALTER TABLE catalog.entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.entry FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON catalog.entry
  FOR ALL TO app_runtime
  USING (tenant_id = identity.current_tenant_id())
  WITH CHECK (tenant_id = identity.current_tenant_id());
```

Equivalent explicit policies apply to each command/query role if runtime duties
are split later. No permissive catch-all policy is allowed. Reference data that
is intentionally global is listed in a reviewed manifest and has no tenant
policy; absence from the manifest makes a new application table private by
default. Dormant grant/visibility data remains private and cannot activate
sharing through an RLS policy.

### Explicit repository tenant scoping

Every repository operation over tenant-private data requires the immutable
`ActorContext`; no public repository method accepts an optional/raw tenant UUID,
and no generic unscoped `find(id)`, list, count, search, bulk or delete operation
is permitted. The repository derives one bound tenant parameter from that
context and includes it visibly in its SQL:

- selects, updates, deletes, existence checks, aggregates and counts include
  `resource.tenant_id = :actor_tenant_id`;
- inserts set `tenant_id` from `ActorContext` and do not accept it in mutable
  request or domain input;
- private parent/child and join queries scope every participating private side
  through tenant-consistent keys/predicates, not only the root table;
- bulk operations apply one actor tenant to the complete statement and reject
  mixed-tenant identifiers before execution; and
- pagination, search, ancestry and uniqueness/existence probes retain the tenant
  predicate so counts, errors and cursors cannot become cross-tenant signals.

For the owner-only MVP, each occurrence/range variable of a tenant-private table
must be structurally anchored to the single actor-tenant bind. An equality chain
such as `child.tenant_id = parent.tenant_id` is sufficient only when the chain
also reaches `:actor_tenant_id`; equality between private tables alone is not
actor scoping. This applies independently to aliases, self-joins, CTEs, derived
or correlated subqueries, `EXISTS`, lateral joins, set-operation branches and
each ORM-emitted relationship/eager/lazy follow-up statement.

Future catalog sharing does not remove explicit repository scoping. Because a
grantee may legitimately read catalog rows whose owner tenant differs from the
actor tenant, activating sharing requires a reviewed replacement for affected
catalog reads: visible ActorContext-derived grant/authorized-scope predicates,
mirrored grant-aware RLS and use-case authorization across joins, search, counts,
cursors and revocation. The query registry and mutation expectations must change
under that feature's architecture, security and test-design reviews. The MVP
continues to require owner equality and dormant grants cannot activate access.

The explicit predicate and transaction-local RLS context are independently
derived from the same validated `ActorContext`. Unit-of-work setup reads back the
database context before the repository executes; an inconsistency fails before
the business statement. RLS applies its own `USING`/`WITH CHECK` expression, so
a missing or wrong repository predicate cannot expose or mutate another tenant.
Repository scoping does not authorize an action: the use case still checks the
approved ownership/grant/action matrix before calling the repository.

Global reference queries and the five pre-authentication control-plane tables are
the reviewed exceptions. Global tables are reconciled with their manifest.
Control-plane access occurs only through fixed privileged functions and is never
disguised as an unscoped normal repository.

Traceability comes from typed repository contracts, a registry mapping every
private table/action to query tests, and semantic inspection of the final
statement plus bind provenance immediately before driver execution and before
PostgreSQL adds RLS predicates. The checked registry is keyed by repository
method, action, emitted statement variant and private table occurrences; it is
mechanically reconciled with public repository methods, ORM statement factories
and every raw/text SQL call site. Unregistered generic/dynamic execution is
prohibited. Global, control-plane and migration exceptions name their category
and owner. Production telemetry records only safe operation and policy-result
categories plus correlation ID; it does not log raw SQL, tenant UUIDs or private
values.

`identity.current_tenant_id()` is a stable, non-security-definer function owned
by `app_owner`. It reads `current_setting('app.tenant_id', true)`, rejects
missing or empty values with SQLSTATE `42501` (`insufficient_privilege`), parses
exactly one UUID and returns it. Invalid values fail the statement. It never
supplies a default, wildcard or system tenant. Runtime receives execute access
only to the reviewed context/query functions it needs. All application and
privileged functions schema-qualify object and `pg_catalog` references and set a
fixed safe `search_path`; runtime cannot create in any schema on that path or
create temporary objects.

### Pre-authentication identity bootstrap

External-identity lookup, invitation and first-login bootstrap occur before a
tenant `ActorContext` exists. The identity module therefore maintains a reviewed
third table category, **authentication control plane**, distinct from tenant-
private data and global reference data. The category contains only `identity.user`, `identity.tenant`,
`identity.external_identity`, `identity.invitation` and `identity.login_session`
and is a checked five-table manifest. User, external identity and invitation do
not carry a tenant ID before linkage; tenant is itself the tenant identity. Login
sessions carry the linked user and tenant IDs but their cookie digest must be
resolved before `ActorContext` exists. These tables are never queried by ordinary
domain repositories.

`app_owner` owns these five tables and their narrowly scoped security-definer
functions. The five control-plane tables do not use tenant RLS; isolation is the
deny-by-default ACL plus the reviewed function boundary. `PUBLIC` and
`app_runtime` have no direct table or sequence privilege. The closed five-table
manifest, absence of RLS, `app_owner` ownership and exact ACLs are catalog-tested
as an explicit exception; any sixth table fails CI. Because `app_owner` owns all
application objects, every security-definer function uses fully qualified
objects, a fixed safe search path, least-result contracts and an explicit runtime
execute grant; no generic privileged function is permitted.

The owner functions resolve an existing active issuer/subject or an opaque
session-token digest to the minimal actor/tenant tuple, create/revoke a digest-
only linked login session under the SEC-05 lifecycle, or atomically consume a
valid invitation to create exactly one
user, personal tenant and external identity. They do not write catalog tables or
owner grants. A personal catalog and its owner grant are created later by the
catalog module inside an ordinary tenant-context unit of work, preserving module
ownership; first-login atomicity covers only the approved identity triple. The
functions use fixed `search_path = pg_catalog, identity`, fully qualified objects,
constrained inputs and least-result shapes. Only `app_runtime` may execute them;
runtime cannot assume `app_owner` and has no direct control-plane table
privileges.

Bootstrap accepts provider issuer/subject only after application-side OIDC
validation and a one-way invitation-token digest. The database atomically checks
unused status, expiry and permitted issuer, consumes it and enforces uniqueness.
Unknown/disabled identity, invalid/expired/replayed invitation, provider mismatch
and concurrent consumption return one stable non-enumerating failure and create
nothing. The function cannot accept tenant, user, owner-grant or visibility IDs
from a client. Session lookup exposes no digest or identity attributes and gives
the same result shape for unknown, expired, revoked or wrong-context sessions.
SEC-05 owns cookie/session lifecycle and Issue #6 may narrow these contracts; any
expansion of table access, function result or execute audience returns to this
review. This ADR owns the database privilege and isolation boundary.

`identity.user(id, state)` and `identity.tenant(id, owner_user_id, state)` use
opaque UUIDs; `tenant.owner_user_id` is a non-null unique foreign key so one user
has exactly one personal tenant in the MVP. `external_identity(provider,
subject, user_id, state)` has a unique `(provider, subject)` and non-null user
foreign key. Session has non-null user/tenant foreign keys plus a constraint
that the tenant is owned by that user. Resolution joins these relationships and
requires active external identity, user and tenant. Bootstrap uses one
transaction, database uniqueness plus atomic invitation consumption, and on
retry returns the already-linked tuple only for the same consumed invitation and
issuer/subject; every conflicting combination fails without partial rows.


### Post-bootstrap catalog provisioning

Identity bootstrap commits independently of catalog ownership to preserve
ADR-005 module boundaries. This does **not** run on every authenticated HTTP
request. A new tenant starts with identity-owned
`tenant.provisioning_state = catalog_pending`; this is orthogonal to the
user/tenant lifecycle state (`active` or `disabled`). A pending but active tenant
can authenticate, while a disabled user or tenant cannot be made active by any
provisioning transition. After the first successful login/bootstrap creates an
`ActorContext`, the login orchestration invokes the idempotent catalog public
command `ensure_personal_catalog(ActorContext)` once. In one catalog transaction,
that command creates both the personal catalog and its owning grant or observes
the already complete pair. A unique personal catalog per owner tenant and a
unique owning grant for that catalog make concurrent calls converge; catalog-row
or grant failure rolls back the pair.

Only after the catalog public port returns its typed successful result does the
login orchestration call an internal identity public command that derives the
target from immutable `ActorContext` and conditionally changes provisioning state
from `catalog_pending` to `ready`. It accepts no client-supplied tenant, user or
target state, is not a generic state setter, is idempotent when already ready,
and requires lifecycle state to remain active. It cannot revive a disabled
account.

Normal session validation only reads account state; it never provisions catalog
data. A ready account goes directly to the requested use case with no ensure
call. If catalog creation or the final ready-state update fails, identity/session
remains valid and the state remains `catalog_pending`. Minimal profile/logout is
available, while catalog/practice commands return a stable provisioning-pending
response without attempting a side effect. Retry occurs only from a later login
callback for that still-pending account—not from arbitrary requests. The MVP has
no provisioning-retry HTTP endpoint or client command; adding one would require
an approved state-changing API contract plus authentication, authorization, CSRF,
method and idempotency tests.

If catalog creation committed but marking ready failed, retry calls the same
idempotent catalog command, observes the existing catalog/grant, and then marks
the account ready. Concurrent pending login callbacks use conflict-safe retry:
each receives a stable success/pending outcome, exactly one complete catalog/
grant pair exists, and a caller can complete the conditional ready transition.
Raw uniqueness errors and whether the catalog pair already committed are never
exposed; all pending substates have the same external response.

This inline login-callback path is the only first-increment reconciliation
mechanism. No worker, request middleware, generic
session resolver, CLI or scheduled reconciler invokes provisioning, and identity
code never writes catalog tables.

### Transaction context lifecycle

One infrastructure component creates database units of work. Repositories
cannot receive raw tenant UUIDs or acquire independent connections. The unit of
work accepts only an immutable `ActorContext` created by identity
infrastructure, then:

1. checks out a connection and requires it to be idle;
2. rolls back unexpected open work and executes `RESET app.tenant_id` before use;
3. begins a transaction;
4. as the first transaction statement, executes parameterized
   `SELECT set_config('app.tenant_id', :canonical_uuid, true)`;
5. reads `identity.current_tenant_id()` and compares it with the expected UUID;
6. only then invokes a repository; and
7. commits or rolls back, followed by pool reset that rolls back and resets the
   tenant setting before the connection becomes reusable.

The preflight in steps 4-5 is the deterministic missing/invalid-context failure;
raw RLS expressions are not assumed to execute on an empty scan. The `true`
argument makes the setting transaction-local. Autocommit repository
access, lazy work after the unit of work ends, nested tenant changes, and opening
a second connection inside the use case are prohibited. A nested unit of work
may reuse the same transaction only with the same `ActorContext`; a different
tenant raises before SQL. Cancellation and exceptions always invalidate or
reset the connection if cleanup cannot be proved.

Pool checkout/check-in hooks are defense in depth, not a substitute for the
first-statement setup and verification. The database adapter exposes no generic
execute handle to delivery/domain code. SQL statements bind values; tenant
context is never interpolated.

PostgreSQL custom settings are settable by a session, so this design does not
claim the GUC authenticates a tenant against a malicious runtime connection.
Application provenance and use-case authorization establish authority; the
transaction-local GUC supplies fail-closed query scoping and protects against
missing/mistaken predicates. Runtime-role attempts to bypass RLS by changing
roles, policies, ownership or RLS attributes must fail. Directly setting a
different well-formed GUC is included in threat evidence and documented as an
application-compromise boundary, not misreported as an impossible database
control.

### Background jobs

No background/domain worker, scheduler, CLI/management command, message
consumer, async callback or tenant data-processing migration callback is allowed
in the first increment. A mechanically checked production-composition manifest
lists every process entry point, executable, scheduled task, async consumer and
outbound job registration in the built/deployed artifact. Issue #9 tests that
the artifact exposes only that allowlist; a new execution root fails CI until it
has an approved tenant provenance, authorization, context and replay design plus
security/test review. The schema migration job described below is the sole non-
HTTP process and cannot execute domain repositories.

### Migrations and privileged data changes

The controlled migration/deployment job authenticates directly as `app_owner`,
runs the reviewed migration once and exits. Every migration declares its owning
module/schema. Cross-module constraints still require the ADR-005 coupling-
register approval. The running application has no owner credential, membership,
`SET ROLE` path or generic migration endpoint.

First-increment migrations are limited to schema changes, RLS policies, grants,
constraints, indexes, approved reference/seed data and transformations that do
not require privileged traversal or mutation of existing tenant-private rows.
They do not temporarily grant owner capabilities to `app_runtime`, disable or
weaken RLS, or add an all-tenant data-migration function. No temporary
`GRANT`/`REVOKE` choreography is introduced.

“Reference/seed data” means only reviewed global-reference rows or initialization
of a newly created empty table. A permitted non-privileged transformation cannot
read, rewrite, backfill or derive from existing tenant/user data. The migration
classification manifest and tests distinguish this setup from a privileged
tenant-data migration; ambiguous cases fail closed into the future design gate.

A migration that must inspect or mutate existing tenant-private data with owner
privilege is not an MVP requirement and is deliberately undesigned. If a concrete
need arises, it triggers a new security-sensitive design and independent
architecture, security and test-design review before the migration is written or
run. That future design must address tenant iteration or other scope, backups,
affected-row reconciliation, idempotency, interruption/retry, rollback or forward
repair, audit evidence, RLS handling and proof that the running application never
receives privileged access. `app_owner` capability is not itself permission to
perform an unreviewed data migration.

Migration failure must leave a compatible schema or invoke a pre-reviewed
schema-level recovery procedure. Catalog assertions after migration verify
ownership, FORCE RLS, policies, default ACLs, runtime grants and the absence of
unexpected privileged functions or runtime owner reachability.

### Observability

Tenant-context failures emit a stable error category, request/correlation ID,
role and operation—not raw tenant UUID, SQL, notes or record values. Metrics
distinguish missing, invalid, mismatch and cleanup failures. Pool reset failure
retires the connection and alerts in deployed environments. Telemetry follows
SEC-10 and cannot be considered evidence until positive-sentinel controls prove
each sink is being observed.

## Required implementation evidence

Issue #9 (`MVP-06`) must implement the approved design and pass PostgreSQL tests
using the runtime role. The matrix includes:

- own-tenant runtime success and cross-tenant denial for read/write/update/delete/list/search,
  aggregate/count, joins, ancestry and child access on every private resource;
- foreign-existing versus same-shaped nonexistent equivalence through repository
  and HTTP paths;
- missing, empty, malformed, mismatched and changed tenant context;
- transaction commit/rollback, nested same/different tenant, cancellation and
  setup failure before any repository statement;
- connection reuse A -> B -> no-context, plus injected session-level stale
  settings and failed reset/connection retirement;
- runtime attempts to change role, alter/disable/bypass RLS, alter policy/table,
  create in application schemas, invoke ungranted functions, access owner tables
  and dormant media objects;
- all tenant-consistent composite constraints and `WITH CHECK` writes;
- composition-manifest proof that unapproved worker/executable roots are absent;
- schema migration from empty and each supported fixture, catalog role/grant/policy
  assertions, owner/runtime identity separation and runtime denial of migration
  access;
- concurrency and pooled execution proving context does not bleed between tasks.

For every private operation, evidence separately proves both controls: generated
repository SQL contains the expected bound tenant predicates on every private
table/join, and real-PostgreSQL execution as `app_runtime` enforces FORCE RLS.
Mutation cases remove or corrupt each repository predicate and must fail the
query-structure suite even when RLS would still prevent data exposure; separate
RLS mutations must fail the integration suite. This prevents one layer from
masking absence of the other.

Bootstrap evidence covers direct-table denial; function ACL/search-path safety;
valid existing identity and digest-only session lookup/create/revoke; atomic
user/tenant/external-identity creation; linked user/tenant/session constraints;
invalid, expired, wrong-issuer and replayed invitations; simultaneous
consumption; duplicate issuer/subject; client-supplied ownership fields; partial-
failure rollback; indistinguishable unknown/disabled identity results; and
indistinguishable unknown/expired/revoked session results.

Issue #9 provides foundation role, policy, context, pool, migration, bootstrap
and then-present schema evidence before its repositories can merge. Each later
feature issue must register every new table, relationship, action and HTTP path
in the cumulative inventory and pass its resource matrix before merge. SEC-01's
design portion may pass here, but the finding is not globally closed until the
implemented mechanism is re-reviewed and all then-present private resources are
reconciled.

Tests must also demonstrate application authorization so RLS is never treated as
the sole control. An alternate in-memory database, table owner, superuser or role
with `BYPASSRLS` cannot provide isolation evidence.

## Alternatives considered

- **Repository predicates without RLS:** rejected because an omitted predicate
  could expose a tenant and would violate the approved defense-in-depth design.
- **RLS without explicit repository predicates:** rejected because normal query
  scope would be less visible and auditable, and a policy/configuration failure
  would have no independent application data-scoping backstop.
- **Schema or database per tenant:** stronger physical separation but excessive
  migration/connection/operations cost for the MVP and inconsistent with the
  approved shared-schema architecture.
- **Session-level tenant setting:** rejected because pooled connections can carry
  stale authority across requests.
- **Database session role per tenant:** rejected because it creates unbounded
  roles/credentials and complicates pooling and future grants.
- **Security-definer tenant setter as authentication:** rejected because a
  runtime caller able to pass an arbitrary UUID gains no cryptographic authority
  merely by calling a function; it would create a false security claim.
- **Separate migrator plus temporary grants:** rejected for the MVP because no
  concrete privileged tenant-data migration requires it. It adds roles,
  membership and grant/revoke failure modes without current product value.
- **Owner/runtime same identity:** rejected because table owners can bypass ordinary
  RLS behavior and need schema privileges forbidden to the application.

## Consequences

Repositories and jobs must run inside explicit tenant-scoped transactions, and
test infrastructure must use real PostgreSQL roles. Pool handling remains explicit, but absent/stale context fails closed and ordinary query bugs
receive a database backstop. Fully compromised runtime credentials remain a
documented trust boundary requiring application authorization, injection
prevention, least privilege, monitoring and incident response.

## Security / privacy impact

This ADR is intended to close the design portion of SEC-01 only after independent
security review. SEC-07 application authorization remains separate. No risk is
accepted, and the ADR does not claim protection from a malicious process holding
valid runtime credentials. Implementation evidence and security re-review are
required before SEC-01 can close.

## Human approval

Approved by the human owner on 2026-10-03. This approval accepts the two-identity
`app_owner`/`app_runtime` model, explicit repository tenant predicates plus FORCE
RLS, transaction-local tenant context and pool lifecycle, pre-authentication
control-plane boundary, post-login catalog provisioning trigger, schema-migration
boundary and required test evidence.

Approval closes the SEC-01 **design** gate only. It does not close SEC-01,
authorize tenant-backed implementation before the remaining gates, accept a
security risk, approve privileged tenant-data migration behavior, or close
SEC-05/SEC-07. Issue #9 must implement this decision against real PostgreSQL and
pass independent security/code review; Issue #16 must prove deployed owner/
runtime credential separation.

Decision: approved.
