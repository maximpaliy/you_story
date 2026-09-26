# Codex AI Team Bootstrap

A GitHub-centered starter repository for a disciplined multi-agent Codex workflow.

The design intentionally uses a small set of durable roles plus focused specialist skills. Current OpenAI guidance favors modular skills and contextual instructions rather than bloated permanent prompts, so the repository keeps role instructions short and puts technology-specific review guidance in skills.

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
