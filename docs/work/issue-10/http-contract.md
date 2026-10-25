# Proposed HTTP contract — Issue #10

Status: approved by the human owner on 2026-10-26 in this conversation.
Existing `/live` and `/ready` remain as currently generated. The accompanying
[OpenAPI candidate](openapi.candidate.json) is a design artifact, not an exposed API.

## Route inventory

| Method/path | Representation and input | Success | Failure |
| --- | --- | --- | --- |
| GET /login | HTML; no query/body input | 200 login form with hidden proof, destination and optional invitation input; signed login binder as needed | 503 unavailable; valid authenticated browser 303 to `/` without creating a flow |
| POST /auth/google/start | Form only, <=4096 bytes; proof required; destination optional enum home/calendar/catalog, default home; invitation optional canonical 43-char token; no other/duplicate fields | 303 to fixed Google authorize endpoint with code+PKCE, state/nonce, scopes exactly openid/profile | 400 invalid_request; 403 forbidden; 409 already_authenticated/login_in_progress; 413 payload_too_large; 415 unsupported_media_type; 429 rate_limited; 503 unavailable |
| GET /auth/google/callback | <=8192 query bytes; exactly one state and either code or error; approved optional extras from Issue #6; no request body | 303 to bound fixed destination, with fresh committed session cookie; catalog pending does not invalidate login | Generic HTML retry page: 400 callback/validation/provisioning-eligibility failure; 409 authenticated browser conflict with session unchanged; 429 limit; 503 unavailable; never echo provider fields |
| GET / | Authenticated HTML; no query/body input | 200 minimal home, readiness state, profile link and logout form | 303 `/login` for absent/invalid/expired session; 503 unavailable |
| GET /profile | Authenticated HTML; no query/body input | 200 own minimal profile/readiness and logout form | Same as home |
| GET /api/v1/profile | JSON; no query/body input, no target ID | 200 exact OwnProfile below | 400 invalid_request for query/body inputs; 401 unauthenticated; 503 unavailable |
| POST /logout | Authenticated form only, <=4096 bytes; exactly one csrf field, no other/duplicate fields | 303 `/login` after revoke commit and expiry of session and login cookies | 401 unauthenticated for repeat/missing/invalid session, no revoke; 400 invalid_request; 403 forbidden; 413 payload_too_large; 415 unsupported_media_type; 503 unavailable |

Only these methods are registered: unsupported methods return 405 with Allow.
In particular HEAD callback and GET logout never execute a command. Framework
404/405/500 and early failures carry the outer response policy and safe envelope.
Home/profile/login reject unsupported query/body input as 400 invalid_request;
there are no invitation-token query links. All unexpected errors are generic 500.

No JSON logout alias is added: the only JSON product operation is the read-only
own-profile query. This keeps a single representation per route. No CSRF token
endpoint, profile mutation, session list/revoke-all, invitation admin, linking,
account deletion, catalog retry or Android/Telegram token route exists.

## OwnProfile

Exact JSON schema (additional properties forbidden):

```json
{
  "user_id": "internal UUID of the authenticated user",
  "provisioning_state": "catalog_pending or ready"
}
```

The user identifier comes solely from a successful production session resolver.
It is an opaque stable identifier, not a credential or an authorization input.
Tenant identity stays internal to the validated actor/session context and is
never returned in this profile response.
Do not return session UUID, issuer/subject, names/email, token/digest, provider
payload, catalog IDs or private preferences. No field can override authority.
Unknown query parameters, including user_id/tenant_id/actor/session, are rejected;
credential-bearing URLs, bodies and Authorization headers cannot authenticate.
No request form/query/body is accepted on this route. Responses never renew
cookie Max-Age or perform catalog provisioning.

HTML shows only signed-in status and readiness, with escaped identifiers if
needed; names/provider content are deliberately absent from this minimal profile.
Both pending and ready actors can use home/profile/logout. Stored-input probes
must prove unselected control/preference/provider canaries cannot reach the page;
do not claim to exercise a stored text rendering sink that this slice lacks.

## Redirects and cookies

Destination enum maps home -> `/`, calendar -> `/calendar`, catalog -> `/catalog`.
Only home is offered by the MVP-07 form. The other values preserve the approved
transaction binding, but their feature routes are not introduced here: following
them currently yields the existing bounded 404. Never substitute arbitrary
return URLs or interpret destinations as URIs. Login tests cover enum rejection
and the fixed mapping; later slices add those features under their own contracts.

Successful login alone sets `__Host-you_story_session`: Secure, HttpOnly,
SameSite=Lax, Path=/, no Domain, Max-Age=2592000. Binder is
`__Host-you_story_login` with the same flags, original maximum 600-second expiry
and signed original deadline. No cookie is renewed by ordinary profile requests.
Logout expires both using matching scope, Max-Age=0 and past Expires, only after
revocation commit. Failed/old callbacks never replace/clear a current valid
session or a newer binder. No raw token in Location, JSON, logs or localStorage.

## Error and policy contract

JSON errors retain the existing envelope:
`{"error":{"code":"stable_code","message":"fixed safe message","correlation_id":"server UUID"}}`.
No request fragments, exception text, provider descriptions or existence details.
Codes use the names in the route table; messages are fixed per code. Callback
failure HTML always has one generic message and fixed `/login` retry link,
including 409/429/503 and unexpected 500. Only HTTP status and Retry-After on 429
vary; no private/provider detail or different identity eligibility message.
Every GET callback failure, including early parsing/middleware failure, passes
through that HTML renderer and receives CSP. Other errors are JSON, including
unsupported-method framework errors; other HTML successes also receive CSP.

Order unsafe request checks as ADR-009: method/auth boundary, provenance,
declared/streamed byte cap and media type, field parsing, CSRF, command dispatch.
Missing valid session yields 401 on logout/API; HTML private GET redirects.
Valid session but bad origin/proof yields the same 403 forbidden regardless of
which provenance/CSRF subcheck failed. Limit denials use the same 429 plus
Retry-After (ceiling seconds to that window's end, >=1). Capacity/service failures
use generic 503 without selecting a different identity-dependent response.

All new routes/errors/redirects use Cache-Control: no-store and generated
X-Correlation-ID. Apply the full ADR-009 response-class header matrix and exact
nonce CSP for HTML. No CORS credentials or permissive origins. Content-type is
text/html; charset=utf-8 for HTML and application/json for JSON. Normal form
submissions accept only form-urlencoded with no parameter or one UTF-8 charset.

## Owner decision (approved on 2026-10-26)

The owner approved the route inventory, read-only profile fields, form-only
logout, fixed destination behavior and response/error choices above. The previously approved
Google lifecycle, cookie, CSRF and SQL-isolation decisions are not being reopened.
This approval grants no deployment permission or security-risk acceptance.

## Owner clarification

The owner chose to retain user_id for debugging and keep tenant_id internal.
This narrows the proposed response to user_id and provisioning_state; it does
not grant permission to select a user/tenant through request input. The broader HTTP contract was subsequently approved by the owner on 2026-10-26.

## Contract approval

On 2026-10-26 the owner stated: "Approved HTTP contract". Approval covers this
contract after the user_id/tenant_id clarification. Implementation may proceed
under the existing design/test/security gates. No deployment or risk acceptance
is implied. No further API approval is needed for this unchanged contract.

## Approved browser compatibility amendment

The owner approved ADR-012 on 2026-10-26 after independent architecture, security
and test reviews and actual Chromium diagnostics. Its exact successful-form-page
header exceptions amend the ADR-009 references above. No route, response schema,
CSRF/provenance check or caller-selected redirect changes.
