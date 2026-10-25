# Independent final documentation review — Issue #10

- Date: 2026-10-25
- Reviewer: independent final-review agent, separate from the design/test authors
- Scope: Issue #10 design, HTTP/OpenAPI candidate, tests, reviews, status,
  README and verification against AGENTS.md and the approved lifecycle
- Current baseline: merged PR #25, main `ca99acd`, closed Issue #9
- Verdict: **pass for corrected documentation-only preparation**; this report
  supersedes the initial stale-baseline documentation pass

## Freshness correction and findings

The supplied checkout initially lacked merged PR #25. The lead found that delta
during its final freshness check, imported exact upstream main, and rewrote the
proposal to reuse the already implemented database boundary. The initial review's
assumptions about missing foundation DDL, permanent unconsumed allowlists and an
empty-session preflight are superseded and are not implementation requirements.

Re-read the corrected design, test design, status, README and verification
against actual `005_identity.sql` and its foundation design/review/evidence.
The plan reuses the seven-table schema and exact wrapper signatures unchanged.
It retains nullable legacy session linkage/CSRF and failed resolution without
touch; no empty-table guard, backfill or replacement migration is introduced.
Admission uses actual bearer/allowlist metadata and permitted_subject, consumes
unknown-subject allowlist admission atomically, and prevents an explicit bearer
digest from falling back to allowlist. Existing active identity bypasses
admission as the merged finalizer requires.

Inspected actual start/claim/finish/limiter SQL. The integration description
preserves the shared advisory auth-control lock, clock refresh after blocking
waits, single IP-stage cleanup batch and commit of ordinary typed denials so
invitation-attempt counters survive. Provider exchange occurs outside the
committed claim transaction. New production ActorContext issuance, typed adapter
provenance, callback-only catalog ensure, actor/session matching before the
existing digest-targeted ready wrapper, and browser/crypto delivery are correctly
assigned to #10. They are not reverse prerequisites for closed #9.

The resolver's minimal return shape is retained; no profile table query or
CSRF-digest grant is invented. The concrete contract and candidate agree on
seven new operations plus two unchanged health operations, closed minimal
profile fields, form-only logout, bounded inputs, fixed destinations and generic
HTML callback failures. The new profile URI/schema is correctly presented for
owner approval under AGENTS.md; accepted auth lifecycle choices are reused.

An earlier wording inconsistency prohibited every actor factory from the wheel
while requiring a production trusted issuer. The corrected text prohibits
public/test factories and retains the sole private trusted issuer. No
contradiction remains. Stored-canary exclusion tests are clearly distinguished
from a nonexistent shipped stored-text sink. Race/fault, real-role PostgreSQL,
provider, HTTP, browser and telemetry evidence are planned, not described as
executed.

The independent architecture/security/test-design reports now explicitly
supersede their own stale passes with current-main dispositions. No blocking
documentation finding remains in the corrected artifacts.

## Verification and limits

Re-ran Python JSON assertions against current-main active OpenAPI: the exact
nine-path method inventory, unchanged health operations/shared schemas and every
callback error's HTML representation pass. Inspected closed profile/form schemas
and cookie security. `git diff --check` passes. No application, PostgreSQL,
provider or browser tests ran; the foundation's reported 217 tests are prior
upstream evidence, not a new #10 result. Active API and production source are not
changed by this documentation-only proposal.

This is not implementation code review or runtime security evidence review.
Owner approval of the concrete HTTP contract, exact typed-adapter/actor/catalog
implementation review, dependency selection, complete implementation and
automated evidence, and independent implementation code/security reviews remain
required. Unchanged reuse of merged SQL needs no new DDL approval; any discovered
database defect requires a separately reviewed additive fix. Issue #10 and
cumulative applicable SEC feature findings remain open; #9 is closed. No
production deployment, real-user-data use or security-risk acceptance is implied.
