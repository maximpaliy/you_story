# Minimal Yousician content schema — owner direction

Status: owner-supplied shape; validation details and independent re-review pending.
This supplements authorization-spec.md, not a bulk-create endpoint contract.

## Owner approval — fragment availability rules

The owner explicitly approved the following fragment rules in this conversation:

- length_seconds is optional until measured; null represents unknown and a
  supplied measurement is a positive integer.
- notes_count is a nonnegative integer with creation default 0; zero can mean
  not yet known, rather than a verified absence of musical notes.
- These are catalog metadata fields, separate from practice duration and
  recorded statistics, and can be filled in later through authorized updates.

This approval is specific to these rules. It does not close Issue #8, supply
unsettled integer upper bounds/author requiredness, or replace independent
re-review of the completed source contract.

The owner specified Song -> Version -> Fragment, with author stored on Song for
now. Author is not yet a separate parent/entity. Future type (chords/melody/
fingerpicking), tuning, capo and chords/progressions are outside this minimum.
Do not accept arbitrary metadata keys in anticipation of them.

| Node | Common field | Source metadata | Parent |
| --- | --- | --- | --- |
| Song | name: string | author: string | Catalog root |
| Version | name: string | level: integer, inclusive 0–15 supported range | Song |
| Fragment | name: string | length_seconds: optional positive integer; notes_count: nonnegative integer, creation default 0 | Version |

Names use the owner-agreed 1–200 Unicode-code-point limit after NFC normalization,
enforced consistently in application and database validation, not as a byte limit.
Increasing the limit later requires coordinated validation/constraint changes,
not truncation or identifier changes. Author requirement and fragment integer
upper bounds still need a concrete contract.
The author's earlier optional-field proposal is not treated as owner approval.
The owner clarified that `notes_count` is the integer count of musical notes
in the fragment. It is not a free-text comment field. Fragment content
length is separate from elapsed practice-record duration and does not require
those durations to match.

The owner clarified that Yousician does not provide fragment length: it must be
measured. Therefore length_seconds may be omitted initially. Proposed canonical
unknown representation is null; a supplied measurement must be strictly positive.
Do not substitute 0 or infer length from practice duration. As part of an active
entry metadata update, null clears the measurement.

Yousician provides the note count only after the fragment has been played, so
notes_count accepts an initial 0 and defaults to 0 on creation when omitted.
Zero may therefore mean not yet known; it must not be advertised as a verified
zero-note fragment. No separate known/unknown flag is introduced in this MVP
shape. A later catalog metadata update can supply the measured length and
observed count under normal active-entry authorization/version checks. This
does not mutate prior practice snapshots or recorded statistic values.
On full metadata replacement, notes_count must be explicit to avoid accidentally
resetting an existing observed count to the creation default. Unknown keys and
noninteger values (including booleans) remain rejected.

Illustrative nested representation, preserving the owner's field types:

```json
{
  "name": "Example song",
  "author": "Example author",
  "versions": [
    {
      "level": 8,
      "name": "Example version",
      "fragments": [
        {
          "name": "Example fragment",
          "length_seconds": 30,
          "notes_count": 12
        }
      ]
    }
  ]
}
```

The sample numeric values illustrate types, not settled bounds. Nested arrays represent relationships between separately addressable
entries, not permission to mass-assign an entire tree. Existing per-entry
commands and authorized parent resolution still apply.

No canonical author identity, automatic author promotion or new author query
filter is approved by this shape alone. Future author entities/grouping require
explicit policy and migration design. Snapshot attribution and fragment metadata
capture must be reconciled explicitly with the approved snapshot contract during
review; no historical snapshot rewrite follows from these new fields.

Before marking the source-schema blocker resolved, select exact
requiredness/bounds for source fields, then update source validation cases and
obtain focused independent re-review. Later extensions may add reviewed schema
versions without silently altering stored entry interpretation.
