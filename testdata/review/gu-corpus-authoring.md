# Gujarati corpus — writing the rows

For the one Gujarati speaker on this team. This is authoring, not reviewing:
the eight-row fixture set A1 is currently measured against was written to
exercise the scorer, so the loop is being graded on material designed to grade
it. Real Gujarati messages are what break that circle.

## Before anything else — the honest caveat this carries

You are **author and reviewer of the same rows**. That is unavoidable and it is
being recorded rather than absorbed: every row you write gets
`source: "handwritten"` and `authored_and_reviewed_by_same_person: true`, and
`docs/RULE-PARITY.md` will say so beside `gu: in-service`.

The repo rule is that nobody marks their own work done. This is the one place it
cannot be satisfied, and naming the exception is what keeps it an exception
rather than a precedent.

---

## What I need from you

Two lists of real Gujarati SMS text. Write them in whatever form is easiest —
a message, a note, plain text — and I will turn them into corpus rows, assign
ids, and run them against the engine.

### List 1 — SCAM messages

What a real Gujarati scam SMS actually says. For each, tell me which of these it
is trying to do:

| rule id | the scam |
|---|---|
| `otp_share` | asks the reader to share / send / tell their OTP |
| `kyc_expiry` | claims KYC is expiring, suspended, or must be updated |
| `account_lock` | threatens the account will be locked, blocked or frozen |
| `lottery_win` | claims a prize, lottery or lucky draw win |
| `urgent_verify` | demands verification right now, today, within N hours |

One message can hit more than one — a KYC threat with a deadline is both
`kyc_expiry` and `urgent_verify`.

**Write them the way they arrive, not the way they should be written.**
Misspellings, English words in Latin script mid-sentence (`KYC`, `OTP`, `bank`),
transliterated Gujarati, missing punctuation — all of that is the real data.
A grammatically clean invented sentence tests nothing.

Both scripts matter:
- **Gujarati script** — `તમારું KYC આજે સમાપ્ત થઈ જશે`
- **Transliterated** — `tamaru KYC aaje samapt thai jashe`

The second is how a great many people actually type, and the rules currently
lean on the English fallback to catch it.

### List 2 — BENIGN messages, and this list must be LONGER

Real Gujarati messages that must **never** be flagged. This is the half that
costs users: a blocked genuine bank message during a fraud alert is us causing
the harm the product exists to prevent.

The valuable ones are the messages that *look* like the scams above:

- A real bank OTP: *"your OTP is 452189, do not share it with anyone"* — contains
  OTP **and** the word share, and is completely legitimate
- A real KYC reminder from a bank you actually hold an account with
- A genuine delivery, appointment or payment confirmation
- A real bank warning about fraud, which will use every scam word there is
- Anything with a deadline that is not a threat — bill due, offer ends

Anyone can write ten scam messages. Twenty benign ones our own rules find
suspicious is the work, and it is what makes the precision number mean anything.

---

## What happens to them

1. I turn each into a corpus row and run it through `offline_rule_hits`
2. Any scam row nothing fires on is a **rule gap** — a real finding, and the
   point of the exercise
3. Any benign row that fires is a **false positive** — a bigger finding
4. Both get reported per-slice, never aggregated
5. Rows land in `testdata/rule_corpus.jsonl`, which both the Python and Kotlin
   engines are held to

You do not need to get the labels right on the first pass. Send the messages and
I will show you what fires; where the engine disagrees with you, you are the one
who is right about Gujarati and the rule is what changes.

---

## The shape a row ends up in

You do not write this — it is here so you can see where your text goes.

```json
{
  "id": "gu-kyc-003",
  "language": "gu",
  "label": "scam",
  "status": "enforced",
  "text": "તમારું KYC આજે સમાપ્ત થઈ જશે, તરત જ અપડેટ કરો",
  "expected_rule_ids": ["kyc_expiry", "urgent_verify"],
  "source": "handwritten",
  "note": "Gujarati script with a Latin-script KYC token, which is how it is normally written."
}
```

## How many

No target, deliberately — a number invites padding, and a padded corpus is worse
than a small honest one because it makes the coverage look established.

Ten scam and twenty benign would roughly double what `gu` has today and is
enough to find real gaps. Five and ten is still worth doing. Send what you can
vouch for and stop there.
