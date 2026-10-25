# Issue #10 — Allowlisted Google sign-in and session logout

Issue: https://github.com/maximpaliy/you_story/issues/10 (`MVP-07`).
Date: 2026-10-26. Status: **implemented and verified; ready for PR review/merge**.

## Result

Invited or subject-allowlisted users can sign in through Google Authorization
Code + PKCE, receive a linked internal user/personal tenant, use minimal
home/profile pages and log out. Profile JSON contains only `user_id` and
`provisioning_state`; tenant identity stays internal. Sessions are opaque,
digest-only in PostgreSQL, independently revocable and bound to validated actor
provenance. New account admission and session issuance commit atomically.

Catalog/grant provisioning runs only from a validated login callback, separately
from identity issuance. A provisioning failure preserves a usable pending
profile/logout; a later fresh login retries to one complete pair and ready state.
No content/catalog editing or practice feature is introduced.

The merged #9 / PR #25 database boundary and all 000–005 migration bytes remain
unchanged. This slice adds provider/crypto/public-port/browser integration,
login-only empty catalog provisioning, exact statement/actor/template/wheel
registries, production configuration and privacy-safe local launch guidance.

## Approval and reviews

The owner approved the concrete [HTTP contract](http-contract.md) on 2026-10-26,
including retained user_id and internal tenant_id. After real Chromium exposed
the original native-form policy conflict, the owner explicitly approved the
independently reviewed [ADR-012](../../architecture/decisions/012-native-login-browser-policy-compatibility.md).
Its form-page exceptions do not relax CSRF, canonical-origin validation or
caller-independent redirect selection.

- [As-built design](design.md), [approved contract artifact](openapi.candidate.json)
  and [active generated OpenAPI](../../api/openapi.json)
- [Reviewed test plan](test-design.md) and [final verification](verification.md)
- Independent [implementation code review](implementation-code-review.md),
  [composition/catalog/gate review](composition-code-review.md),
  [implementation security review](implementation-security-review.md) and
  [test-evidence review](test-evidence-review.md)
- [Browser compatibility evidence](browser-compatibility-evidence.md) with
  scoped [architecture](browser-policy-architecture-review.md),
  [security](browser-policy-security-review.md) and
  [test](browser-policy-test-review.md) reviews
- Initial [architecture](architecture-review.md), [security](security-review.md),
  [test-design](test-design-review.md) and [documentation](documentation-review.md)
  reviews remain historical design evidence, superseded by implementation reports

Review authorship is explicit: the provider author did not approve their own
provider code; the catalog/browser-test author excluded those files from their
code-review verdict. Separate reviewers covered those boundaries.

## Verification and limits

The full canonical command passed: **638 tests, zero failures or skips**, including
nine HTTPS Chromium journeys, PostgreSQL/RLS/migration/public-port tests,
188 browser-policy cases, signed synthetic provider cases and independent gate
mutations. Lint/format, strict types, architecture/SQL provenance, generated
OpenAPI, wheel build/artifact checks and an installed-wheel smoke passed.

Real Chromium follows the original start 303 to Google's fixed authorize URL;
CDP fulfills only the synthetic provider response. The backend validates real
RS256 signatures/JWKS through a controlled transport. Tests do not use live
Google credentials or claim a live Google/proxy/production deployment. Local
Chromium's explicit version override and CI's pinned browser setup are recorded
separately. One existing Starlette TestClient deprecation warning remains.

No production resources, real-user data, deployment, global security-finding
closure or deferred feature is authorized by this completion record. #10 remains
open until the PR is reviewed and merged.
