# Shared test corpus

`rule_corpus.jsonl` is the **specification** for the offline rule engine. The
Python implementation in `backend/app/services/rule_engine.py` and the Kotlin
port planned in #28 are both implementations of it, and both must reproduce it.

It lives at the repository root rather than under `backend/` deliberately: the
moment it belongs to one implementation, the other one's disagreements start
looking like that implementation's business.

## Why this file exists

Two engines written from the same description will drift. When they do, the phone
and the server disagree about whether a message is a scam, and nobody finds out
until a user is shown two different answers for the same text. A shared corpus
turns that from a discovery into a test failure.

## Format

One JSON object per line, UTF-8, no trailing commas.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable, unique, kebab-case. Referenced from issues and commits, so do not renumber. |
| `language` | string | One of the twelve codes in `LanguageCode` (`backend/app/routes/scan.py`). |
| `label` | `"scam"` \| `"benign"` | Ground truth about the message, independent of what any rule does. Used by the verdict-level benchmark. |
| `status` | `"enforced"` \| `"known_gap"` | Whether the engine is expected to reproduce `expected_rule_ids` **today**. See below. |
| `text` | string | The message, verbatim. |
| `expected_rule_ids` | string[] | The rule ids that *should* fire. Empty for benign cases. |
| `source` | string | Where it came from: `handwritten`, `review:#18`, `issue:#23`, and so on. |
| `note` | string \| null | Why this case exists. Write it for anything non-obvious — the note is what stops a future reader from "fixing" a deliberate choice. |

## `status` is the important field

- **`enforced`** — the engine must produce exactly `expected_rule_ids`. A mismatch
  fails the build.
- **`known_gap`** — the engine **must not** produce `expected_rule_ids` yet. This
  is a documented defect with a test pinning it.

`known_gap` is checked strictly, in both directions. If you fix a gap, the test
fails and tells you to change the status to `enforced`. That is intentional:
closing a gap should be a visible, deliberate edit to this file, not a silent
change in behaviour that nobody notices until the numbers move.

## Adding cases

1. Add the row with your best expectation of `expected_rule_ids`.
2. Run `pytest backend/tests/test_rule_corpus.py -q`.
3. If it passes as written, mark it `enforced`. If the engine disagrees and the
   engine is *wrong*, mark it `known_gap` and open an issue.

Never edit a case to match what the engine happens to do. The corpus describes
what should happen; the engine is what might be wrong.

## Rule ids

Concept-level and shared across languages — the Hindi and English "share your
OTP" rules are the same `otp_share`. The ids are also i18n keys: the frontend
renders `trace.rules.<rule_id>` (#19), and the Kotlin port will key off the same
strings. **A new language must reuse the existing ids, not invent new ones.**

Current ids: `otp_share`, `kyc_expiry`, `account_lock`, `lottery_win`,
`refund_click`, `urgent_verify`.

## Coverage today

`RULES` covers `en`, `hi`, `gu`. The other nine languages have no rules at all
and fall through to English patterns — see #31, which is why several rows here
are `known_gap` with a language code as the only reason.
