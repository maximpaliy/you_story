# Independent test-design review — GitHub Issue #4

- **Reviewer:** Independent test-strategy review agent
- **Review date:** 2026-09-30
- **Material reviewed:** `docs/testing/strategy.md` against the approved product
  definition, architecture, security review and Issue #4 acceptance criteria
- **Initial verdict:** Revise before human approval
- **Re-review verdict:** Pass
- **Final disposition:** TDR-01 through TDR-06 are resolved; the human owner
  approved the strategy on 2026-09-30

## Findings and dispositions

### TDR-01 — Acceptance-level traceability was too broad (blocking)

The initial feature/security matrix did not explicitly map every in-scope
product requirement or architecture invariant to an owner and named evidence.

**Disposition:** Resolved. Sections 6.1 and 6.2 now assign stable local IDs and
map every product-definition area and first-increment architecture invariant to
scope/deferred status, GitHub issue/backlog owner and named verification. The
existing security matrix now includes both GitHub issue and MVP identifiers.

### TDR-02 — Background jobs were missing from SEC-01 cases (material)

**Disposition:** Resolved. PostgreSQL isolation cases now require worker/job
tenant-context construction and a fail-closed oracle, or explicit composition
evidence that no worker exists plus a gate when one is introduced.

### TDR-03 — Destructive-action reauthentication was incomplete (material)

**Disposition:** Resolved. The identity suite now makes Issue #6 (`MVP-03`)
classify all first-increment destructive actions and verify required
reauthentication. Account deletion and mobile token/redirect tests are explicitly
deferred and gated.

### TDR-04 — Telemetry absence assertions lacked a positive control (material)

**Disposition:** Resolved. Each enabled sink must first observe a benign unique
sentinel. Bounded polling/flush, inspected interval, revision and lag are
recorded; missing sentinel or sink makes the test fail as inconclusive.

### TDR-05 — Dormant-media checks could pass on names alone (material)

**Disposition:** Resolved. Architecture evidence now combines runtime
composition inspection, a reviewed route/OpenAPI allowlist, negative HTTP/API
assertions and PostgreSQL runtime-privilege inspection, including generic file
or upload behavior.

### TDR-06 — Cross-tenant non-enumeration oracle was underspecified (material)

**Disposition:** Resolved. Foreign-existing and same-shaped nonexistent
resources must be equivalent across stable status/error schema, allowed headers
and redirects, count/cursor behavior, response-size class and bounded timing
where relevant, through HTTP/browser and public-port/repository paths.

## Advisory improvements incorporated

- Supported migration origins now use a checked manifest whose missing fixtures
  fail CI.
- GitHub issue mappings also retain stable MVP identifiers.
- The exhaustive matrix assigns accessibility, HTTPS/configuration, secrets and
  correlation-ID requirements to explicit evidence.
- Real-provider coverage is bounded to a separately controlled non-production
  smoke; configuration assertions remain required without live credentials.

The browser/assistive-technology support matrix remains an owning-issue decision
and is explicitly listed among open strategy decisions. This is not a blocker
to strategy approval because the strategy requires the matrix and records exact
versions before the applicable manual review.

## Review conclusion

The revised strategy satisfies the independent review's pass conditions. It
retains real PostgreSQL/RLS fidelity, adversarial multi-tenant checks, two named
end-to-end history journeys, evidence hygiene and correct deferred-feature
boundaries. No security finding is closed by this review. The human owner
approved the strategy on 2026-09-30, completing the Issue #4 acceptance gate.
