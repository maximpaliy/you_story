# Independent security review — proposed native-form browser adjustment

- Reviewer: independent security-review agent; did not author the proposed
  ADR or browser delivery implementation
- Date: 2026-10-26
- Material: proposed ADR-012, accepted ADR-009/011, current form templates and
  delivery response/provenance controls, approved Issue #10 HTTP contract
- Verdict: **approved policy implementation and native-browser evidence pass**.
  Owner explicitly approved the scoped
  ADR-012 adjustment on 2026-10-26 before activation. The initial proposal-only
  restrictions below are historical prerequisites, now satisfied for owner
  approval and inspected policy code. No production or risk acceptance.
- Current frozen final evidence: **638 passed, zero errors/failures/skips, nine
  real HTTPS browser cases**. The 580/582-case results below are historical and
  superseded by the frozen final evidence addendum.

## Assessment

The proposed adjustment preserves strict provenance rather than admitting opaque
Origin values. Restricting Referrer-Policy: same-origin to successful HTML GETs
on /login, / and /profile allows native same-origin form provenance without
sending a referrer to Google or another origin. These pages reject query/body
input, contain no callback query or credential-bearing URL, and render proof/CSRF
only as escaped hidden form fields. Fragments are not transmitted in HTTP
referrers. Callback responses retain no-referrer, no-store and generic failures.

The additional form-action source is limited to successful login-form HTML and
the fixed Google HTTPS authorize URL. Other pages, especially logout, retain
self-only form-action. It introduces no script, remote resource, credentialed
CORS, generic provider selector or unvalidated return destination. Application
code still constructs the exact fixed Location after signed binder, proof,
canonical provenance, body/schema and rate checks.

This is nevertheless a real change to an independently approved browser defense.
The source document's form-action now permits applicable navigation to the
accounts.google.com origin, and redirect-hop CSP path matching cannot establish
an exact endpoint boundary by itself. ADR-012 states this limitation correctly.
The server's fixed authorize URL supplies the initial path boundary; escaped
templates, proof/binder validation and exact route inventory remain independent
controls. Do not describe the new CSP permission as harmless to a hypothetical
HTML injection or as restricting every redirect hop to the authorize path.

## Mandatory activation and evidence conditions

1. Obtain the owner's explicit ADR-012 decision before changing production
   response policy. Previous HTTP-contract approval does not waive this gate.
   Diagnostic header changes may remain fixture-only and cannot be reported as
   passing production behavior.
2. Bind each policy exception to **exact method, registered path, success status
   and HTML content class**. A POST result, redirect, JSON body, callback or
   framework/error response must not inherit it merely because its path matches.
   Only login-form HTML gets the Google form-action addition; authenticated
   home/profile get same-origin referrer policy without the Google source.
3. Preserve the full remaining ADR-009 CSP/header matrix, fresh independent
   nonce, no-store, escaping and hidden-field token rules. No null-Origin bypass,
   permissive forwarding-origin inference or external resource source is allowed.
4. Record actual native HTTPS Chromium behavior with the existing unmodified
   failure first, then isolate the referrer and redirect-CSP causes in synthetic
   diagnostic composition. Do not synthesize request Origin, disable CSP, or
   replace native form submission with a client API request to obtain a pass.
5. After approval, execute the exact activated policy with real runtime-role
   PostgreSQL, signed synthetic provider responses and the production delivery
   stack. Prove login/profile/logout, strict null/cross-origin and wrong-CSRF
   denials, self-only logout, blocked attacker form navigation, and unchanged
   callback/error/redirect/JSON defaults. Include exact header-policy tests.
6. Evidence retains only bounded status/origin classification/CSP directive and
   engine version. Do not retain blockedURI, callback URL/query, proof, binder,
   invitation, tokens or credential-bearing browser traces/screenshots. Existing
   server access-log suppression and independent secret-canary checks still apply.

No additional blocking security design finding was identified in this narrow
proposal. It does not establish browser compatibility before the diagnostic and
final native-form runs, approve a policy implementation not yet inspected,
complete issue #10 or authorize real users/deployment. The separate implementation
review still tracks actor/session integrity, logging and full runtime evidence.

## Owner decision and activated policy re-review

The owner explicitly approved the exact scoped ADR-012 adjustment on 2026-10-26.
This reviewer then inspected the activated `apply_response_policy` and the root
middleware's method/path wiring independently of their authors.

The exception predicate requires HTML, status exactly 200, method exactly GET,
and path exactly /login, / or /profile. Only that login-form class appends the
literal Google HTTPS authorize source. Home/profile remain self-only form-action;
callback, errors, redirects, JSON, other methods/paths and missing request
classification retain no-referrer and strict self-only form-action. Nonce,
no-store, all other fourteen CSP directives and the remaining header matrix
remain as approved. No null-Origin/provenance bypass or request-selected source
was introduced. The app supplies method/path from the actual Request, not an
untrusted header or client field.

Independent focused run of `tests/test_browser_policy.py` and
`tests/test_auth_logging.py`: **190 passed, one upstream Starlette/httpx warning,
1.10 seconds**. The 120-case method/path/status/representation matrix independently
checks all directives, exceptions and unchanged defaults; missing-classification
and safe-log canary controls also passed.

**Exact policy source/focused evidence verdict: pass.** The final real native
HTTPS browser outcome and full integration evidence remain a separate completion
condition. This source/header pass does not claim those pending runs executed,
authorize production or close issue #10/security findings on its own.

## Final native-browser evidence disposition

The coordinator's final canonical run completed **580 passed, zero failures or
skips**, including the seven actual HTTPS Chromium journeys. This reviewer
independently inspected the JUnit summary and browser-test assertions, without
concurrently rerunning the destructive shared PostgreSQL fixture.

The positive flow keeps native POST/303, actual enforced response policy and
strict provenance. CDP intercepts only the fixed external Google request after
CSP checks to supply the synthetic provider response; no test rewrites the
initial redirect, forges Origin or disables CSP. The resulting signed-token,
cookie/profile/logout and independent-account journeys passed. Real browser
negatives observed form-action blocking for attacker targets, an unapproved
Google path, and Google submission from non-login profile; the response-policy
matrix also confirms all callback/error/redirect/JSON defaults remain unchanged.

**Final scoped policy security verdict: pass.** The original incompatible policy
is retained as a failing historical diagnostic, not an ignored failure in the
final run. Owner approval, exact source review, header matrix and native-browser
evidence now resolve this compatibility gate. No live Google deployment,
production proxy configuration, real-user-data permission or risk acceptance is
implied. See [implementation security review](implementation-security-review.md)
for the separate identity/catalog/logging findings and final scoped disposition.

## Final evidence addendum — nine browser cases

The coordinator's final full rerun is **582 passed, zero errors/failures/skips,
75.370 seconds**, including nine actual native HTTPS browser cases. This reviewer
parsed the updated JUnit and inspected the additional real-app pending-catalog
fault/retry journeys and strengthened stored-canary assertions. All original
native form/CSP/provenance positives and negatives remain in that passing run;
the new cases also exercise pending-profile and native logout before successful
fresh-login reconciliation. No policy or other production source changed for
this test/evidence refinement.

This is the current acceptance result; the earlier 580-case/seven-browser record
is retained only as a historical checkpoint. The scoped policy security pass
remains unchanged, with the same independent-review and production limitations.

## Frozen final evidence addendum

The current canonical JUnit and successful check/package log were independently
inspected: **638 passed, zero errors/failures/skips, 76.196 seconds**, retaining
all nine real HTTPS browser cases. The 56 added issuer-capability static mutations
do not change the approved policy or browser feature behavior. This supersedes
the 580/582-case historical aggregate checkpoints. The exact policy/source and
native-browser security pass, scope and production limitations remain unchanged.
