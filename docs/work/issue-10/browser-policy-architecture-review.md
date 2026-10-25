# Independent architecture review — proposed ADR-012

- Date: 2026-10-26
- Reviewer: architecture-review agent, independent of the browser-policy proposal
  and delivery implementation; this reviewer authored identity-core code, which
  is outside this policy-design review
- Material: proposed ADR-012, accepted ADR-009/011, Issue #10 HTTP/design
  contracts, current outer response policy and native Chromium journey fixture,
  independent implementation review's ICR10-05 diagnosis
- Verdict: **pass for the proposed bounded architecture amendment**;
  **owner approval and independent security/test review remain pending**
- Activation: **not approved by this report**; original policy remains active

## Assessment

Native form navigation is a required part of the approved server-rendered
Google login/logout experience. The reported original-policy baseline is a real
compatibility failure: native login POST has opaque Origin and no Referer,
receives 403, and causes zero provider exchanges. The current provenance gate
correctly denies that request. Changing the test's Origin or permitting opaque
provenance would conceal the conflict rather than fix the architecture.

Proposed `Referrer-Policy: same-origin` only on successful form-containing
GET `/login`, `/` and `/profile` is a bounded correction. These pages reject
query/body inputs, contain no credential in their URL, and remain no-store.
Same-origin provenance becomes available for the existing native POST controls;
cross-origin referrers remain suppressed. Signed binder/proof, authenticated CSRF,
exact canonical-origin comparison and Fetch Metadata checks stay independent.
No null-Origin or permissive Referer exception is introduced.

The proposed login-only `form-action` addition permits navigation already named
by the approved fixed Google Authorization Code/PKCE flow. It introduces no
provider selection, arbitrary destination, remote script or resource loading.
The policy source contains only the fixed HTTPS Google authorize endpoint and
no state, nonce, code, invitation or proof. As ADR-012 correctly states, CSP
path matching may be ignored on redirects: the immutable application-selected
Location enforces the initial exact endpoint, while CSP permits the Google
origin for applicable redirect checks. Do not describe the CSP path as a
universal redirect-hop allowlist.

The second, form-action compatibility layer is still a browser-test hypothesis
in the proposal at the time of this review. The design is reasonable without
claiming it has been demonstrated. Preserve its independent diagnostic outcome
and test the complete proposed policy before reporting the journey passed.
The architecture pass is not operational evidence for that layer.

## Required implementation boundaries after approval

1. Select exceptions by exact request method/path, successful 200 status and HTML
   representation: only GET `/login`, `/` and `/profile` use same-origin
   referrer policy. Only that GET `/login` class gains the Google form source.
   A matching URL alone is insufficient for errors/redirects/JSON/other methods.
2. Callback HTML, every error, redirect, JSON/API response and other response
   class retains no-referrer. Existing full outer response policy still applies
   to framework and early failures. Other pages keep self-only form-action.
3. Preserve all other exact CSP directives, fresh 32-byte nonce generation,
   no-store and security headers. No wildcard, broad Google domain list,
   external logout destination or implicit resource exception is introduced.
4. Preserve trusted deployment origin/provider configuration and the literal
   fixed authorize URL. Neither Host/forwarding headers nor request fields may
   choose a CSP source, expected origin, provider URL or redirect target.
5. Record header-classification and native-browser positive/negative tests,
   including unchanged rejection of null/cross-origin provenance, bad CSRF and
   external attacker forms; verify non-login pages cannot submit to Google.
   Diagnostic fixture overrides are never production defaults or final evidence.

## Owner and completion gate

This is an explicit amendment to owner-approved browser controls, not a silent
compatibility fallback or an implication of the prior HTTP-contract approval.
The proposed ADR correctly keeps activation blocked on independent architecture,
security and test review plus the owner's specific decision. This report
approves presenting that bounded proposal; it does not supply the human decision
or accept a security/privacy risk.

No policy code was changed or browser/DB test executed by this reviewer for
this report. The baseline diagnosis is attributed to the independent browser
runner. Full proposed-policy browser evidence, exact implementation review and
final cumulative checks remain required before Issue #10 completion. Identity
core correctness is outside this policy-design verdict and needs another
reviewer's independent implementation disposition.
