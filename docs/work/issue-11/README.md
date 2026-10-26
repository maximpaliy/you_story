# Issue #11 — Searchable personal Yousician catalog

Issue: https://github.com/maximpaliy/you_story/issues/11 (MVP-08).
Baseline: main `4c6ac30`, including completed #10.

The owner approved the exact HTTP contract, author search, scoped catalog defaults
and ADR-013 on 2026-10-26. Independent architecture/security/test-design reviews
passed, including the author amendment. Implementation now supplies catalog
policy/service, migration 006, actor-scoped PostgreSQL persistence, JSON API and
native HTML forms. See [verification](verification.md) for actual checks and
remaining evidence; design review alone is never runtime evidence.

The personal catalog remains provisioned by login. There are no user catalog-
create/rename/delete commands, sharing activation, practice, characteristics,
customizations, import, or Songsterr workflow. Songsterr is a persistence/policy
fixture only. No deployment or unrelated ADR-010 approval is inferred.

Contract: [HTTP](http-contract.md), [OpenAPI candidate](openapi.candidate.json).
Implementation design: [design](design.md), [tests](test-design.md).
Independent implementation reviews: [code](implementation-code-review.md) and
[security](implementation-security-review.md). Their initial findings and
remediation verdicts remain explicit, with evidence limits recorded.
