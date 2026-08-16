# Language review sheets

One sheet per unreviewed language, for #89 and the seeding half of #88.

## Why these exist

Eight of the twelve languages we advertise have detection rules **no speaker of
that language has read**. `docs/RULE-PARITY.md` §02b is blunt about what that
means: a rule nobody who speaks the language has read is a guess, and a guessed
rule that never fires is invisible. That is exactly how nine languages shipped
with no coverage at all before #31.

The blocker was never that nobody would review. It was that the thing to review
looked like this:

```
(?:(?:ஓடிபி|OTP)[^.!?\n]{0,40}?(?:பகிர|அனுப்ப|சொல்ல|தெரிவி)|…
```

Nobody should have to parse that to answer "would a scammer write these words?".
Each sheet extracts the vocabulary, states what the rule is trying to catch, and
asks questions a speaker can answer without reading code.

## The rule that governs all of this

**A speaker fills these in, not a translation tool.**

Running the English through a translator and pasting the output back defeats the
entire purpose — it produces exactly the plausible-looking guess these sheets
exist to replace, and it would then carry a reviewer's name. A pattern written
by someone who does not speak the language is a guess that gets treated as
evidence, and a wrong one teaches the classifier wrong, silently, for every user
in that language.

If no speaker is available for a language, it stays `unreviewed`. That is an
honest state. A falsely-`in-service` entry is not.

## What comes back, and what happens to it

A completed sheet gives three things:

1. **Verdict on the vocabulary** — which words are wrong, which are missing
2. **Six to ten real scam messages** — these become corpus rows proving the
   rules fire, and seed the pattern database, which for these languages is
   currently empty (#88)
3. **Scam types the six categories miss** — the part no amount of translation
   would have surfaced

From that, one PR per language, as #89 asks:

- rule vocabulary updated from the verdict
- corpus rows added from the messages
- `REVIEW_STATUS` flipped `unreviewed` → `in-service`, **in the same PR** so the
  table and the evidence move together
- both parity suites run, since `testdata/**` triggers the Python and Kotlin
  halves

## Order

`ta`, `te`, `bn` first — largest speaker populations among the eight, so the
same effort protects more people.

`ur` has a second sheet, `ur-rule-review-devanagari.md`, for a **Hindi
speaker**. Hindi and Urdu are the same spoken language in two scripts, and scam
vocabulary is mostly English loanwords and everyday verbs rather than the
high-register words where the two diverge — so a Hindi speaker can judge most
of it from a transliteration.

Most, not all. Extracting the vocabulary showed five words that *are*
Persian/Arabic-derived — `معطل`, `منجمد`, `توثیق`, `قرعہ اندازی` — and the sheet
marks them, because a Hindi speaker may find them unfamiliar even when they are
correct Urdu. On those, "unsure" is a more useful answer than a guess.

That review cannot make `ur` `in-service`. It is a weaker claim than a native
reviewer and the table should say so — #89 proposes a separate
`reviewed-by-proxy` value recording who reviewed it and through which language.

RTL rendering is separately verified (computed `direction: rtl`, checked in #67
and #75), so what is open for `ur` is vocabulary, not layout.

`mr` is deliberately absent. It is `inherited` rather than `unreviewed` — it
borrows Hindi's rules because the vocabulary genuinely overlaps. Worth a
Marathi speaker confirming eventually, but it is a different claim from the
eight here.

## Privacy

The sheets ask for real messages with phone numbers, links and account numbers
replaced by `XXXXX`. Nothing that reaches this directory should identify anyone
— these files are committed, and the corpus rows built from them ship in the
repository.
