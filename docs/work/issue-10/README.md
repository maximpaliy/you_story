# Issue #10 — Allowlisted Google sign-in and session logout

Issue: https://github.com/maximpaliy/you_story/issues/10 (`MVP-07`).
Date: 2026-10-25.

Status: **design reviews passed; concrete HTTP contract awaits owner approval**.
The application still exposes health checks only. No login implementation or
runtime authentication tests are claimed; #10 remains open.

## Reviewable result

- [Implementation design and prerequisite plan](design.md)
- [Exact proposed HTTP contract and owner decision](http-contract.md)
- [Candidate OpenAPI](openapi.candidate.json), separate from the active contract
- [Implementation test design](test-design.md)
- Independent [architecture](architecture-review.md),
  [security](security-review.md) and [test-design](test-design-review.md) reviews
- [Verification and remaining gates](verification.md)
- [Final documentation review](documentation-review.md)

The accepted #6 lifecycle and ADR-007/008/009/011 are reused on current main
`ca99acd`, merged [PR #25](https://github.com/maximpaliy/you_story/pull/25).
Issue #9 is closed: reuse its implemented database wrappers and verification.
The initially provided checkout was stale and was updated before final review.
#10 adds provider/crypto/browser/public-port integration, trusted actor issuance
and login-only catalog-pair provisioning; it does not redesign the database
foundation or make #9 depend on this later integration. Proposed profile data is only
the resolved user's UUID and catalog readiness; tenant identity stays internal. Logout is
a CSRF-protected form POST. No profile-name persistence is introduced.

## Owner decision

Approve [the concrete HTTP contract](http-contract.md): `/login`, Google
start/callback, `/`, `/profile`, read-only `/api/v1/profile`, and form-only
`POST /logout`, with the listed fields, redirects and error representations.
The Google lifecycle/cookie policy already has approval; this decision concerns
the new concrete endpoint/schema choices.

The source is the root [AGENTS.md](../../../AGENTS.md), whose human gate says:
“The human owner approves: ... externally visible API contract changes.”
The [approved backlog](../proposed-mvp-backlog.md) also states its approval
“does not approve an API contract.” The accepted Q01 query inventory explicitly
does not define final HTTP endpoints. No new deployment or risk acceptance is
requested. Existing 005 SQL is reused unchanged; any discovered SQL defect would
need a separately reviewed additive fix. Owner API approval does not substitute
for implementation review or runtime verification.

## Completion evidence and limits

Changed only the issue's design/contract/test/review/status documentation.
Documentation structure, references, JSON and contract consistency were checked;
see verification for exact checks and limits. Independent design reviews passed
after remediation; no implementation/security evidence review has happened.
SEC-01/05/06/07 and #10's integration gates stay open; #9 is closed. Nothing here
marks proposed ADR-010 feature policies accepted or authorizes production data,
infrastructure or deployment.
