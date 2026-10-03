# Issue #5 tenant-isolation test design

- **Status:** Approved by the human owner on 2026-10-03
- **Design under test:** ADR-008
- **Security finding:** SEC-01
- **Implementation owner:** Issue #9 (`MVP-06`) after this design gate passes

## Test oracle

Runtime-isolation and application cases run on supported PostgreSQL with
production-equivalent migrations and production-named `app_runtime`. The
controlled migration fixture alone authenticates directly as production-named
`app_owner`; postconditions and runtime-denial evidence reconnect as
`app_runtime`. Owner results are migration/setup
evidence, not isolation evidence. An allowed own-tenant runtime operation must
succeed. A forbidden
operation must return no row or the stable authorization/not-found result, make
no state change, and expose no distinguishable count, cursor, header, error body
or material timing class compared with a same-shaped nonexistent resource.

After each failure, privileged fixture SQL verifies both tenants' state. Role,
policy, grant and connection-state assertions use PostgreSQL catalogs. HTTP cases
repeat the resource/action authorization matrix so repository success cannot
mask delivery/use-case failure.

## Required cases

### TD-01 — Role and grant baseline

- Assert every role's login, transitive membership, effective `SET ROLE` reach,
  database `CONNECT`/`CREATE`/`TEMP`, schema `CREATE` and object privileges.
- Assert the migration/deployment fixture can authenticate directly as
  `app_owner`, while the application/runtime deployment identity cannot obtain
  its credential, authenticate as it or reach it through direct/transitive
  membership or `SET ROLE`.
- Assert runtime cannot become owner, create/alter objects, change RLS,
  grant roles, invoke unapproved functions or access dormant media objects.
- Assert `PUBLIC`, per-creator default ACLs and actual function/table/sequence
  ACLs expose no application object; runtime cannot create in `public`, an
  application schema or temporary schema or hijack function resolution.
- Assert each private table is non-null-tenant, RLS-enabled, RLS-forced and has
  explicit `USING` plus `WITH CHECK`; assert global tables match the manifest.

### TD-02 — Context parser fails closed

- Unit-of-work preflight deterministically rejects missing, empty, whitespace,
  malformed, multi-value and non-UUID settings before repository execution.
- Direct SQL with missing/invalid context never discloses or mutates a row;
  require parser error only when the function/policy expression is evaluated,
  because an empty scan need not evaluate an RLS expression.
- A canonical UUID round-trips; there is no default/system/wildcard tenant.
- Context verification mismatch stops the unit of work before repository SQL.

### TD-03 — Resource/action isolation matrix

For every private parent and child, exercise owner and foreign tenant create,
read, update, delete/tombstone, list, search, filter, aggregate/count, join and
ancestry behavior. Include guessed IDs, a valid child under a foreign parent,
mixed-tenant bulk input, owner/tenant/visibility mass assignment, composite-key
violations and policy `WITH CHECK` failures.

For each operation, capture the final statement and bind metadata immediately
before driver execution and PostgreSQL RLS rewriting. A dialect-aware PostgreSQL
AST or ORM expression-tree oracle—not substring/regex matching or database
`EXPLAIN`—must prove every private table occurrence is transitively anchored to
the single actor-tenant bind. Prepared and batched execution retains statement-
shape and bind-provenance evidence. Tests verify the RLS context readback and all
repository tenant bindings originate through the typed immutable `ActorContext`
path, not merely from a request value with an equal UUID.

The statement suite covers aliases and self-joins; CTEs; derived/correlated
subqueries; `EXISTS`; lateral joins; `UNION`/set branches; `DISTINCT`, `GROUP BY`
and `HAVING`; joins used only for filter/order; relationship loaders; eager,
select-in and lazy/follow-up ORM statements; and aggregate/uniqueness/existence
probes. Each emitted statement passes independently. Keyset page and count SQL
retain the predicate, and cursor context is tenant-bound/validated so a cursor
cannot be replayed across tenants.

Write cases cover single/multi-row `INSERT`, `INSERT ... SELECT`, upsert/`ON
CONFLICT`, `UPDATE ... FROM`, `DELETE ... USING`, ORM flush/cascade and
relationship writes. Inserted tenant comes only from `ActorContext`; every source,
target, conflict-update branch and private relation is scoped; tenant identity is
immutable. Mixed-tenant batches fail before SQL and produce no partial write.

A checked statement-site registry is keyed by repository method, action, emitted
variant and every private alias/range variable. It mechanically reconciles public
repository methods, ORM statement factories and raw/text SQL sites; an
unregistered method/variant, registry entry without an executable test, generic
dynamic SQL or unnamed exception fails CI. Global, control-plane and migration
exceptions record category and owner.

### TD-04 — Non-enumeration

Compare repeated samples for a foreign-existing ID and a same-shaped nonexistent
ID at repository and HTTP layers. Assert semantic and byte equality of a
canonicalized body (normalizing only an explicit reviewed list of nondeterministic
fields), equality of every observable header value except an explicit allowlist,
and exact absence/equality of count, pagination and cursor metadata. Compare
bounded timing distributions where meaningful. Positive controls deliberately
vary error code/message, exact body length, header/redirect value, count and
cursor so the oracle must fail. Repeat after tombstone and invalid ancestry.

### TD-05 — Transaction and pool lifecycle

- Assert setup is the first transaction statement and repositories cannot run in
  autocommit or after unit-of-work close.
- Exercise commit, domain rollback, database error, cancellation and setup/read-
  back mismatch.
- Force a one-connection pool (or equivalent checkout instrumentation), record
  PostgreSQL backend PID and prove the same physical connection is reused for
  Tenant A, Tenant B and missing context.
- Inject a session-level stale setting, failed transaction and cleanup failure;
  prove reset or connection retirement prevents reuse.
- Exercise nested same-tenant success and different-tenant failure.
- Run concurrent randomized tenants over a small pool and assert zero bleed.

### TD-06 — Runtime bypass attempts

As runtime, attempt direct and transitive `SET ROLE`, table ownership/policy/RLS changes, DDL, grants,
unapproved security-definer functions, owner-schema reads and dormant media
access. All fail. Direct well-formed GUC alteration is documented as possible
for a compromised runtime session; application tests prove request input cannot
construct `ActorContext` or reach generic SQL execution.

### TD-07 — Production composition and worker absence

Reconcile a mechanically checked allowlist with every composition root,
executable, scheduler/CLI/management command, migration callback, asynchronous
consumer and outbound job registration in the built/deployed artifact. Only the
HTTP application and dedicated non-domain migration job are allowed. Mutation
fixtures add a differently named executable/consumer/callback and must fail CI.

### TD-08 — Schema migrations and privileged-data guardrail

- Empty-to-head and every checked supported fixture run through the controlled
  `app_owner` migration identity and validate schemas, owners, FORCE RLS,
  policies, constraints, indexes, default ACLs and exact runtime grants.
- Reconnect as `app_runtime` and prove it cannot invoke migrations, authenticate
  or `SET ROLE` as owner, alter owned objects/policies, or access owner-only data.
- Reconcile every actual migration against a checked classification manifest.
  First-increment migrations may contain schema changes, policies, grants,
  constraints, indexes, reviewed global-reference data, initialization of newly
  created empty tables, and only transformations proven not to read, derive from
  or mutate existing tenant/user rows. Ambiguous classification fails closed.
- A migration classified as requiring privileged access to existing tenant data,
  disabling/weakening RLS, a generic all-tenant function, or temporary runtime
  elevation fails CI and is blocked pending a new reviewed architecture/security/
  test design. No synthetic future mechanism or temporary grant choreography is
  accepted as MVP evidence.
- Inject failure into each schema migration phase and exercise the declared
  schema-compatible rollback or forward recovery. Validate the catalog after
  failure and retry; synthetic fixtures do not substitute for every actual
  migration in the supported manifest.
- Platform evidence that the running service cannot authenticate as `app_owner`
  is tracked to Issue #16 (`MVP-13`). Cross-schema changes fail without a
  registered ADR-005 exception.

### TD-09 — Observability hygiene

Trigger missing, invalid, mismatch and cleanup failures. A positive sentinel
first proves the enabled sink is observed. Assert correlation ID, safe category,
role and operation are present; raw tenant UUIDs, SQL, tokens, notes and record
values are absent. Cleanup failure retires the connection and emits the expected
metric/alert event.

### TD-10 — Coverage reconciliation and mutation controls

Generate a machine-readable inventory from PostgreSQL catalogs and reconcile it
with the reviewed global and authentication-control-plane manifests, tenant
tables/policies, special ownership/ACL/no-RLS classification, composite
relationships, authorization matrix and registered per-resource/per-action test
cases. Any unclassified table, action or relationship fails CI. Mutation cases
temporarily introduce `USING (true)`, permissive/missing `WITH CHECK`, a sixth
control-plane table, direct runtime control-plane grant, widened bootstrap
function result/privilege, a missing
child tenant predicate, ID-only relationship and cross-tenant join; the suite
must detect every mutation. Repository-layer mutations independently remove or
replace the explicit tenant predicate on a root, child, join, count, pagination
and bulk operation; the SQL-structure suite must fail even though intact RLS
would still deny cross-tenant rows. Conversely, RLS mutations must fail the real-
PostgreSQL suite even while repository predicates remain intact.

Additional negative mutations bind a request-supplied tenant, predicate the wrong
alias, constrain only a root, relate two tenant columns without anchoring either
to the actor, omit one CTE/union/subquery or eager-load statement, leave a cursor
unbound, omit an upsert conflict-update/source predicate, introduce raw SQL, or
omit a query site from the registry. Positive controls prove valid complex read
and write shapes pass. For the MVP, registry expectations require owner-tenant
equality; a future sharing feature must replace affected catalog expectations
with reviewed grant-aware scope tests rather than weakening/removing them.

### TD-11 — Pre-authentication identity bootstrap

Catalog assertions prove the five-table control-plane manifest, `app_owner`
ownership, exact table/function ACLs and the intentional no-RLS exception. They
also prove `app_runtime` cannot authenticate or assume owner. As runtime, direct
reads/writes of user,
tenant, external-identity, invitation and login-session tables/sequences fail.
Approved functions expose only least-result shapes. Exercise valid
external-identity and session-digest lookup, session create/revoke, and atomic
identity-only invited bootstrap plus invalid/expired/replayed/wrong-
issuer invitation, duplicate issuer/subject, simultaneous consumption, disabled
identity, unknown/expired/revoked session, ownership-field injection and partial
failure. Assert user/tenant/external-identity/session foreign keys, unique
provider-subject, exactly-one-personal-tenant, active-state joins and idempotent
same-invitation/same-subject retry versus conflicting retry. Assert stable non-
enumerating failures, no partial rows, safe fixed search paths, exact EXECUTE
audience and inability to assume `app_owner`. Assert bootstrap never
writes catalog tables; later personal-catalog/owner-grant creation uses the
catalog public port inside tenant context. Assert first bootstrap sets
`provisioning_state=catalog_pending` separately from active/disabled lifecycle
state, the login callback invokes ensure once, success marks `ready`,
and ordinary session validation plus ready-account HTTP requests never invoke
ensure. Assert catalog and owner grant commit atomically, with constraints for one
personal catalog per owner and one owning grant; inject failure between their
writes and prove neither persists.

Inject failure before/after the catalog transaction and before the conditional
ready-state update. Assert safe pending behavior and idempotent retry only on a
later pending-account login callback. Race two pending login callbacks, including
one whose ready update fails: both callers receive stable outcomes, exactly one
complete catalog/grant pair exists, a later/other caller reaches ready, and
subsequent ready requests never ensure again. Unknown database conflicts are not
exposed.

Assert the internal ready command derives user/tenant from `ActorContext`, accepts
no client target/state, permits only conditional `catalog_pending -> ready`, is
idempotent at ready, and cannot revive disabled lifecycle state. Forged tenant,
user and state inputs plus direct HTTP invocation fail. There is no retry endpoint
in the MVP. Assert no provisioning from middleware, session validation, profile/
logout, arbitrary catalog/practice requests, CLI, worker or scheduler. Pending
responses are equivalent before catalog commit and after catalog commit/before
ready update, and remain stable and non-enumerating.

## Evidence and review

Canonicalization/header allowlists and the production-composition manifest are
reviewed checked artifacts; expansions fail CI pending review. Composition is
reconciled against the final container image and deployment descriptors, not only
source discovery.

Evidence records database version, migrations/commit, exact role, pool settings,
commands, pass/fail/skip count and minimized concurrency seed. No test is allowed
to silently substitute an owner, superuser or alternate database. Issue #9 covers foundation and then-present schema evidence. Every later slice
registers and passes cumulative new table/relationship/action/HTTP cases before
merge. Flakes and skips block the applicable SEC-01 evidence set.

Independent security review must assess the explicit compromised-runtime trust
boundary, owner/runtime operational separation and whether function grants create
escalation paths. Privileged tenant-data migrations remain a future design gate.
Independent test-design review must determine whether a broken policy, stale
pool context, omitted child check or unregistered worker could still pass.
