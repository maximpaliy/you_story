# ADR-012: Native form compatibility for the approved Google login flow

- Status: Accepted by the human owner on 2026-10-26 after independent reviews
- Date: 2026-10-26
- Scope: narrowly amend ADR-009 for HTML containing the approved native forms

## Observed conflict

Real Chromium HTTPS testing of the approved implementation returns 403 before
Google: native POST from a document with Referrer-Policy: no-referrer sends
Origin: null and no Referer. ADR-009 correctly rejects that opaque provenance.
Tests must not fake a same-origin Origin or disable the provenance check to
claim the journey passed.

The same browser may also enforce the source document's form-action across
the approved POST-start 303 redirect to Google. A same-origin form-action alone
cannot authorize that approved external navigation. The sanitized browser
evidence records each layer separately, without storing callback URLs or tokens.

## Proposed exact adjustment

1. Successful GET /login, GET / and GET /profile HTML that contains the approved
   proof/CSRF-protected forms uses Referrer-Policy: same-origin. This permits
   same-origin native POST provenance while suppressing cross-origin referrers.
2. Only successful GET /login HTML adds
   https://accounts.google.com/o/oauth2/v2/auth to its form-action directive.
   Its value becomes `form-action 'self' https://accounts.google.com/o/oauth2/v2/auth`.
   All other CSP directives and every other page's form-action remain unchanged.
3. Callback HTML, errors, redirects, JSON, and other response classes retain
   Referrer-Policy: no-referrer. Native form page URLs reject query/body input
   and never contain credentials, invitation values, proof or CSRF values.

No new route, representation, external identity provider, caller-controlled
destination, script or resource source is introduced. Start still enforces proof,
signed binder, canonical same-origin provenance, strict body parsing, rate
limits and immutable server-selected Google Location. No null-Origin exception.

## Precise security boundary

Same-origin Referrer-Policy exposes only the form page's URL to the same origin,
and sends no referrer across origins. Callback URLs remain no-referrer/no-store.
Only /login can initiate the fixed approved Google form redirect; logout stays
self-only. CSP path matching may be ignored on redirect hops, so the policy must
not be described as enforcing the authorize path on every hop. The application's
fixed HTTPS Location enforces the exact initial authorize endpoint; the CSP
exception permits the accounts.google.com origin for applicable redirect checks.

These amend explicit reviewed browser controls. Architecture/security/test
reviews passed and the owner explicitly approved the scoped adjustment on
2026-10-26. Neither an
HTTP-contract approval nor a passing mocked HTTP test implicitly approves this
policy delta. There is no accepted security risk or production deployment here.

## Required evidence

- Preserve the unmodified browser failure as a failing compatibility baseline.
- Change headers only in a synthetic diagnostic fixture to isolate each cause;
  record Origin classification, status, blocked CSP directive and engine version,
  never blockedURI, callback query, binder, proof or tokens.
- Verify the exact proposed policy with native HTML forms over HTTPS, signed
  RS256 synthetic Google responses, actual PostgreSQL/runtime and no policy bypass.
- Cross-origin/null-origin forms and invalid CSRF still fail; non-login pages
  cannot submit to Google; external attacker form navigation remains blocked.
- Header matrix tests bind each exception to exact method/path/status/content
  class, and assert callback/error/JSON/redirect defaults remain no-referrer.
- Obtain independent reviews and record the owner's decision before activation.
