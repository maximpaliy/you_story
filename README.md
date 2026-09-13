# Codex AI Team Bootstrap

A starter repository for a GitHub-centered, multi-agent Codex workflow.

The project deliberately uses a small number of durable agent roles plus reusable specialist skills. This avoids maintaining a permanent "employee" for every technology while still allowing architecture, API, database, client, infrastructure, testing, and review expertise to participate when needed.

## Roles

- **Lead** — orchestrates the workflow and delegates work.
- **Architect** — owns system-level design and cross-client concerns.
- **Test Designer** — defines tests before implementation.
- **Implementer** — implements approved work.
- **Reviewer** — independently reviews architecture, tests, code, and verification evidence.

Specialist skills provide focused expertise for API, database, web, Android, Telegram, infrastructure, and testing.

## First use

1. Create a GitHub repository from this template.
2. Fill in `.github/ISSUE_TEMPLATE/project-definition.yml` and create the first Project Definition issue.
3. Ask Codex to work on that issue.
4. The lead/architect workflow should produce a product definition and proposed architecture.
5. Review and approve the architecture before implementation begins.

Do not connect issue creation directly to automatic agent execution yet. Validate the workflow manually first; automate later if it proves useful.

## Important note about Codex configuration

This bootstrap intentionally keeps agent role definitions and workflow instructions in repository files. Exact Codex runtime configuration is version-sensitive, so do not treat a guessed `.codex/config.toml` as authoritative. Configure model/subagent settings using the Codex version and documentation available in your environment.

The repository is therefore useful even when run from the Codex app, CLI, or another compatible harness.
