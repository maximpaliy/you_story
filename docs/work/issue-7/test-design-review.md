# Independent test-design review — GitHub Issue #7

- **Reviewer:** Independent test-design review agent
- **Review date:** 2026-10-06
- **Material reviewed:** `docs/work/issue-7/test-design.md` against ADR-009,
  SEC-06 and the approved first-increment test strategy
- **Initial verdict:** Revise before approval
- **Re-review verdict:** Pass
- **Final disposition:** TDR7-01 through TDR7-06 are resolved; SEC-06 is ready
  for implementation evidence, but remains open until that evidence and the
  required independent implementation/security review exist

## Assessment

The initial design was strong in its use of production middleware and a real
browser, adversarial parser cases, route/template/sink inventories, state
postconditions, and positive controls for both forbidden-sink checks and
telemetry scanners. It also correctly preserved the strategy's distinction
between test evidence and proof that XSS or CSRF is absent. The initial review
found the following ambiguities; the dispositions record their resolution in
the revised design.

## Findings and required dispositions

### TDR7-01 — The top-level mutation oracle is over-permissive (blocking)

The statement that a mutation is allowed when session, provenance, media type
and token all pass reads as a sufficient authorization rule. Those browser
controls are necessary but not sufficient: authorization, tenant isolation,
validation, concurrency and domain rules can still deny a request. Rewrite the
oracle as a one-way condition: failure of any browser precondition must prevent
the domain mutation, while passing all browser preconditions merely permits the
request to proceed to the remaining application controls. Name the observable
boundary at which the browser middleware rejects and require unchanged durable
state and absence of downstream command/repository calls for each rejection.

**Disposition:** Resolved. The revised oracle makes the four browser controls
necessary rather than sufficient, locates rejection at the outer
browser-policy/application-dispatch boundary, and requires both no downstream
command/repository call and no durable state change.

### TDR7-02 — CSP nonce negative cases use an impossible browser oracle (blocking)

A browser does not independently reject a server-generated nonce because it was
reused, and an attacker-supplied nonce is not a request input that the CSP layer
can generally reject. Separate three testable properties:

1. configuration/source inspection establishes the approved cryptographic RNG
   and minimum entropy/encoding contract;
2. response tests prove a newly generated nonce is propagated consistently only
   to the CSP header and approved script elements and is not repeated across a
   bounded deterministic sample (a collision test is regression evidence, not
   proof of unpredictability); and
3. browser probes prove scripts with no nonce, a mismatched nonce, or an
   attacker-controlled guessed nonce do not execute, while the response's
   matching approved script does.

The revised design must not claim that a statistical uniqueness test proves
unpredictability or that the browser detects nonce reuse.

**Disposition:** Resolved. WEB-04 now separates source/configuration inspection,
response propagation and bounded uniqueness regression evidence from browser
execution probes, and explicitly disclaims both statistical proof of
unpredictability and browser detection of nonce reuse. ADR-009 supplies the
concrete 32-byte OS-CSPRNG and unpadded-base64url contract.

### TDR7-03 — Expected provenance canonicalization is underspecified (material)

WEB-02 lists case, encoding, default-port and other confusion variants without
stating which are equivalent to the configured origin and which must fail.
Define the comparison oracle using parsed origins (scheme, canonical host and
effective port), reject credentials, opaque/multiple/malformed values, and state
the expected result for default ports, host casing, trailing dots, IDNs and
percent-encoded forms. Do the same for the `Referer` origin extraction. Without
these expectations, implementations with opposite behavior can both satisfy
the current prose.

**Disposition:** Resolved. ADR-009 defines the configured origin and parsed
tuple, trusted source, case/default-port normalization and rejected forms;
WEB-02 applies those outcomes to both `Origin` and `Referer`, including the
configured non-default-port and trusted-configuration cases.

### TDR7-04 — Traceability is implicit rather than mechanically reviewable (material)

The five WEB groups broadly cover ADR-009 and SEC-06, but there is no explicit
requirement-to-case map. Add a compact matrix mapping every ADR-009 decision and
SEC-06 remediation item to a test ID, level (static/HTTP/browser/configuration),
positive control or mutation where applicable, and owning implementation issue.
The matrix must explicitly identify deferred COEP, HSTS subdomain/preload,
rich-text, upload and cross-origin credential behavior so an inventory change
cannot silently turn a deferral into an untested feature.

**Disposition:** Resolved. The traceability table maps the browser-control,
encoding, CSP/header, inventory/leakage and complete SEC-06 requirements to
levels, mutations or positive controls, and implementation owners. It also
turns each named deferred capability into an explicit absence/inventory test
whose introduction must reopen design.

### TDR7-05 — The cross-product and browser execution plan needs a bounded,
reproducible definition (material)

“Cross-product” across every route and listed header dimension can grow without
a stable stopping rule, while “a supported real browser” does not identify the
support target. Define a generated canonical matrix for every unsafe method and
transport, use named boundary/equivalence classes (or pairwise generation for
non-interacting dimensions), and reserve full combinations for interactions
such as token × origin fallback × Fetch Metadata × media type. Record the
browser engine/version, test runner, PostgreSQL version, seed/corpus version,
and retry policy in retained evidence. Browser-security failures must not be
silently retried to green.

**Disposition:** Resolved. The execution profile pins the evidence dimensions,
requires canonical boundary/equivalence cases per unsafe method and transport,
uses a full product for the interacting security dimensions, confines pairwise
generation to documented non-interactions, and prohibits silent security-test
retries.

### TDR7-06 — Leakage scanning needs explicit safe collection and failure
handling (material)

The design correctly requires positive controls for every sink, but it should
adopt the strategy's bounded flush/polling oracle and evidence metadata. Specify
the inspected interval, application revision, sink/query, ingestion lag and
timeout; a missing benign sentinel or uninspected enabled sink must fail as
inconclusive rather than pass as clean. Positive controls must use synthetic
canaries—not actual session or CSRF secrets—and raw artifacts must be scanned or
redacted before retention, including artifacts produced by failed tests.

**Disposition:** Resolved. WEB-05 now records the revision, interval, query,
ingestion allowance and timeout; treats missing sentinels, sinks, timeouts and
collection failures as failing/inconclusive; limits controls to synthetic
canaries; and scans or redacts success and failure artifacts before retention.

## Re-review conclusion

The revised design satisfies all pass conditions without weakening ADR-009. It
has a necessary-only dispatch oracle, technically valid nonce evidence,
explicit origin normalization, complete ADR/SEC-06 traceability, bounded and
reproducible execution, mutation controls, and fail-closed leakage collection.
The cases are feasible at the specified static, HTTP, browser and sink-polling
levels, while the route/template/sink inventories prevent later web slices from
silently escaping coverage.

This passes the pre-implementation test-design gate only. No production
implementation is approved, passing future tests will not prove the absence of
XSS or CSRF, SEC-06 is not closed, and no residual security risk is accepted.
