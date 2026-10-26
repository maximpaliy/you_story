# ADR-013: Catalog native-form referrer policy

Status: Accepted by the owner on 2026-10-26 after independent design reviews.
Issue: #11. Additive to ADR-009/012; no deployment authorization.

## Proposed decision

Successful authenticated GET /catalog, /catalog/entries/new,
/catalog/entries/{entry_id}, and /catalog/entries/{entry_id}/edit use
Referrer-Policy: same-origin so native form submissions supply the same-origin
Referer required by existing provenance validation when Origin is absent.
These are exact route patterns, not a prefix-wide exemption. Apply only to
200 text/html responses with valid sessions. Every other response retains the
existing policy. Preserve all nonce CSP, no-store, CSRF, Fetch Metadata, cookie,
strict content-type and origin checks. No security check is bypassed.

Unlike ADR-012's queryless pages, catalog navigation accepts allowlisted search,
parent and pagination parameters. Same-origin Referer can carry these parameters
to this app. The application must never log Referer, catalog raw URL/query,
request body or cursor at any enabled application/server/proxy sink. Test with
positive canaries in search, names, IDs and cursors. Do not embed third-party
resources or accept arbitrary destinations. Cross-origin requests receive no
Referer under same-origin policy. This is a scoped new privacy decision, requiring
owner approval; no risk is represented as already accepted.

## Alternatives and verification

Keeping no-referrer breaks native forms in browsers that omit Origin; relaxing
provenance or adding scripts would change the approved security model further.
Use actual pinned Chromium/HTTPS to prove create/edit/move/tombstone submissions,
Origin-absent Referer fallback, cross-origin suppression, and no-store/CSP on
all successful and failed route classes. Verify every logging sink with positive
canaries. Independent architecture/security/test-design review precedes code.

## Owner approval — 2026-10-26

The owner approved the MVP contract after adding author search: “Great, looks
good for MVP, approved”. This approves the exact issue-11 contract including
author search, scoped catalog defaults and ADR-013 as presented. Independent
author-search design/security/test delta review passed. Implementation and
verification may proceed; deployment and unrelated ADR-010 work are not included.
