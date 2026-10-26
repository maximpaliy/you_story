# You Story

A Python/FastAPI modular monolith with allowlisted Google sign-in, opaque
PostgreSQL sessions, minimal authenticated home/profile, logout, and login-only
empty personal catalog provisioning. The HTTP contract exposes only user_id
and provisioning_state in profile JSON; tenant identity remains internal.

The merged Issue #9 database foundation is reused unchanged. Issue #10 supplies
provider/crypto/browser integration; its [evidence](docs/work/issue-10/README.md)
records independent reviews and test limits. Catalog editing/practice, sharing,
media, deletion and offline features remain unavailable. No production deployment
or real-user-data approval is implied by the local implementation.

## Local development and verification

Requirements: Python 3.12.14, uv 0.12.19, Docker with Compose. All commands below
use synthetic data and public, localhost-only fixture passwords. Never use these
credentials or the fixture bootstrap in a shared/deployed environment.

```sh
docker compose up -d --wait db
make sync
export PLAYWRIGHT_BROWSERS_PATH="$PWD/work/browsers"
uv run --frozen python -m playwright install --with-deps chromium
export TEST_ADMIN_URL=postgresql://postgres:local-fixture-only@127.0.0.1:55439/you_story_issue9_test
export TEST_DATABASE_CONFIRM=disposable
make check
```

The full test command is destructive only inside the dedicated
`you_story_issue9_test` database carrying the fixture marker installed by
`tools/db-bootstrap.sql`. It refuses missing configuration or another database;
it never substitutes SQLite, a superuser for runtime isolation, or skipped tests.
Use `make unit` for the non-PostgreSQL subset. Do not run PostgreSQL suites
concurrently against the same fixture database. Supported upgrade points are
`000_security` and the merged `004_media` foundation; tests cover empty-to-head,
bootstrap-to-head, populated foundation-to-head, every real revision's
transactional failure/retry, and ledger/checksum mismatch.

After the checks, run migrations as the separate owner process, then start HTTP
with the runtime database credential and the auth settings described below:

```sh
MIGRATION_DATABASE_URL=postgresql://app_owner:owner-fixture@127.0.0.1:55439/you_story_issue9_test \
  uv run --frozen python -m you_story.migrations
YOU_STORY_DATABASE_URL=postgresql+psycopg://app_runtime:runtime-fixture@127.0.0.1:55439/you_story_issue9_test \
  uv run --frozen uvicorn you_story.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

`GET /live` checks the process; `GET /ready` checks bounded database access,
actual runtime identity/privileges and the exact migration ledger. Errors use a
safe envelope and server-generated `X-Correlation-ID`. Interactive API docs are
disabled; the approved auth/profile routes are registered. The generated contract
is [docs/api/openapi.json](docs/api/openapi.json); `make openapi` regenerates it
for review. Runtime configuration has no owner-credential field and startup
performs no migration. Keep owner/runtime credentials in separate processes.

Migrations live under each owning module; the controlled runner alone can apply
packaged, reviewed schema revisions. A failure rolls back its current revision;
fix the cause and rerun the same command. Never edit an applied revision, weaken
RLS or backfill tenant data through this runner. New migrations, supported
upgrade points, SQL registrations and deployment commands require reviewed
manifest updates. No production resources are provisioned here.

`docker compose stop db` stops the local fixture without deleting its data.
The source and built wheel are checked for module boundaries and unregistered
execution roots. CI runs the same lint/type/architecture/contract/PostgreSQL/
migration/package checks. Dependency, artifact, cloud-IAM, vulnerability and
production operational gates remain owned by later platform issues.

## Development workflow

The repository uses the GitHub-centered review workflow below. Keep requirements,
architecture, tests and review evidence as durable project memory.

## Durable roles

- **Lead / Orchestrator** — owns workflow, delegation, gates, and project state.
- **Architect** — owns system-level design and cross-client concerns.
- **Test Designer** — designs verification before implementation.
- **Implementer** — implements approved work.
- **Reviewer** — independently reviews architecture, tests, code, and evidence.

## Specialist skills

Use only when relevant:

- Security
- API
- Database/Data
- Web/UI
- Android
- Telegram
- Infrastructure/Operations
- Test Review

A specialist is not expected to edit production code merely because its domain is involved. Its default role is focused analysis/review and documented recommendations.

## Project workflow

### First issue: Project Definition

Create a GitHub issue using the Project Definition template. The issue describes what the product must do and the technology constraints/preferences. It should not prescribe the implementation architecture.

Then ask the Lead to work on the issue.

The foundation workflow is:

```text
Project Definition
      ↓
Architecture Design
      ↓
Independent Architecture Review
      ↓
Security Review
      ↓
Human Approval
      ↓
Test Design
      ↓
Independent Test Review
      ↓
Human Approval if architecture/test strategy changes materially
```

No production implementation is part of the foundation workflow.

### Feature issues

Feature work follows the same gates where relevant:

```text
Issue
  ↓
Requirements / acceptance criteria
  ↓
Architecture impact check
  ↓
Relevant specialist reviews
  ↓
Architecture / ADR
  ↓
Independent architecture review
  ↓
Security review when relevant
  ↓
Human approval when required
  ↓
Test design + independent test review
  ↓
Implementation
  ↓
Automated verification
  ↓
Independent code review
```

## GitHub is the durable project source of truth

Keep requirements, architecture, ADRs, test strategy, security decisions, and work status in the repository. Issues and PRs provide the work-item history.

## Automation policy

Do not initially trigger agents automatically from issue creation. Validate the workflow manually first. Automation can be introduced after the process is stable and its failure modes are understood.

## Codex runtime configuration

This repository deliberately does not guess a version-specific `.codex/config.toml`. Current OpenAI agent runtimes support explicit multi-agent orchestration and reusable skills, but the exact configuration surface depends on the runtime you use. Keep runtime-specific settings outside the project rules unless you have verified them against the current documentation.

The repository can therefore serve as the durable project/workflow layer while the Codex app, CLI, SDK, or another compatible harness supplies execution.

## Approved Google web authentication configuration

The HTTP contract for #10 was approved on 2026-10-26. The runtime requires
`YOU_STORY_AUTH_ORIGIN` (the canonical external HTTPS origin),
`YOU_STORY_AUTH_CLIENT_ID`, `YOU_STORY_AUTH_CLIENT_SECRET`, and separately
generated `YOU_STORY_AUTH_PREAUTH_KEY`, `YOU_STORY_AUTH_VERIFIER_KEY` and
`YOU_STORY_AUTH_IP_KEY`. Each key is canonical unpadded base64url of 32 random
bytes and must be distinct. Inject secrets securely; no values or production
defaults are committed. The exact registered Google redirect URI is the origin
plus `/auth/google/callback`. Scopes are only `openid profile`.

Keep Uvicorn access logs disabled and proxy headers disabled with the command
above: default access records contain callback secrets, and untrusted forwarding
headers must not choose rate-limit IP keys. The app also suppresses Uvicorn
access records as defense in depth. An eventual trusted-proxy deployment must
provide its own reviewed client-address handling and query-free logging; no
production proxy configuration is introduced here.

The profile JSON contains only `user_id` and `provisioning_state`; tenant IDs
stay inside validated server context. Run `make browser` against the guarded
disposable database to verify the real HTTPS browser journeys. The browser
runner is pinned in the lockfile; evidence records the exact Chromium version.

## Personal Yousician catalog

Issue #11 adds the personal guitar/piano catalog at `/catalog` and JSON routes
under `/api/v1/catalog`. Songs contain versions (required level 0–15), which
contain fragments (optional measured length and initially zero note count).
General search matches names or the containing song author; the author filter
combines with source/instrument/type/ancestor filters. There is no sharing or import.

Inject `YOU_STORY_CATALOG_CURSOR_KEY` as a separate canonical unpadded base64url
encoding of 32 random bytes, with no checked-in/default key. Startup fails
closed if absent or invalid. Replacing this key immediately invalidates existing
15-minute pagination cursors. Treat cursors and catalog search/referrer URLs as
private: retain disabled Uvicorn access logging and query/referrer suppression
at any future proxy. No production proxy or deployment is added by this issue.

Catalog writes require the aggregate ETag from GET `/api/v1/catalog` in
`If-Match: "catalog:<id>:<version>"`; edits/moves/tombstones also require
`expected_entry_version`. Entry-detail ETags cannot substitute for catalog
preconditions. Include the session-bound `X-CSRF-Token` from the authenticated
catalog form and same-origin provenance on JSON writes. Missing/stale versions
return 428/412; re-read and review changes before resubmitting.
