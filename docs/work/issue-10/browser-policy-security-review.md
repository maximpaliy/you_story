# Independent security review — proposed native-form browser adjustment

- Reviewer: independent security-review agent; did not author the proposed
  ADR or browser delivery implementation
- Date: 2026-10-26
- Material: proposed ADR-012, accepted ADR-009/011, current form templates and
  delivery response/provenance controls, approved Issue #10 HTTP contract
- Verdict: **proposal design pass; inactive pending owner approval and exact
  browser/implementation evidence**. No production or security-risk acceptance.

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
