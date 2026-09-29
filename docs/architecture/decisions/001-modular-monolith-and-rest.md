# ADR-001: Python modular monolith with a versioned REST API

- Status: Accepted
- Date: 2026-09-26
- Owners: Architecture / human owner

## Context

The product begins small but must serve web, Android and Telegram clients. It
needs transactional catalog and practice operations without speculative
distributed infrastructure.

## Decision

Use a Python FastAPI modular monolith, PostgreSQL, and a versioned REST/JSON API
described by OpenAPI. Domain/application modules remain independent of HTTP and
GCP adapters. Web rendering and future client adapters call the same services.

## Alternatives considered

- Java/Spring: viable and approved, but more ceremony for this personal MVP.
- Microservices and messaging: operational cost without an established scaling
  or team boundary.
- GraphQL: flexible but unnecessary for the known navigation and increases the
  authorization/query-complexity surface.

## Consequences

Transactions, testing and deployment stay simple. Module discipline and API
compatibility checks are required to prevent accidental coupling. Services may
be extracted later based on evidence. Extraction uses a strangler approach:
first enforce module-owned data and explicit contracts in-process, then add
transactional outbox/idempotency semantics where asynchronous communication is
needed, move one bounded context and its data at a time, and preserve the public
API while routing internally to the new service. Separate services do not share
tables or distributed transactions; they require explicit consistency,
compensation, authorization, observability and operational ownership.

Candidate triggers are independently different scaling, availability, release
cadence or team-ownership needs. A module becoming large is not by itself a
trigger. Each extraction is a material architecture and trust-boundary change
requiring its own ADR and independent architecture/security review.

## Security / privacy impact

One enforcement point simplifies authorization, but compromise has a larger
blast radius; least-privilege runtime identity and module-level tests are
required.

## Human approval

Required. Decision: approved by the human owner on 2026-09-27, conditional on
defined function and database-object boundaries. ADR-005 and the corresponding
architecture section fulfill that condition and were approved by the human owner
on 2026-09-27. The condition is complete.
