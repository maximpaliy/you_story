# Minimal Yousician content schema — owner direction

Status: focused architecture, security and test-design reviews passed;
new engineering defaults remain separately identified for final acceptance.
This supplements authorization-spec.md, not a bulk-create endpoint contract.

## Owner approval — fragment availability rules

The owner explicitly approved the following fragment rules in this conversation:

- length_seconds is optional until measured; null represents unknown and a
  supplied measurement is a positive integer.
- notes_count is a nonnegative integer with creation default 0; zero can mean
  not yet known, rather than a verified absence of musical notes.
- These are catalog metadata fields, separate from practice duration and
  recorded statistics, and can be filled in later through authorized updates.

The owner subsequently approved the discussed design direction and requested
independent review. The small validation defaults below are editorial/engineering
defaults, not additional claims of explicit product approval. Review must verify
that they preserve the discussed behavior before recommending issue closure.

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
not truncation or identifier changes. Concrete engineering defaults: author is optional/null; when supplied it is
NFC-normalized, trimmed nonempty plain text of at most 200 code points.
length_seconds is null or an integer in 1–2147483647; notes_count is an integer
in 0–2147483647, never null. Reject booleans, fractions and overflow. These
representational bounds are not a claim of Yousician product maxima.
The owner clarified that `notes_count` is the integer count of musical notes
in the fragment. It is not a free-text comment field. Fragment content
length is separate from elapsed practice-record duration and does not require
those durations to match.

The owner clarified that Yousician does not provide fragment length: it must be
measured. Therefore length_seconds may be omitted initially. Canonical
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

The sample numeric values illustrate valid values within the above bounds. Nested arrays represent relationships between separately addressable
entries, not permission to mass-assign an entire tree. Existing per-entry
commands and authorized parent resolution still apply.

No canonical author identity, automatic author promotion or new author query
filter is approved by this shape alone. Future author entities/grouping require
explicit policy and migration design. Snapshot attribution and fragment metadata
capture must be reconciled explicitly with the approved snapshot contract during
review; no historical snapshot rewrite follows from these new fields.

## Exact per-node metadata and replacement rules

- Song: only author; omitted on creation becomes null. A metadata replacement
  must explicitly include author (string or null), preventing accidental erasure.
- Version: only level; required integer 0–15 on create and replacement.
- Fragment: only length_seconds and notes_count. Creation defaults omitted
  length_seconds to null and notes_count to 0. Replacement requires both keys,
  with the same value/null rules, so omission never silently clears measured data.
- Common name is required on entry creation and non-null when updated. Common
  source/instrument/type/parent fields remain outside metadata under C03–C05.
- Reject all other metadata keys. Guitar/piano use song root -> version ->
  fragment with a maximum ancestry depth of three nodes. Initial configured
  practiceable types are version and fragment; song is navigation/grouping only.
  This practiceability choice is an engineering proposal requiring review, not a
  previously explicit owner decision; no record may bypass the published policy.
- Common optional notes/comments remain separate from integer notes_count;
  this source schema introduces no free-text fragment-notes key.

No author/fragment metadata is added to historical snapshots by this schema.
Retain the approved minimal source/instrument/ancestor/type/name snapshot and
immutable definition eligibility binding; these source fields are live catalog
metadata only. Future attribution/history requirements need explicit review.

Later extensions may add reviewed schema versions without silently altering
stored entry interpretation. Focused independent reviews passed this contract; its prior missing-source-schema
design blocker is resolved. Runtime enforcement remains unverified.
