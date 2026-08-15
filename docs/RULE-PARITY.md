# Rule parity — one specification, two engines

> Applies to `backend/app/services/rule_engine.py` and
> `android/core/rules`. Read this before changing either.

---

## 00 · Why this exists

The same rules run in two places: Python on the server, Kotlin on the device.
Two regex implementations of the same rules, in two languages, drift. When they
do, the phone and the server disagree about whether a message is a scam, and
nobody finds out until a user is shown two different answers about the same
text — which, for a product whose entire pitch is trustworthy fraud detection,
is worse than either answer being wrong on its own.

Nothing prevents drift by construction. So it is caught instead.

> `testdata/rule_corpus.jsonl` is the specification. The two engines are
> implementations of it.

---

## 01 · The contract

| | |
|---|---|
| **Specification** | `testdata/rule_corpus.jsonl` |
| **Python implementation** | `backend/app/services/rule_engine.py` |
| **Kotlin implementation** | `android/core/rules/…/RuleEngine.kt` |
| **Python check** | `backend/tests/test_rule_corpus.py`, run by `backend-ci.yml` |
| **Kotlin check** | `android/core/rules/…/RuleCorpusTest.kt`, run by `android-ci.yml` |
| **Field reference** | `testdata/README.md` |

There is no separate parity workflow. Each side is checked by the CI job that
already owns that stack, and both jobs additionally trigger on `testdata/**` —
without that path, editing only the corpus would run neither check, on precisely
the change most likely to break the contract. Neither job uses `|| true`.

Each corpus line is one case. `testdata/README.md` is the field reference; the
short version:

```json
{"id": "en-otp-share-imperative-002", "language": "en", "label": "scam",
 "status": "enforced", "text": "Share your OTP now",
 "expected_rule_ids": ["otp_share"], "source": "handwritten", "note": null}
```

`expected_rule_ids` is matched as an **exact set**, not containment. A rule that
starts firing where it should not is as much a regression as one that stops
firing.

### `status`

- **`enforced`** — the engine must produce exactly `expected_rule_ids`.
- **`known_gap`** — the engine must **not** produce them yet. A documented
  defect with a test pinning it.

`known_gap` is checked **strictly, in both directions, in both suites**. Fix a
gap and the build fails, telling you to change the status. That is the property
that makes the file worth having: closing a gap becomes a visible edit to the
specification instead of a silent behaviour change nobody notices until the
numbers move. Because both engines read the same rows, it also cannot be closed
on the server and left open on the device.

Today's gaps track [#23](https://github.com/CODER7657/raksha-ai/issues/23)
(romanized Hindi, halves in different sentences) and
[#31](https://github.com/CODER7657/raksha-ai/issues/31) (the nine languages with
no rules at all). The #31 rows are that issue's checklist: flip each to
`enforced` as coverage lands.

---

## 02 · Changing a rule

1. **Change the corpus first.** Add or edit the cases that describe the new
   behaviour.
2. Run both suites. They should now fail — if they do not, the case does not
   test what you think.
3. Change **both** engines.
4. Run both suites again.
5. Commit all of it together. A commit that changes one engine without the other
   is the exact failure this document exists to prevent.

Do not edit the corpus to make a failing suite pass. If a suite fails and you
did not intend a behaviour change, the engine regressed.

---

## 03 · Where Python and Java regex disagree

This is the part that bites, and it is subtler than it first appears. Both
directions are pinned by executable assertions in `RegexDialectTest.kt`.

### The flag decision

`RuleEngine.kt` compiles with case-insensitivity **only** — deliberately *not*
with `UNICODE_CHARACTER_CLASS`, which is the opposite of what
[#28](https://github.com/CODER7657/raksha-ai/issues/28) proposed. The reason is
measured:

| Pattern / text | Python | Java default | Java + `UNICODE_CHARACTER_CLASS` |
|---|---|---|---|
| `\bOTP\b\s*\w+` on `OTP शेयर` | match | **no match** | match |
| `\bखाता\b` on `आपका खाता बंद` | no match | no match | **match** |

The first row is the divergence #28 predicted: Java's `\w` is ASCII-only by
default, Python's is Unicode-aware.

The second row is the one that makes the prescribed fix unsafe. `खाता` ends in
`ा` (U+093E), a combining mark. Python's `\w` **excludes** combining marks, so
there is no word boundary after it and the match fails. Java's Unicode `\w`
explicitly **includes** them (`\p{gc=Mn}`), so the boundary exists and it
matches — the opposite answer.

So the flag repairs one divergence and introduces another. It is off because:

- **No rule currently reaches the first row.** The verb stems (`shar\w*`,
  `expir\w*`) only ever extend ASCII words; `\w` is never asked to match a
  non-ASCII character.
- **No Hindi or Gujarati rule contains `\w` or `\b` at all.** They are literal
  alternations plus a negated-class gap, neither of which depends on Unicode
  character classes.

`RegexDialectTest.testNoIndicRuleUsesAWordClassOrBoundary` asserts that second
point. If it fails, someone added `\w` or `\b` to a non-English rule, the choice
above is now live, and it has to be made on purpose.

> **Note for #28:** its acceptance criterion "add a corpus case per script that
> would fail if the Unicode flag were missing" cannot be satisfied as written.
> No such case exists, because the Indic rules use no word classes. The property
> is asserted directly against the regex engine instead, which is where it
> actually lives.

### Also worth knowing

- `re.IGNORECASE` is Unicode-aware; Java's `CASE_INSENSITIVE` is ASCII-only
  unless paired with `UNICODE_CASE`. Irrelevant for Devanagari and Gujarati,
  which are caseless, but it would matter for a Latin-script language with
  diacritics.
- The gap `[^.!?\n]{0,40}?` behaves identically in both, but counts **characters**,
  and Indic combining marks each consume one. A Devanagari phrase reaches the
  40-character limit sooner than its English equivalent looks like it should.

---

## 04 · Deliberately not covered

- **Performance on real hardware.** `RuleLatencyTest` runs on the JVM on desktop
  or CI hardware. It catches the regression that matters — rebuilding `Regex`
  objects per message instead of once — but a pass does not prove the ~200ms
  on-device budget. That needs the Macrobenchmark in
  [#29](https://github.com/CODER7657/raksha-ai/issues/29) §8.
- **Accuracy.** The corpus proves the two engines agree. It says nothing about
  whether the rules are *correct* — that is the labelled benchmark, still open.
  Two engines agreeing on a wrong answer will pass everything here.
