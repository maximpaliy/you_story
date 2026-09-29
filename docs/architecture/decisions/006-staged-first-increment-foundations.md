# ADR-006: Stage deferred capabilities behind migration-ready foundations

- Status: Accepted
- Date: 2026-09-29
- Owners: Architecture / human owner

## Context

Media support, account deletion and offline capabilities are not required in the
first usable increment. Deferring their behavior must not force a disruptive or
backward-incompatible database change when they are introduced later.

## Decision

The first increment does not expose media upload/download, account-deletion or
offline-write behavior. It does include the already identified stable storage
and contract foundations when omitting them would require a later migration:

- retain the separately owned `media` schema and its `upload_intent` and
  `attachment` metadata tables, but do not expose media commands or routes;
- retain stable identity, tenant, catalog-entry and practice-record UUIDs,
  immutable content snapshots and explicit account state needed to attach later
  lifecycle workflows without changing existing identifiers or history; and
- retain versioned REST contracts, idempotency/concurrency conventions and
  client-neutral application boundaries, but add no offline queue, sync state or
  conflict-resolution persistence until an offline use case is approved.

Initial migrations would create only these reviewed foundations. They would not
create speculative media-processing, anonymization, synchronization or
distributed-systems infrastructure. Enabling a deferred capability requires its
policy, security gates, tests and API to be approved at that time; ordinary additive
migrations remain acceptable when they do not reinterpret existing data or
break deployed clients.

“Unless their later addition would require database migrations” means that the
stable foundations needed to avoid disruptive ownership, identifier or existing-
data reinterpretation changes are created now. Ordinary additive migrations for
requirements that are not yet known are explicitly allowed. This avoids both a
backward-incompatible retrofit and speculative offline or lifecycle schema.

## Alternatives considered

- Implement all three capabilities now: adds security-sensitive behavior that
  does not contribute to the first increment.
- Omit every trace until later: minimizes initial DDL but would require known
  module, identifier and relationship foundations to be retrofitted.
- Prebuild complete future schemas: avoids some migrations but creates
  speculative fields and invariants before their requirements are known.

## Consequences

Core catalog, session and history work can proceed without media, deletion or
offline feature tests. Initial migration tests still verify the reserved module
ownership, keys and relationships. Later feature work may use additive database
migrations, but must not require a backward-incompatible ownership or identifier
change.

## Security / privacy impact

No deferred endpoint, worker or user-visible promise exists in the first
increment. The runtime database role has no privilege on the dormant `media`
schema, and no media repository or command adapter is registered. Architecture
and integration tests verify database denial and route/adapter absence. This
decision does not close SEC-02, SEC-03, SEC-08 or any other finding; each becomes
a blocker at its documented feature or deployment gate.

## Human approval

Approved by the human owner on 2026-09-29. Ordinary additive migrations are
allowed; the initial foundations prevent disruptive ownership, identifier and
existing-data changes rather than attempting to prebuild every future field.
