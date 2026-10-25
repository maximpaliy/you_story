# Issue #10 design verification

Date: 2026-10-25. Baseline: `ca99acd` (merged PR #25 auth database foundation).
Scope: documentation and candidate HTTP contract only. No production source,
dependency, migration, runtime privilege or active OpenAPI artifact changed.

The supplied checkout initially pointed to `ce4b102`. A final GitHub freshness
check found merged PR #25 and confirmed live #9 is closed. The workspace was
updated to the exact upstream signed `ca99acd466c529b49ba69a296771f77f065ed736`
commit; its reconstructed tree was verified as
`0089aa30c99aaaa578d77d52ada62ea3b2c4dad6`. The API-delivered upstream patch was
used because shell git's configured proxy was unreachable. This imports already
merged upstream files, not new production changes in this proposal. All final
reviews supersede their initially stale baseline assumptions.

## Checks

- `git diff --check`: passed for tracked differences; the new directory also
  received an explicit trailing-whitespace scan before staging.
- Python standard-library JSON parsing: candidate parses successfully and all
  local JSON references resolve.
- Contract assertions: exactly seven new operations plus two unchanged health
  operations; exact method/path inventory, unique operation IDs, strict profile
  and form fields, cookie-only private query auth, callback error HTML and body
  limits, no additional endpoint or widened health contract.
- Local Markdown links: referenced files exist; GitHub web targets are not
  represented as network-tested links.
- AUTH6-01–27 and WEB-01–05 source-to-test-design traceability were independently
  reviewed. Candidate/profile/error/schema inventory was independently reviewed.

Independent architecture, security and test-design reviews passed after
remediation; each report retains findings and the focused final disposition.
These are design reviews, not implementation code or runtime security reviews.

## Not executed

No application tests, OIDC/browser journeys, PostgreSQL auth tests or new
migrations ran. `make check` was not run for this documentation-only increment;
the full cumulative command and browser suite are mandatory after implementation.
There is no live Google exchange or deployed authentication evidence. No issue
closure, merge, production deployment or real-user-data use is authorized by
this record.

## Remaining gates

1. Owner approval of the exact HTTP contract under AGENTS.md.
2. Typed adapters, actor/session provenance, catalog SQL-site registry and pinned
   provider/crypto/browser tooling reviewed for implementation. Existing 005
   SQL/reviews are reused unchanged; no new DDL is planned.
3. Implement login-only catalog provisioning and conditional-ready orchestration
   on the existing database wrappers; extend the cumulative integration matrix.
4. Implement the whole login/profile/logout slice and run the named suites,
   canary scans, fault/race cases and cumulative checks without hidden skips.
5. Independent implementation security/code review of actual evidence before
   completion. SEC-01/05/06/07 remain open for their applicable runtime scopes.
