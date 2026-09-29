# ADR-003: Tenant-owned catalogs with dormant sharing primitives

- Status: Accepted
- Date: 2026-09-26
- Owners: Architecture / human owner

## Context

The MVP exposes personal catalogs only, but later sharing must not require a
database upgrade or backward-incompatible ownership change. Private user data
requires strong isolation from the beginning.

## Decision

Give every private aggregate a tenant ID. Store catalog owner, visibility and
catalog grants in the initial schema, while MVP service policy permits only
personal visibility and an owner grant. Enforce scoped repositories and
server-side object authorization, with PostgreSQL RLS as defense in depth.

## Alternatives considered

- Add sharing columns/tables later: simpler initially but violates the explicit
  compatibility requirement.
- Database/schema per user: strong isolation but high migration and operational
  cost.
- RLS alone: valuable defense but insufficient as the only policy layer.

## Consequences

Future sharing can be enabled by policy and API additions. Every query,
migration and background task must carry tenant context, and adversarial
cross-tenant tests are mandatory.

## Security / privacy impact

Tenant confusion is a critical risk. The runtime role must not bypass RLS;
service and database checks, audit evidence, and independent review are required.

## Human approval

Approved by the human owner on 2026-09-27. This approval accepts the initial
tenant/catalog/grant storage shape, dormant future-sharing primitives, scoped
authorization, and RLS defense-in-depth architecture. It does not waive the
open tenant-isolation security findings or authorize implementation before
their stated gates are satisfied.
