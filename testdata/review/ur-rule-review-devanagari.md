# Urdu / اردو — rule review, for a Hindi speaker

Language code `ur` · currently **unreviewed** · 5 rules

**You do not need to read Urdu script.** Every word below is shown twice: as it
appears in the rule, and transliterated into Devanagari. Read the Devanagari.

## Why a Hindi speaker can do this

Hindi and Urdu are the same spoken language written in two scripts. They
diverge in *high-register* vocabulary — Sanskrit-derived on one side,
Persian/Arabic-derived on the other — but the words a scam SMS uses are mostly
neither: English loanwords (OTP, KYC, account) and everyday verbs (send, share,
block).

**Where that argument gets weaker, it is marked.** Words tagged ⚠️ below are
Persian/Arabic-derived and may be unfamiliar or feel wrong to a Hindi speaker
*even when they are correct Urdu*. On those, "I don't know" is a genuinely
useful answer — better than a guess in either direction.

## Two caveats you should know before you start

1. **The transliteration is mine, not a speaker's.** If something reads oddly,
   it may be my transliteration rather than the rule. Both scripts are shown so
   you can flag either.
2. **This cannot make Urdu `in-service`.** A Hindi speaker reviewing Urdu is a
   weaker claim than a native reviewer, and the status table should say so —
   the proposal on #89 is a separate `reviewed-by-proxy` value recording who
   reviewed it and through which language. Nobody should later read this as a
   native review.

> The question is **not** whether the words are grammatical.
> It is whether a **scammer would actually write them** — including
> misspellings, English mixed in, and transliteration, if that is how these
> messages really arrive.

---

## Part 1 — the rules

### otp_share

**Meant to catch:** asks the reader to share / send / tell someone their OTP.

| Urdu | Devanagari | roughly |
|---|---|---|
| `OTP` | `OTP` | English, unchanged |
| `او ٹی پی` | ओ टी पी | "O T P" spelled out |
| `شیئر` | शेयर | share |
| `بھیج` | भेज | send |
| `بتا` / `بتائ` | बता / बताए | tell |

- Would a scammer use these?  ☐ yes  ☐ no  ☐ unsure
- Wrong, odd, or nobody would write:
  
- **Missing** and should be added:
  

### kyc_expiry

**Meant to catch:** claims the reader's KYC is expiring, suspended, or must be updated.

| Urdu | Devanagari | roughly |
|---|---|---|
| `KYC` | `KYC` | English, unchanged |
| `کے وائی سی` | के वाई सी | "K Y C" spelled out |
| `اپ ڈیٹ` | अपडेट | update |
| `میعاد` | मीयाद | term / validity period |
| `ختم` | ख़त्म | finished, ended |
| `بند` | बंद | closed |
| ⚠️ `معطل` | मुअत्तल | suspended |

- Would a scammer use these?  ☐ yes  ☐ no  ☐ unsure
- Wrong, odd, or nobody would write:
  
- **Missing** and should be added:
  

### account_lock

**Meant to catch:** threatens that the reader's account will be locked, blocked or frozen.

| Urdu | Devanagari | roughly |
|---|---|---|
| `اکاؤنٹ` | अकाउंट | account |
| `کھاتہ` | खाता | account (native word) |
| `بلاک` | ब्लॉक | block |
| `بند` | बंद | closed |
| ⚠️ `معطل` | मुअत्तल | suspended |
| ⚠️ `منجمد` | मुंजमिद | frozen |

- Would a scammer use these?  ☐ yes  ☐ no  ☐ unsure
- Wrong, odd, or nobody would write:
  
- **Missing** and should be added:
  

### lottery_win

**Meant to catch:** says the reader has won a lottery, prize or lucky draw.

| Urdu | Devanagari | roughly |
|---|---|---|
| `لاٹری` | लॉटरी | lottery |
| `انعام` | इनाम | prize |
| ⚠️ `قرعہ اندازی` | क़ुरा अंदाज़ी | lucky draw |

- Would a scammer use these?  ☐ yes  ☐ no  ☐ unsure
- Wrong, odd, or nobody would write:
  
- **Missing** and should be added:
  

### urgent_verify

**Meant to catch:** pushes the reader to verify or confirm something immediately.

| Urdu | Devanagari | roughly |
|---|---|---|
| `فوری` | फ़ौरी | immediate |
| `ابھی` | अभी | now |
| `جلد` | जल्द | soon, quickly |
| `ویری فائی` | वेरीफ़ाई | verify (English loan) |
| `تصدیق` | तसदीक़ | confirmation |
| ⚠️ `توثیق` | तौसीक़ | attestation / verification |
| `اپ ڈیٹ` | अपडेट | update |

- Would a scammer use these?  ☐ yes  ☐ no  ☐ unsure
- Wrong, odd, or nobody would write:
  
- **Missing** and should be added:
  

---

## Part 2 — real scam messages

Six to ten if you can, **in Urdu script if possible** — if not, Devanagari or
Roman is still useful and I will note how it was supplied.

These become test cases proving the rules fire, and seed the pattern database,
which for Urdu is currently **empty** — so an Urdu verdict today is the model
guessing with no reference material.

**Remove real phone numbers, links and account numbers** — replace with
`XXXXX`. These files are committed.

| # | The message, as it would arrive | Which rule | Script used |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |
| 6 |  |  |  |
| 7 |  |  |  |
| 8 |  |  |  |
| 9 |  |  |  |
| 10 |  |  |  |

---

## Part 3 — anything else

Scam types common among Urdu speakers that the five rules above miss entirely:



---

Reviewer name: 

Reviewed via: ☐ native Urdu  ☐ Hindi (proxy — see #89)

_Returned to: #89._
