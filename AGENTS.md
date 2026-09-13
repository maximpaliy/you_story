# Codex Project Rules

## Mission
Build the application through a disciplined multi-agent workflow. The repository is the durable source of truth.

## Non-negotiable workflow
1. Start from a GitHub Issue.
2. For a new project: define product requirements and technical constraints before architecture.
3. For a feature: clarify requirements before design.
4. Architecture comes before implementation.
5. Client concerns (web, Android, Telegram) are considered during architecture, not after backend design.
6. Architecture must be independently reviewed before implementation.
7. Test strategy and test cases are designed before production implementation.
8. Test design is independently reviewed.
9. Implementation follows the approved design and tests.
10. Run appropriate automated checks before declaring completion.
11. Code review is independent of implementation.
12. Record important architectural decisions in `docs/architecture/decisions/`.

## Source of truth
- Product requirements: `docs/project/product-definition.md`
- Architecture: `docs/project/architecture.md`
- Architecture review: `docs/project/architecture-review.md`
- Test strategy: `docs/testing/strategy.md`
- Work status: `docs/work/`
- GitHub Issues and PRs: authoritative workflow state for work items.

## Agent behavior
- Do not silently change approved architecture.
- If requirements conflict, stop and surface the conflict.
- Prefer small, reviewable changes.
- Do not mark work complete without verification evidence.
- Do not create speculative infrastructure just because it may be useful later.
- When parallel work is useful, delegate independent analysis/review rather than duplicating it sequentially.

## Human approval gates
The human owner approves:
- initial architecture,
- material architecture changes,
- security/privacy trade-offs,
- externally visible API contract changes,
- production infrastructure with meaningful cost or operational impact.

## Communication
Every completed work item should state:
- what changed,
- what was verified,
- unresolved risks/questions,
- files changed.
