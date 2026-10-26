# Issue #11 test design

Status: independently reviewed and approved for implementation; execution is
recorded in verification.md, separately from this design.
Use the approved docs/testing/strategy.md and Issue #8 C03–C06/Q02–Q06 oracles;
retain all existing canonical checks. Synthetic two-tenant data only; guarded
disposable PostgreSQL, separate owner/runtime connections, no SQLite or skipped
integration suites. Real pinned Chromium over local HTTPS with production
middleware/templates/session resolution; synthetic provider only at its boundary.

| Cases | Boundary and oracle |
| --- | --- |
| CAT-01 reference/migration | Empty and 005 upgrade paths; deterministic seeds; exact ACL/global manifest; source-definition immutability; installed wheel includes 006; provisioning before/after migration idempotent |
| CAT-02 hierarchy/property | Guitar/piano all valid edges and invalid permutations, 3-node maximum, song nonpracticeable, version/fragment practiceable; structurally distinct Songsterr fixture accepted only through policy contract; production disallows Songsterr |
| CAT-03 metadata/property | NFC/code-point lengths, trim, 0/15 levels and out-of-range, boolean/fraction rejection, optional author, fragment null length and default zero notes_count, positive/overflow boundaries, full replacement omission, unknown/nested keys |
| CAT-04 use cases | Direct public calls reject forged actor, enforce owner grant and active parents, catalog/type/source/instrument/version consistency; no untrusted actor factory or hidden provisioning |
| CAT-05 CRUD/API | Full song/version/fragment create/edit/read/move/leaf-tombstone; retained detail; forbidden root/cross-scope moves, active children, restore/cascade/hard-delete absence; exact serialization |
| CAT-06 optimistic races | Barrier-controlled separate runtime transactions: simultaneous writes with same catalog version, create-vs-tombstone, move-vs-tombstone; exactly one valid serialization, rollback leaves no partial bump; distinct stale EV/CV and missing/malformed preconditions |
| CAT-07 tenant/IDOR | Every route/public query/command and private filter against foreign/missing/same-tenant wrong parent IDs; identical safe errors/no-store; unknown mass-assignment at every nesting level; modify tenant/owner/visibility/grants/state/definition/version rejected |
| CAT-08 independent defenses | Runtime missing/wrong context, pool reuse, joins/recursive descendants; mutate explicit predicates while keeping RLS and disable RLS in labelled owner-controlled fixture while preserving predicates; both defenses fail their intended adversarial controls independently |
| CAT-09 search/cursor | Literal percent/underscore/backslash, Unicode/case, each and combined filter, same-name UUID tie, page boundaries/no duplicates without writes, proper descendants, active-only lists, expired/tampered/cross-actor/filter/operation token; no unsigned fallback; bounded queries/size and malformed integer/UUID |
| CAT-10 browser journey | Real login -> catalog -> create guitar/piano tree -> browse/search/breadcrumb -> edit metadata -> move fragment -> tombstone leaf; reload persistence, stale form, pending catalog, empty/error states, labels/keyboard/focus; browser enforces CSP/native forms |
| CAT-11 browser negative | Stored/reflected XSS probes in every name/author/filter/error sink, CSRF/session binding, origin/referer/Fetch Metadata, duplicate JSON/form/query/cookies, streamed oversize, unsupported representations/methods; prove zero mutation on denial |
| CAT-12 compatibility/evidence | Candidate-vs-baseline OpenAPI additive check, exact routes/composition/SQL registrations and mutation tests, source and wheel tests, canonical lint/type/DB/browser suites, telemetry canaries, bounded-query performance against strategy workload |

For races inspect committed owner-visible rows and versions after both sessions
finish; no sleep-only race oracle. Metadata property tests use independent
expected-valid generators plus targeted invalid mutations, not policy code as
its own oracle. Errors with foreign/private inputs must match missing targets
apart from correlation IDs. Owner-only fixture mutations restore and verify
original policies/constraints before the next case. Never run destructive DB
suites concurrently. Preserve exact commit, commands, versions, test counts,
zero-skip status, limitations, reviewer identities and unresolved findings in
verification.md after execution. Independent security, code and evidence reviews
must examine implementation and negative controls, not just this plan.

CAT-13 proposed ADR-013: pinned Chromium/HTTPS must prove native catalog forms
with Origin absent use same-origin Referer, cross-origin receives no Referer,
only exact successful page patterns get the exception, and errors/redirects/
unknown paths retain policy. Positive canaries cover query/Referer at every
enabled application/server/proxy log sink. This new scoped privacy/browser
policy needs explicit owner approval; ADR-012 alone is insufficient.

CAT-14 definition evolution: publish synthetic retained v1/v2 with changed
metadata rules and configured default; existing v1 entries validate under v1,
new roots use v2, children inherit v1, cross-version subtree move fails without
partial change. Both definitions remain immutable. No practice snapshot claim.
CAT-15 persistence seam: source-neutral universal DB constraints plus dispatched
source-specific constraints; actual runtime Songsterr-fixture writes obey its
different graph/depth, invalid edges/metadata rejected, Yousician policy unchanged;
production references/admission never expose Songsterr. Cleanup restores fixture.
CAT-16 interleaving and bounds: READ ONLY REPEATABLE READ ancestry snapshot
against concurrent committed move; timeout/lock exhaustion rolls back every
entry/catalog version change; exact cursor expiry equality, key replacement,
missing-key startup, 2048 encoded/1500 decoded-byte edges; generic failures and
no private queries on failed binding. Candidate response allowlists and negative
schemas are checked independently, including cross-type metadata and precedence.

## Author search amendment — owner request

Text searches entry name OR containing song author. Test a song, its versions
and fragments, null authors, author edits and fragment moves between versions
of different songs. Separate author filter combines with text/source/instrument/
type/ancestry using AND. Verify case/Unicode/literal wildcard behavior, input
bounds, normalized empty inputs, cursor rejection after author filter changes,
and cross-tenant ancestry joins. Browser search covers author-only and combined
filters with escaping and log/referrer canaries. No child author metadata copy.
Focused independent author-amendment review passed before implementation;
implementation evidence is recorded separately.
