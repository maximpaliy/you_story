# Independent supplementary code review — composition, catalog and gates

- Date: 2026-10-25
- Reviewer: supplementary final-review agent, independent of the reviewed
  composition/catalog/logging implementation
- Reviewed source: `app.py`, `catalog/public/__init__.py`,
  `catalog/infrastructure/provisioning.py`; referenced actor validation and
  shared transaction controls for call-boundary verification
- Verdict: **scoped code-review pass**; this is not an independent review of
  this reviewer's browser delivery implementation or of the whole auth slice

## Findings and assessment

No blocking defect identified in the reviewed source. Composition invokes the
catalog public port only after successful identity completion and only for a
pending account. Catalog pair writes use a separate tenant transaction; failure
is caught without undoing the committed identity/session or exposing exception
details. The ready transition follows typed catalog success and goes through
the identity service, which remains responsible for validated actor/session
matching and active session linkage. Ordinary profile and health paths do not
invoke provisioning. Successful ready marking need not mutate the immutable
callback session evidence; a subsequent resolver reads the authoritative state.

Catalog rejects forged or modified actor evidence before database dispatch.
Every private read has explicit actor-derived tenant equality. Insert bindings
derive tenant and grantee from the same actor; catalog and grant IDs are generated
by trusted code. The unique tenant catalog insertion, locked tenant read and
unique catalog grant insertion make concurrent callers converge. Owner-grant
verification and the shared unit of work preserve pair atomicity and independent
FORCE RLS. No foreign control-table access, catalog metadata editing or content
seed behavior is introduced.

The outer HTTP middleware generates correlation IDs, catches unexpected errors
without exception detail and applies the response-policy function to normal and
early/framework errors. Exact callback GET exceptions use generic HTML; method
errors do not dispatch callback logic. Access-log filters suppress the default
Uvicorn and HTTPX URL-bearing records; safe application events remain observable
without raw SQL, provider payload or credentials. These filters are application
controls, not proof of deployed proxy or tracing configuration.

OpenAPI augmentation adds the cookie scheme to metadata generated from actual
registered routes. It does not replace route discovery with a separate proposed
contract or expose the interactive schema/docs endpoints.

## Verification and limits

Executed the non-PostgreSQL subset of `tests/test_http.py`,
`tests/test_auth_logging.py` and `tests/test_catalog_provisioning.py`: **8 passed,
3 PostgreSQL cases deliberately deselected**. This targeted selection is not
the cumulative acceptance run. The logging check observes a positive safe event
and proves callback access-record/provider canaries are absent from captured
logs and responses. Catalog unit checks reject forged actor evidence before DB
dispatch and independently inspect SQL tenant bindings/predicate removal.

Did not rerun the destructive PostgreSQL suites or the real browser journey
while the lead owns those fixtures. Their catalog concurrency/fault/RLS and
whole-slice evidence must be included in final verification. This report does
not independently approve this reviewer's own browser source, provider/OIDC
cryptography, all identity-service semantics, deployed telemetry sinks or
production use. This reviewer subsequently authored the owner-approved ADR-012
delivery adjustment; that code is outside this independent review's scope and
requires the separate security/code review. Independent implementation reviews
and cumulative browser/runtime checks remain gates.

## Final gate and CI scope extension — pass after remediation

Independently reviewed the gate implementation authored by the separate
test-review agent: `tools/check_architecture.py`, `tools/check_artifact.py`,
`tools/export_openapi.py`, composition/technical-SQL manifests, the Makefile and
the GitHub Actions check workflow. This extension still excludes this reviewer's
own browser delivery/policy source and does not replace the whole-slice security
or runtime evidence review.

### IR-G01 — Issuance capability escaping the exact trusted chain — resolved

The initial gate rejected direct ActorContext and AuthenticatedSession creation
but permitted an already registered identity provider adapter to import and call
`actors.issue_session` with an arbitrary tuple. Reproduced the mutation against
`identity/infrastructure/google.py`: source checking returned no error. This was
a static-boundary defect, not misuse found in the actual provider source.

The author added an exact capability check: importing issue_session is limited
to wiring, and references are allowed only as the direct call in wiring._issuer.
Actor issuance references are limited to the internal direct call in
actors.issue_session. Aliased imports, module-qualified access, extracted
callbacks, wiring._issuer escape and wildcard imports are rejected. Legitimate
service use of its injected self._issuer remains allowed. Independently
reproduced direct, aliased, extracted and wildcard mutations after remediation;
all are rejected. Positive controls and actual source checking pass. IR-G01 is
resolved; no remaining gate blocker identified.

### SQL, package, route and process checks

The SQL registry has exactly the two inherited technical files plus the private
identity adapter and catalog provisioning file. It tracks SQL calls, extracted
execution references and their containing function bodies. Crucially, `_rows`
callers are hashed too: changing a wrapper target or its binds cannot hide behind
the one generic execution helper. Catalog predicate and actor-bind mutations
are tested independently of RLS. Registry file/site additions fail closed rather
than receiving a whole-file SQL exemption.

Source inventories explicitly name the approved behavior files. The composition
manifest lists only four catalog statement shapes, HTTP and schema migration;
workers and media adapters remain absent. Source and wheel checks reconcile
package bytes, classify payloads and entry points, and scan the exact three
templates for unsafe sinks/resources. Source module-edge and execution-root
checks remain active. Template package data is included in the wheel comparison.

OpenAPI generation first verifies the actual runtime route/method inventory,
including routes hidden from schema, then verifies schema parity. It does not
substitute a hand-authored candidate for the running application's route list.
The current implementation's composition contains no conditional hidden route
or additional process registration.

### Delivery workflow and independent checks

The workflow retains immutable checkout/Python action references and read-only
repository permission. It syncs the frozen lockfile, installs Chromium through
the pinned Playwright package, then runs the complete canonical check. The
unfiltered pytest command includes the marked HTTPS/browser/PostgreSQL tests;
the separate browser target does not remove them from canonical checks. The
browser fixture requires an installed engine and does not skip on absence.
Deployment-descriptor hashes include the Makefile and updated workflow, with
mutations rejecting an unregistered command or descriptor.

Executed architecture source/composition and generated-OpenAPI checks, plus
architecture/artifact/OpenAPI mutation suites: **112 passed**, zero failures or
skips. Ruff and whitespace checks pass. This is focused gate evidence only;
the lead's final canonical, installed-wheel and real-browser evidence remains
separate. No acceptance decision is based on test count alone, and this review
does not approve deployment or close unrelated operational/security findings.
