# Gujarati corpus — machine drafts for review

**Drafted by a machine, reviewed by a speaker.** Rows accepted here land with
`provenance: "agent"` and `drafted_by: "claude"`, never `handwritten` — #79 added
those fields so a reviewer, and eventually an auditor, can tell which evidence
behind a verdict was machine-drafted.

## What I am asking you to check, and what I cannot check myself

I can write grammatical Gujarati. I cannot tell you:

1. Whether it reads **naturally** or like a translation
2. Whether a **scammer would actually write it** — the judgement the whole
   exercise turns on
3. Whether the **register** is right: scam SMS is blunt and slightly wrong, not
   well-formed

So the useful answer on any row is often "no" or "not like that". A sheet that
comes back all-accepted is the result to look at twice.

Mark each row: **✅ keep** · **✏️ fix** (write what it should say) · **❌ drop**

---

## Part 1 — SCAM drafts (10)

| # | Gujarati | roughly | should fire |
|---|---|---|---|
| S1 | તમારું KYC આજે સમાપ્ત થઈ રહ્યું છે, તાત્કાલિક અપડેટ કરો નહીં તો ખાતું બંધ થઈ જશે | Your KYC expires today, update immediately or the account will close | `kyc_expiry` `urgent_verify` `account_lock` |
| S2 | તમારો OTP તરત જ શેર કરો, હું બેંકમાંથી બોલું છું | Share your OTP at once, I'm calling from the bank | `otp_share` |
| S3 | tamaru account block thai gayu che, ahi click karo | your account is blocked, click here | `account_lock` |
| S4 | અભિનંદન! તમે ૨૫ લાખ રૂપિયાની લોટરી જીતી છે | Congratulations! You've won a 25 lakh lottery | `lottery_win` |
| S5 | તમારું ATM કાર્ડ બ્લોક થઈ ગયું છે. ૨૪ કલાકમાં વેરિફાય કરો | Your ATM card is blocked. Verify within 24 hours | `account_lock` `urgent_verify` |
| S6 | KYC update karva mate aa link par click karo, nahi to account band thai jashe | Click this link to update KYC, or the account will close | `kyc_expiry` `account_lock` |
| S7 | તમારા ખાતામાં શંકાસ્પદ વ્યવહાર થયો છે, OTP કહો | Suspicious transaction on your account, tell me the OTP | `otp_share` |
| S8 | છેલ્લી તક! આજે જ કેવાયસી પૂર્ણ કરો | Last chance! Complete KYC today | `kyc_expiry` `urgent_verify` |
| S9 | તમે લકી ડ્રોમાં કાર જીતી છે, પ્રોસેસિંગ ફી ભરો | You've won a car in the lucky draw, pay the processing fee | `lottery_win` |
| S10 | તાત્કાલિક વેરિફિકેશન જરૂરી છે, અન્યથા સેવા બંધ કરવામાં આવશે | Immediate verification required, otherwise service will be stopped | `urgent_verify` |

**Specifically unsure about:** S2's `હું બેંકમાંથી બોલું છું` — that is spoken
register in a text message and may be wrong. S10 reads formal and bureaucratic;
real scam SMS may be blunter.

---

## Part 2 — BENIGN drafts (20)

Longer than the scam half on purpose. These are the ones that cost users: a
blocked genuine bank message during a fraud alert is us causing the harm.

**Rows B1, B5, B9 and B20 are the important ones** — each contains scam
vocabulary and is completely legitimate.

| # | Gujarati | roughly | why it is hard |
|---|---|---|---|
| B1 | તમારો OTP 452189 છે. કોઈની સાથે શેર કરશો નહીં. | Your OTP is 452189. Do not share with anyone. | **OTP + share, entirely legitimate** |
| B2 | HDFC બેંક: તમારા ખાતામાંથી ₹૨,૫૦૦ ઉપડ્યા છે. બેલેન્સ ₹૧૨,૩૪૦ | ₹2,500 debited. Balance ₹12,340 | routine alert |
| B3 | તમારું વીજળી બિલ ₹૮૫૦ ૧૫ તારીખ સુધીમાં ભરો | Pay your ₹850 electricity bill by the 15th | deadline, not a threat |
| B4 | તમારી ટ્રેન ટિકિટ કન્ફર્મ થઈ છે, PNR 2745891 | Train ticket confirmed | — |
| B5 | બેંક ક્યારેય OTP કે PIN માંગતી નથી. કોઈને ન આપો. | The bank never asks for OTP or PIN. Give it to no one. | **a fraud warning, uses every scam word** |
| B6 | તમારો ગેસ સિલિન્ડર આવતીકાલે ડિલિવર થશે | Gas cylinder delivers tomorrow | — |
| B7 | ડૉક્ટરની એપોઇન્ટમેન્ટ કાલે સવારે ૧૦ વાગ્યે | Doctor's appointment tomorrow 10am | — |
| B8 | તમારા ખાતામાં ₹૫,૦૦૦ જમા થયા છે | ₹5,000 credited to your account | — |
| B9 | તમારું KYC સફળતાપૂર્વક પૂર્ણ થયું છે. કોઈ કાર્યવાહી જરૂરી નથી. | Your KYC completed successfully. No action needed. | **KYC, and benign** |
| B10 | આજે ઓફર પૂરી થાય છે, ૫૦% ડિસ્કાઉન્ટ | Offer ends today, 50% off | urgency, not a threat |
| B11 | Recharge safal thayo. Balance ₹247. | Recharge successful | transliterated benign |
| B12 | તમારી બેંક શાખા સોમવારે રજા રહેશે | Your branch is closed Monday | — |
| B13 | LPG સબસિડી ₹૩૦૦ તમારા ખાતામાં જમા થઈ | LPG subsidy ₹300 credited | — |
| B14 | તમારું ક્રેડિટ કાર્ડ બિલ ₹૪,૨૦૦ ૨૦ તારીખે ડ્યુ છે | Credit card bill ₹4,200 due on the 20th | deadline |
| B15 | Aaje tamari appointment 3 vagye che | Your appointment is at 3 today | transliterated benign |
| B16 | તમારો પાર્સલ ડિલિવરી માટે નીકળી ગયો છે | Parcel out for delivery | — |
| B17 | શાળામાં કાલે વાલી મીટિંગ છે | Parents' meeting at school tomorrow | — |
| B18 | તમારી FD ૧૫ તારીખે પાકે છે, રિન્યુ કરવા શાખાની મુલાકાત લો | FD matures on the 15th, visit the branch to renew | deadline + "visit branch" |
| B19 | વીમા પ્રીમિયમ ₹૩,૫૦૦ ભરવાનું બાકી છે | Insurance premium ₹3,500 pending | — |
| B20 | બેંક તરફથી ચેતવણી: KYC અપડેટની લિંક પર ક્લિક ન કરો | Bank warning: do not click KYC update links | **a warning about the scam, contains KYC + link** |

**Specifically unsure about:** B13 — whether LPG subsidy SMS actually arrives in
Gujarati or only English. B18's `પાકે છે` for a maturing deposit may be wrong.

---

## What happens next

Send back the marks. Then I:

1. Run every accepted row through `offline_rule_hits`
2. Report **scam rows nothing fires on** — real rule gaps, the point of this
3. Report **benign rows that fire** — false positives, the bigger finding
4. Land them in `rule_corpus.jsonl` with `provenance: agent`, `drafted_by: claude`
   and your acceptance recorded

Where the engine disagrees with you, you are right about Gujarati and the rule
is what changes.
