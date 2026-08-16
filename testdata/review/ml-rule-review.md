# Malayalam / മലയാളം — rule review

Language code `ml` · currently **unreviewed** · 5 rules

You are the reviewer this asks for. Nobody who speaks this language has
read these rules — they were written from a concept list, which makes them
a guess until you say otherwise.

**You do not need to read any code.** Each section gives you the words the
detector currently looks for, and what it is trying to catch. Answer in
the space provided, in whatever form is easiest.

> The question is **not** whether the words are grammatical.
> It is whether they are what a *scammer would actually write* — including
> misspellings, English words mixed in, and transliteration, if that is how
> these messages really arrive.

---

## Part 1 — the rules

### otp_share

**Meant to catch:** Asks the reader to share / send / tell someone their OTP.

**Words it currently looks for:**

```
OTP   അയക്ക   അയയ്   അറിയിക്ക   ഒടിപി   പങ്കിട   പറയ
```

- Are these the words a scammer would use?  ☐ yes  ☐ no
- Anything here that is wrong, odd, or nobody would write:
  
- Words that are **missing** and should be added:
  

### kyc_expiry

**Meant to catch:** Claims the reader's KYC is expiring, suspended or must be updated.

**Words it currently looks for:**

```
KYC   അപ്ഡേറ്റ്   കാലാവധി   കെവൈസി   നിർത്ത   റദ്ദ
```

- Are these the words a scammer would use?  ☐ yes  ☐ no
- Anything here that is wrong, odd, or nobody would write:
  
- Words that are **missing** and should be added:
  

### account_lock

**Meant to catch:** Threatens that the reader's account will be locked, blocked or frozen.

**Words it currently looks for:**

```
അക്കൌണ്ട്   അക്കൗണ്ട്   അടയ്ക്ക   നിർത്ത   ബ്ലോക്ക്   മരവിപ്പിക്ക
```

- Are these the words a scammer would use?  ☐ yes  ☐ no
- Anything here that is wrong, odd, or nobody would write:
  
- Words that are **missing** and should be added:
  

### lottery_win

**Meant to catch:** Says the reader has won a lottery, prize or lucky draw.

**Words it currently looks for:**

```
ഭാഗ്യ നറുക്ക്   ലോട്ടറി   സമ്മാനം
```

- Are these the words a scammer would use?  ☐ yes  ☐ no
- Anything here that is wrong, odd, or nobody would write:
  
- Words that are **missing** and should be added:
  

### urgent_verify

**Meant to catch:** Pushes the reader to verify or confirm something immediately.

**Words it currently looks for:**

```
അടിയന്തിര   അപ്ഡേറ്റ്   ഉടനടി   ഉടൻ   പരിശോധിക്ക   സ്ഥിരീകരിക്ക
```

- Are these the words a scammer would use?  ☐ yes  ☐ no
- Anything here that is wrong, odd, or nobody would write:
  
- Words that are **missing** and should be added:
  

---

## Part 2 — real scam messages

Six to ten if you can. These do two jobs: they become test cases proving
the rules fire, and they seed the pattern database the AI compares
against — which for this language is currently **empty**, so verdicts here
are the model guessing unaided.

Best are messages you or someone you know actually received. Invented ones
are still far better than nothing, as long as they are how these really
sound.

**Please remove real phone numbers, links and account numbers** — replace
with `XXXXX`. Nothing here should identify anyone.

Spread them across these if you can: OTP request · KYC expiry · account
lock · lottery win · refund link · urgent verification.

| # | The message, as it would arrive | Which of the six above |
|---|---|---|
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |
| 4 |  |  |
| 5 |  |  |
| 6 |  |  |
| 7 |  |  |
| 8 |  |  |
| 9 |  |  |
| 10 |  |  |

---

## Part 3 — anything else

Scam types common for speakers of this language that the six categories
above miss entirely:


---

Reviewer name (so the table can credit who read it): 

_Returned to: #89. One PR per language._
