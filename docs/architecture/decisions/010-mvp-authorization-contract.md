# ADR-010: MVP authorization contracts and historical statistic eligibility

- Status: Proposed — owner review required
- Date: 2026-10-21
- Related issue: #8 / MVP-05

## Context

The owner accepted personal-tenant use-case authorization, command/query scope,
draft/completed session editing, immutable historical associations and statistic
meaning, and late entry of values only for statistics applicable at record
creation. Earlier reviews required concrete input, action and consistency rules.

## Proposed decision

Use the [Issue #8 specification](../../work/issue-8/authorization-spec.md) as the
reviewable authorization contract. Owner-approved product decisions are recorded
separately in [the decision summary](../../work/issue-8/README.md); the detailed
specification also contains new proposed defaults, not blanket prior approval.

- Owning public use cases enforce actor-derived authorization independently of
  HTTP and independent of repository predicates/FORCE RLS.
- Parent aggregate gates serialize session completion with child mutations;
  transaction-scoped owner guards serialize authorization-dependent references
  with entry changes/tombstones and definition retirement. No cross-module ORM
  access is introduced.
- Capture the immutable published source-definition binding on record creation.
  Retained immutable definition membership proves eligibility for later omitted
  values without copying an entire definition set. Retired definitions prohibit
  additions; existing values retain original meaning.
- New entry roots use a configured published default; children inherit parent
  versions. Existing entries do not silently upgrade. Unsupported mixed-version
  moves are rejected rather than interpreted using current definitions.
- Global-reference categories require actual reviewed table-manifest entries;
  this proposal itself grants no RLS exemptions. User definitions and recorded
  data stay private.

## Alternatives

Route-only authorization fails for direct public-port callers. RLS-only control
cannot enforce same-tenant parent/lifecycle rules. Current-definition lookup can
reinterpret historical eligibility. Copying every available definition into each
record is unnecessary if immutable published membership is retained.

## Consequences and gates

Explicit contracts and bounded query collections improve reviewability and test
oracles. Aggregate versions can cause safe optimistic conflicts on concurrent
edits. Actual lock ordering, global-table manifests and database enforcement need
implementation evidence. Initial Yousician metadata schema, including level type
and bounds, remains missing; entry create/update are blocked until reviewed.
This ADR does not enable deferred features or close SEC-07.

## Reviews and human approval

See the independent [architecture](../../work/issue-8/architecture-review.md),
[security](../../work/issue-8/security-review.md) and
[test-design](../../work/issue-8/test-design-review.md) reports. Framework policy
and specified test oracles passed focused re-review after remediation; the source
schema block remains. Owner acceptance of these material clarifications and
proposed defaults is pending. No production implementation is authorized here.
