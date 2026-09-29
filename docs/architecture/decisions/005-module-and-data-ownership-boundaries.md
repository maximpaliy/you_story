# ADR-005: Module and data ownership boundaries

- Status: Accepted
- Date: 2026-09-27
- Owners: Architecture / human owner

## Context

The human owner approved the modular-monolith direction on the condition that
function and database-object boundaries are defined. Catalog management,
session management and user management are expected candidates for possible
future services. An undifferentiated ORM or shared data-access layer would make
those boundaries nominal and later extraction disruptive.

## Decision

Define `identity`, `catalog`, `practice`, `media` and `reporting` as owned
modules. Each owns its use cases, domain model, repository interfaces,
PostgreSQL schema, tables and migrations. Other modules use typed application
interfaces and opaque IDs; they do not import owner persistence/domain packages
or query owner tables. Architecture tests enforce those rules.

Only `<module>.public` contracts may be imported across a boundary. Initial
ports are `ActorContextProvider`, `UserAccountCommands`, `UserProfileQueries`,
`CatalogCommands`, `CatalogQueries`, `CatalogEntryValidator`,
`PracticeSessionCommands`, `PracticeHistoryQueries`,
`PracticeRecordAuthorization`, `MediaCommands`, `MediaQueries` and
`ReportQueries`. Allowed domain edges are `practice -> catalog`,
`media -> practice`, and reporting to owner queries/events; cycles are forbidden.

Identity supplies validated actor/tenant context. Catalog owns content and
customization. Practice owns sessions, records, snapshots and recorded
statistics. Media owns upload/attachment metadata and objects. Reporting is a
read-only consumer and never a second writer of domain data.

Explicitly reviewed cross-schema foreign keys may preserve MVP integrity while
co-deployed, but they are documented extraction coupling and are not the sole
enforcement of business invariants. Public and cross-module references use
stable UUIDs. The referencing module owns the constraint; both owners and
architecture review approve a coupling-register entry and removal condition.
Private-resource constraints include tenant identity, grant no table access,
and never authorize direct ORM navigation or cross-schema queries.

## Alternatives considered

- Package boundaries with shared ORM access: easy initially but unenforceable
  ownership and expensive extraction.
- Separate databases or deployables immediately: strongest isolation but adds
  distributed consistency and operations before evidence justifies them.
- Only three modules (user/catalog/session): simpler naming but mixes media
  security/lifecycle and reporting projections into transactional owners.

## Consequences

The monolith gains enforceable ownership and clear candidates for later
extraction without paying distributed-system costs now. Some convenient joins
must be exposed through owner queries or deliberate read models. CI needs import,
migration-ownership and contract tests. Any actual service split remains a new
material decision requiring its own ADR and independent architecture/security
review.

## Security / privacy impact

Authorization remains in each owning use case, and tenant context is passed as
a validated technical primitive rather than accepted from request data. Tests
must prove that interfaces, projections and any reviewed cross-schema constraint
do not bypass tenant isolation or deletion rules.

## Human approval

Required. Decision: approved by the human owner on 2026-09-27.
