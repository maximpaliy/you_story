# Independent test-design review — Issue #9

- Review date: 2026-10-22
- Reviewer: independent `test_review` agent (not the design author)
- Material: Issue #9 design and test design, accepted ADR-008 and Issue #5
  TD-01–TD-11, approved first-increment strategy
- Disposition: pass after the two design findings were resolved; implementation
  evidence and independent security/code review remain required
- Scope: safe executable/schema/context foundation subset only. Issue #9 and
  SEC-01 remain incomplete; this review cannot waive TD-11 or Issue #6.

## Findings

1. **Exact schema oracle was not yet available.** The draft promised a checked
   manifest but did not specify all columns, keys, constraints and grants.
   F-04/F-07/F-10 cannot distinguish the intended schema from an incomplete one
   without that oracle. Add the schema specification before migrations, reconcile
   every catalog object and relationship, and mutation-test omitted/ID-only keys,
   wrong nullability/owner and extra ACLs. **Resolved:** the concrete initial
   column/constraint proposal and technical migration ledger exception now give
   the schema oracle; test design requires column/FK/trigger/ACL reconciliation.
2. **Immutability promises need executable scope.** Add explicit existing-row
   tenant/owner reassignment negatives and source-definition/snapshot mutation
   checks for any immutable behavior claimed by the foundation. If a promise
   belongs to a later feature slice, state its deferral rather than imply current
   enforcement. **Resolved:** owner-local immutable ownership/definition-binding
   triggers, snapshot write denial and immutable-row trigger are specified; the
   test design now requires mutation attempts and detector mutations with
   positive mutable-metadata controls. Product history-meaning and lifecycle
   tests remain deferred rather than claimed.

## Assessment of the bounded test design

The named F-01–F-11 suites require real PostgreSQL, direct runtime reconnection,
positive own-tenant controls, independent predicate-free RLS probes, complete
then-present table inventory, physical backend reuse, failure/cancellation/reset
injection, migration replay/failure/retry and parser preflight. These are the
right layers. The semantic statement oracle is independent of RLS; its positive
baseline and wrong-alias/unanchored/removed-predicate mutations prevent a
substring check or always-failing detector from being accepted.

The empty production private-operation registry is acceptable only while actual
packaged composition, private SQL sites and repository registrations are
mechanically absent. A test-only probe does not satisfy later production-query
shape or use-case authorization coverage. F-03/F-09/F-10 must fail when such a
site appears without its complete reviewed registry and matrix.

Authentication control-plane and dormant-media ACL-denial tests must never be
reported as allowed-tenant CRUD evidence. No auth functions or production actor
issuer are present; TD-11 bootstrap/session/provisioning, SEC-05 and SEC-07
functional evidence remain explicitly outstanding. Health-only HTTP absence
checks do not establish product non-enumeration or browser-journey success.

Passing design review is permission to implement the reviewed subset only; it
is not evidence that implementation passed. Required tests must run without
silent skips or retries, and final independent security/code review must assess
implementation evidence and honest gaps.

## Re-review conclusion

The revised concrete schema proposal and test additions resolve the identified
false-pass gaps. The bounded design may proceed to implementation. In particular,
F-07/F-10 must execute the ownership/definition/snapshot mutations, F-04 must
check both empty and `000_security` upgrade paths with each actual revision's
failure/retry, and readiness must reject every unknown/missing/altered ledger
revision/checksum instead of accepting a merely reachable database.

This disposition does not approve implementation shortcuts or close Issue #9.
Final evidence must report the planned versus executed cases, zero required
skips, and all outstanding TD-11/session/provisioning and full-issue gates.
