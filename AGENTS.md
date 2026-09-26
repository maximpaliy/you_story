# Codex Project Rules

## Mission
Build the application through a disciplined, GitHub-centered multi-agent workflow. Keep repository documentation as the durable project memory.

## Required workflow
1. Start work from a GitHub Issue.
2. Clarify requirements before design.
3. Architecture comes before production implementation.
4. Consider all currently planned clients and integrations during architecture.
5. Obtain independent architecture review before implementation.
6. For security-sensitive work, obtain an independent security review before implementation or deployment.
7. Design tests before production implementation and review the test design independently.
8. Implement only against approved requirements, architecture, and test design.
9. Run appropriate automated checks and preserve verification evidence.
10. Perform independent code review before completion.
11. Record material architectural decisions in `docs/architecture/decisions/`.

## Source of truth
- Product requirements: `docs/project/product-definition.md`
- Architecture: `docs/project/architecture.md`
- Architecture review: `docs/project/architecture-review.md`
- Security review: `docs/project/security-review.md`
- Test strategy: `docs/testing/strategy.md`
- Work status: `docs/work/`
- GitHub Issues and PRs: workflow state for individual work items

## Agent behavior
- Read only the project documents relevant to the task; do not mechanically load the entire repository for every small change.
- Do not silently change approved architecture or technology constraints.
- If requirements conflict or are materially ambiguous, surface the conflict instead of inventing a product decision.
- Prefer small, reviewable changes.
- Do not create speculative infrastructure merely because it may be useful later.
- Use specialist skills for focused expertise instead of maintaining a permanent agent for every technology.
- Delegate independent tasks when parallel work improves quality or speed; coordinate carefully when agents edit the same files.
- Do not treat passing tests as proof of correctness.
- Never hide failing tests, security findings, lint errors, or infrastructure problems.

## Human approval gates
The human owner approves:
- initial architecture;
- material architecture changes;
- security/privacy trade-offs and accepted security risks;
- externally visible API contract changes;
- production infrastructure with meaningful cost or operational impact;
- technologies outside the approved technology constraints.

## Completion evidence
Every completed work item should state:
- what changed;
- what was verified;
- unresolved risks/questions;
- files changed;
- security review status when relevant.
