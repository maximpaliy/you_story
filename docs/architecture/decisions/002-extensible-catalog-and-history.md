# ADR-002: Validated content trees with immutable practice snapshots

- Status: Accepted
- Date: 2026-09-26
- Owners: Architecture / human owner

## Context

Yousician uses song/version/fragment while Songsterr and future sources may not.
Historical records must remain intelligible after catalog changes.

## Decision

Represent catalogs as typed parent/child nodes qualified by source and
instrument. Versioned source definitions and policy code validate hierarchy and
metadata. Practice records retain an optional live reference plus an immutable
content snapshot and versioned typed statistic values.

“Typed” means each node stores an `entry_type` discriminator column declared by
the versioned definition for its source; it does not mean each personal catalog
invents its own type system. The definition specifies the allowed type vocabulary,
parent/child combinations, required metadata and practiceable types, optionally
constrained by instrument. Thus Yousician can define
`song -> version -> fragment` while Songsterr defines a different valid graph.
Entries retain the definition version against which they were validated.

## Alternatives considered

- Dedicated table per source: strongly typed but creates source-specific APIs
  and migrations for every source.
- One fixed song/version/fragment schema: cannot faithfully represent other
  structures.
- Unrestricted JSON documents: flexible but weakens integrity and querying.
- Event sourcing: preserves history but is disproportionate for the MVP.

## Consequences

New sources usually add policy/configuration and contract tests rather than
schema changes. Validation and snapshot duplication add complexity. Semantics
that do not fit a tree require a new reviewed ADR, not arbitrary JSON.

## Security / privacy impact

Snapshots can retain personal text after deletion; allowed snapshot fields and
the anonymization/erasure process need security review and a final privacy rule.

## Human approval

Approved by the human owner on 2026-09-27. This approval accepts the validated
content-tree, source-definition and immutable practice-snapshot decision. It
does not settle the final anonymization, deletion, retention or export policy,
which remains a separate approval gate.
