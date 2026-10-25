# Independent test-design review — proposed ADR-012

- Reviewer: independent test-review agent, not the browser test author
- Date: 2026-10-26
- Material: proposed ADR-012, ADR-009/011, Issue #10 browser-policy tests,
  real-browser journey harness and test-only compatibility diagnostic
- Verdict: **proposed test-design scope passes with the exact matrix below**;
  browser implementation/evidence acceptance remains blocked
- Owner approval: pending; production policy must remain unchanged
- Execution by this reviewer: source/design inspection only; no browser or
  PostgreSQL suite executed

## Scope and observed evidence limits

The reviewed [ADR-012](../../architecture/decisions/012-native-login-browser-policy-compatibility.md)
changes two explicit browser-policy choices. It does not authorize null Origin,
change CSRF/proof parsing, add an authentication provider or relax server-selected
redirects. Owner approval and independent architecture/security review remain
necessary before activation.

The strict native-browser baseline reports login start 403 with opaque Origin,
no Referer and zero provider exchanges. The response-only diagnostic changing
Referrer-Policy to same-origin reports native start 303 followed by a form-action
violation and zero provider exchanges. These isolate different layers. Neither
is a passing production login journey or permission to alter browser request
headers. Retain their sanitized status/directive/engine observations and original
failure disposition; do not retain raw request URLs or credential-bearing DOM.

The scratch diagnostic is appropriate for cause isolation, but its response
substitutions are not the final exact route/method/status/header implementation
and cannot stand in for production-middleware tests. The proposed-policy
journey also encounters provider-navigation interception limitations in the
browser harness. That is unresolved evidence, not proof the proposed policy
has completed the external redirect.

## Exact regression matrix required after approval

Parse effective CSP directives and header multiplicity rather than checking
substrings. All rows retain the other ADR-009 directives, fresh nonce, no-store
and applicable security headers unchanged.

| Response boundary | Referrer-Policy | form-action / oracle |
| --- | --- | --- |
| Exact GET `/login`, status 200, HTML containing the approved login form | same-origin | Exactly self plus the fixed HTTPS Google authorize source from ADR-012 |
| Exact GET `/` or `/profile`, status 200, HTML containing logout form | same-origin | Exactly self; no Google or other external form source |
| Those paths with errors, non-200 status, redirects or non-HTML content | no-referrer | HTML retains self-only; non-HTML/redirect receives no invented CSP exemption |
| Callback HTML, including all 400/409/429/500/503 failures | no-referrer | Exactly self; no Google source |
| API JSON, health JSON, unknown-path errors and framework/middleware failures | no-referrer | Original response-class CSP applicability; no form-page exemption |
| Login/start/callback/logout redirects, including authenticated login redirect | no-referrer | Original redirect policy; no exception inherited from preceding page |
| HEAD/POST/OPTIONS or other methods at form-page paths; trailing-slash redirects and prefix/suffix lookalikes | no-referrer | Unsupported methods do not dispatch commands; no path-only/prefix exemption |

The matrix must exercise actual outer production middleware, including early
origin/body/media-type failures, unavailable service and unexpected exceptions.
Mutation cases independently broaden an exception to path-only, all HTML or all
statuses; each must fail the corresponding negative matrix row. A mutation adding
Google to home/profile/callback CSP must fail even when login still succeeds.

## Required native browser and security cases

1. Over real HTTPS with the pinned engine and real runtime PostgreSQL, submit
   the actual login form without injected Origin/Referer or CSP bypass. Assert
   same-origin native provenance, real start 303 to the exact fixed Google HTTPS
   Location, successful signed synthetic provider callback, authenticated own
   profile, and native logout/revocation. Repeat from both home and profile
   logout forms and independent browser accounts. Inspect actual effective
   response headers, not fixture assumptions.
2. Separately prove the browser allows the original fixed Google navigation under
   the proposed login CSP. A signed-provider transport substitution may replace
   provider service behavior, but may not erase the navigation being tested.
   Observe only safe destination classification/request count and eventual local
   callback outcome. Preserve a no-Google-source mutation that blocks that
   navigation with effectiveDirective=form-action and no code exchange.
3. Prove off-provider form navigation remains blocked on login and all form
   navigation to Google remains blocked on home/profile. Do not mistake the
   explicit Google exception on login for an assertion that every external form
   is forbidden there. The application's actual form action stays same-origin.
4. Native cross-origin and opaque/null-Origin submissions remain rejected before
   downstream commands; missing/foreign/expired proof or CSRF also fails.
   Origin present but null never falls back to Referer. Valid token alone cannot
   bypass provenance, Fetch Metadata, representation or streamed-body limits.
5. Observe same-origin referrer behavior from the three exact form documents and
   absence of referrer on cross-origin navigation. Callback/error documents retain
   no-referrer. Reject form-page query/body inputs so credentials cannot enter a
   same-origin-referrable form-document URL. No raw Referer or callback query is
   retained in artifacts.
6. Retain existing nonce, inline script/event/style, base/frame/object and
   reflected/stored-canary exclusion cases. Both intended form submissions and
   forbidden navigation need positive observed request/scanner controls. Unseen
   network events or a disconnected CSP listener cannot prove blocking.

CSP source path matching can be ignored on redirect hops. Tests must not claim
that the CSP string enforces Google's authorize path on every hop. Assert the
server-generated initial Google Location exactly, and separately verify the
browser's actual form-action behavior for approved/off-provider navigation.

## Harness finding and final acceptance rule

Rewriting the POST-start 303 Google Location into a local callback can test the
remaining native form/session/provider path in a clearly labelled diagnostic.
It bypasses the external navigation and cannot satisfy case 2 above. Likewise,
absence of a recorded CSP violation alone is not successful provider navigation.
Fix interception or use another controlled browser/provider boundary that
preserves the original redirect, and prove its observation with a positive
request control before reporting the native journey passed.

Read only effectiveDirective and bounded status/origin categories from browser
violations. Do not collect blockedURI, callback URL, code, state, binder, proof,
CSRF or screenshots/traces containing hidden tokens. Keep all diagnostic header
substitutions outside production code, the wheel and final acceptance tests.

The proposed test scope is adequate to review the policy decision, with these
required cases made explicit. It grants no implementation activation or security
risk acceptance. Final acceptance requires the corrected production matrix,
unmodified native browser journeys, full canonical checks and independent
implementation/security evidence review after owner approval; current strict
browser failures remain visible until then.
