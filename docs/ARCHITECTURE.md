# Raksha AI — System Architecture (V2)

> Status: deployed, pre-pilot · Processing: edge-first · Repo: private
>
> Read this before writing code. The design changed direction after the jury
> round, and work built against the V1 model will be rejected in review.

---

## 00 · The critique that reframed the product

A jury member asked the question that mattered: *if a scammer is on the call
right now, how does your website help? By the time they open it, the money is
gone.*

That is not a UX complaint — it invalidates the delivery model.

V1 was a **pull** system. It required the victim to already suspect they were
being scammed, then stop, open an app, paste a message and read a verdict. But a
scam that is working does not feel like a scam. Suspicion arriving in time is
precisely the thing the fraudster is engineering away.

> A tool that waits to be consulted protects only people who were already
> suspicious — the ones least likely to be defrauded. **V2 stops waiting.**

Everything below follows from one inversion: the system observes the channels
fraud actually arrives through, and interrupts. The website becomes the
dashboard, not the product.

---

## 01 · Interception model

Fraud is a sequence, not an event. Each stage is a chance to intervene, and the
value of intervening rises as the money gets closer — while the odds of the
victim *acting* on a warning fall, because by then they are being actively
coached not to believe it.

```
Contact  ──▶  Trust  ──▶  Pressure  ──▶  Action  ──▶  LOSS
call/SMS      imperson.    urgency       OTP/PIN      money moves
   │             │            │             │
   ▼             ▼            ▼             ▼
 [1][2]         [3]          [4]           [5]
```

| # | Layer | What it does | Status |
|---|---|---|---|
| 1 | **Number reputation** | Check an incoming call against numbers **this phone** has already flagged — a number is known because an SMS it sent here tripped the on-device rules. Cheapest signal, weakest evidence: numbers are disposable, and it knows nothing about a caller who has not texted first. | ✅ **Built** — #133 |
| 2 | **SMS auto-scan** | Android reads incoming SMS, scores on-device, raises a notification. **Zero user action.** Highest-value quick win: phishing SMS is the most common vector. | ✅ **Built** — #38, hardened #86/#93 |
| 3 | **Call screening** | `CallScreeningService` sees an unknown number pre-answer and posts a warning. Native Android, no recording, and the call is never rejected, silenced or logged differently. Needs API 30+ and a role the user grants. | ✅ **Built** — #133 |
| 4 | **Live call analysis** | Streaming transcription during the call, detecting authority claims, urgency and OTP requests, with a persistent warning. Highest impact, hardest to build; Android restricts third-party call audio and recording-consent law varies by state. | ❌ Not built |
| 5 | **Payment interrupt** | Accessibility service watches UPI apps. Payment about to leave for a flagged VPA → full-screen interrupt. | ❌ **Not built** — and the thesis rests on it |

### What the phone can actually do today

**Three layers of five, and every detector on them is the same rule engine.**

Layers 1 and 3 arrived together in #133 and they are narrower than the table
alone suggests. Both are worth stating here, because the gap between "built" and
"protects someone" is where this document has been wrong before:

- **Layer 3 needs API 30+.** `CallScreeningService` dates from API 24, but a
  non-dialer app cannot hold the screening role until `RoleManager` at 29, and
  the floor was set at 30. On a phone below that the app says so rather than
  offering a switch that does nothing. `minSdk` is still 24, so some of the
  handsets §02 designs for get layers 2 and 5 and not layer 3.

  **29 was measured and is closed.** It looked like a free widening — the role
  exists there, and it reaches more cheap handsets. It is not. On an API 29
  image the platform binds the screening service for a number in the user's own
  contacts, which API 36 does not, and there is no `getContactDisplayName` at 29
  to catch it: same number, same flagged message, contact status the only
  variable, and 29 warned about a saved contact while 36 was never called at
  all. Widening the floor would ship a false positive about the people a user
  deliberately saved, to the population least able to absorb one.
- **Layer 1 is empty on a new install**, and fills only when a number sends a
  scam SMS to *this* handset. It protects against the second contact from a
  number, never the first. That is the honest shape of the cheapest signal.

The Android client still declares exactly two permissions — `RECEIVE_SMS` and
`POST_NOTIFICATIONS` — and **no `INTERNET`**. Layer 3 added none: the screening
role is granted by the user through a system dialog rather than declared here,
which is why it could ship while `RECEIVE_SMS` sat in Play's queue. It has no
HTTP library. So the device cannot reach the backend at all, which means
on-device detection is the regex rule engine and nothing else: no retrieval, no
model, no cloud escalation.

The "On-device model" box in the diagram below is `RuleEngine.kt`, six rule
concepts, pattern matching. **There is no model on the device.** That is a
deliberate consequence of the privacy posture rather than an oversight — nothing
leaves the phone because nothing can — but it is not what the box says.

Everything else a user can do (text scan, voice scan, UPI check, chat, practice)
lives on the **website** and requires them to already suspect something. That is
the pull model §00 says V2 stops waiting on. The phone now carries three of the
five layers; the website still carries everything else.

Stated plainly because the gap is easy to miss from the diagrams, and because
the honest version is still strong: three interception layers working end to end
on-device, with nothing leaving the phone, is a real thing. Claiming five is what
would cost us — and so is letting "built" stand in for "reaches everyone", which
is why the two limits above are in this section rather than a commit message.

**Design principle.** A scam does not fail when it is detected. It fails when the
money stops. Layers 1–4 are advisory; only layer 5 is terminal. Build it assuming
the other four will sometimes be ignored.

---

## 02 · Edge-first architecture

Two objections were raised in review, and one decision answers both:

1. A cloud round trip is too slow when someone is mid-call.
2. *"Why would HDFC put their customers' messages on your cloud?"*

Move detection onto the device and the message never leaves the phone: no
latency, and nothing for an institution to trust us with.

```
ON DEVICE  (no message leaves the phone)
  SMS listener ┐
  Call screener├─▶ Rule engine (zero network) ─▶ On-device model ─▶ Interrupt
  UPI watcher  ┘                                        │
                                                        │ uncertain only
CLOUD  (patterns and intelligence, never raw content)   ▼
  Pattern sync ──▶ (signed bundles, pulled by device)
  RAG escalation ◀─ opt-in, ambiguous cases only
  Aggregate intelligence ◀─ SHA-256 hashes only ──▶ Institution dashboard
```

| Concern | Placement | Rationale |
|---|---|---|
| Rule engine | Device | Must answer with no network. Already built. |
| Classifier | Device | Latency and privacy. Quantised, updated via signed bundles. |
| Scam patterns | Synced to device | Read-only bundle. Device pulls; server never pushes content. |
| Ambiguous cases | Cloud, opt-in | Escalate only when on-device confidence is low **and** user consents. |
| Community counts | Cloud | Hashed digests, never raw text — already how V1 works. |
| Institution dashboard | Cloud | Aggregates only; no individual message reconstructable. |

> The cloud learns that a scam pattern is spreading in a district. It never
> learns what any individual person received.

---

## 03 · Traceability

A judge asked to **see** the reasoning trace and there was no view to show. The
data existed inside the pipeline and was discarded before reaching the
interface. For an institutional buyer this is disqualifying — a bank cannot
deploy a system whose decisions it cannot audit.

V2 treats the trace as a first-class output, not a debug artifact.

| Evidence | V1 | V2 |
|---|---|---|
| Flagged phrases, highlighted in context | Shipped | Retained |
| Plain-language explanation, in-language | Shipped | Retained |
| Offline rules fired | Returned but never rendered | Shown, itemised by rule |
| Retrieved patterns + similarity scores | Computed, then discarded | Returned and persisted |
| Model identity and prompt version | Not captured | Stamped on every verdict |
| Tamper-evident audit record | Absent | Append-only, hash-chained |

**Why version stamping matters.** Without recording which model and prompt
produced a verdict, a decision made six months ago cannot be reproduced or
defended — the models will have changed underneath it. For a regulated buyer,
*"we cannot reconstruct why we told your customer that"* ends the conversation.

**The answer, next time it is asked:** every verdict carries the rules that
fired, the scam patterns it matched with similarity scores, the exact phrases
flagged, and the model and prompt version that judged it — written to an
append-only record.

---

## 04 · Deployment models

Institutions do not buy architectures. They buy ones they are permitted to run.
Four shapes, one detection core.

| Model | For | Where data sits | Trade-off |
|---|---|---|---|
| **Public SaaS** | Citizens, free tier | Our cloud; hashed aggregates only | Fastest reach; not acceptable to a bank |
| **Embedded SDK** | Banks, wallets | Inside the bank's own app | Strongest privacy story; their release cycle |
| **Private VPC** | Large banks, NBFCs | Their tenancy, our stack | Full data control; they own ops |
| **On-premise** | State cyber cells, government | Their hardware, air-gappable | Meets sovereignty rules; slow cadence |

**The bank objection, answered.** The embedded SDK is the real response to *"why
would we put customer data on your cloud?"* — you don't. Detection runs inside
your app, on your customer's device, under your privacy policy. We ship a signed
pattern bundle and a model; no message reaches us.

---

## 05 · Scalability

Cost scales with **cloud escalations**, not with users. Edge processing means
traffic growth does not translate one-to-one into spend.

| Layer | Scaling property | First constraint | Response |
|---|---|---|---|
| API | Stateless — any request, any instance | Instance count | Horizontal; no code change |
| Vector search | Indexed (ivfflat); pattern growth ≠ slowdown | Index rebuild time | Scheduled reindex, read replica |
| LLM escalation | Linear in escalations, not users | Provider rate limit | Two providers + verdict cache; paid tier is a billing change |
| Verdict cache | One scam text reaches thousands | Cache memory | Move in-process cache to Redis |
| Pattern sync | Read-only, CDN-cacheable | Bandwidth | Delta bundles, signed |
| Audit log | Append-only, write-heavy | Storage growth | Partition monthly, cold-tier after 90 days |

### Known limits — state these before you are asked

- The in-process verdict cache does not survive a restart and is not shared
  across instances.
- **There is no labelled accuracy benchmark.** Precision and recall are
  unquantified. This blocks every accuracy claim we might want to make.
- **The audit log can have gaps.** An audit write that fails does not fail the
  scan — a user mid-scam gets their warning even when the compliance record
  cannot be written. The verdict is still returned and stored; only the chain
  entry is missing, and the response says so by omitting `trace.audit`. The
  chain stays verifiable across a gap, because each link hashes its own
  predecessor rather than a row count.
- **Audit appends serialise on one advisory lock.** That is what stops two
  concurrent scans forking the chain, and it puts a ceiling on append
  throughput. Not a constraint at pilot scale; it becomes one before the
  institution dashboard does.
- **Audit records outlive the account that produced them.** `verdict_audit`
  references scans and users by value, not by foreign key — an append-only
  table cannot participate in referential actions, because every referential
  action is a mutation, and an `on delete` rule would either fail the deletion
  or delete the evidence. So closing an account leaves audit rows carrying a
  `user_id` that no longer resolves. The payload holds a digest and never the
  message, so what remains is pseudonymous, but this is not yet an answer to a
  DPDP erasure request. A real one means a documented process — a compensating
  erasure record, or crypto-shredding the pepper per user — and neither exists
  yet. **Decide this before a pilot handles real users' data.**
- On-device model size versus low-end Android RAM is unvalidated.
- Prompt-injection hardening is partial, not solved.

---

## 06 · Institutional integration

Three buyers, three genuinely different products on one core. Selling all three
the same dashboard would be the mistake.

### Banks and NBFCs — the compliance wedge

RBI requires banks to run customer fraud-awareness programmes: an existing,
funded, mandatory budget line, mostly spent today on posters and SMS blasts
nobody reads. We are that obligation delivered as working software in twelve
languages, with reporting to evidence the programme.

- **Embedded SDK** inside the bank's app — protection with no separate install
- **Payment interrupt** on their own UPI flow — the highest-value integration
- **Awareness module** — the practice game, white-labelled, with completion reporting
- **Fraud telemetry** — which scams target their customers, by region and week

### State cyber cells — the intelligence product

A cyber cell does not want a consumer app; it wants situational awareness. Which
scam is spreading in which district this week, built from hashed reports
containing no personal data — so it can be shared without a privacy review
blocking it.

- Live regional scam-trend dashboard by category and district
- Emerging-pattern alerts before a wave peaks
- Verified-report export for FIR corroboration
- Air-gappable on-premise deployment

### Ecosystem

NPCI for authoritative VPA reputation, telecom operators for network-level call
screening, CERT-In for coordinated disclosure. All partnerships to **earn after a
pilot**, not assumptions to design around now.

---

## 07 · Security and compliance

| Control | Implementation | Status |
|---|---|---|
| Identity | Signed JWT verified server-side; client identity never trusted | Shipped |
| Data isolation | Row Level Security — the database blocks cross-user reads, not just the app | Shipped |
| Key handling | Service key backend-only; browser holds public anon key | Shipped |
| Community privacy | SHA-256 digests; raw text never stored centrally | Shipped |
| Credential hygiene | OTP, PIN, card numbers never requested or stored, by design | Shipped |
| Licensing | MIT / Apache-2.0 only — no copyleft exposure | Shipped |
| Phone-number identity | **HMAC with server-side pepper** | Required for mobile |
| Audit trail | Append-only, hash-chained verdict records | Shipped — enforced by trigger, not policy |
| Prompt injection | Delimited input, forced JSON, server-side schema validation | Partial |
| Data residency | India-region storage; DPDP Act 2023 alignment | Planned |
| Model governance | Version pinning, drift monitoring, staged rollout | Later |

> **Do not skip this.** A plain SHA-256 of an Indian mobile number is trivially
> reversible — keyspace ≈ 10¹⁰ and the `+91` prefix is known. Phone-number
> identity must be HMAC with a server-held pepper, or the "we only store hashes"
> claim is false.

---

## 08 · Roadmap

| Phase | Deliverable | Why this order | Owner |
|---|---|---|---|
| P0 | Traceability UI + persisted evidence | Closes the gap that lost marks; data already exists | Pavan |
| P0 | Accuracy benchmark + labelled set | Every later claim depends on being able to measure | Pavan |
| P1 | Android shell + SMS auto-scan | First true interception; no alarming permissions | Ayush |
| P1 | On-device rule engine port | Removes the network from the hot path | Pavan |
| P2 | Payment interrupt (UPI watcher) | The terminal intervention — highest value | Ayush |
| P2 | Institution dashboard | What cyber cells and banks actually buy | Hem |
| ✅ | Call screening + number reputation | Shipped in #133 — the one layer that needed no Play declaration | Ayush |
| P3 | Live call analysis | Hardest, legally constrained. The "needs the rest proven" precondition is now met, and #136 retired it; what remains is a feasibility gate, not a wait | Ayush |
| P3 | Embedded SDK packaging | Only worth building once a bank has said yes | Pavan |

**Sequencing logic.** P0 is unglamorous and comes first anyway: without a
benchmark no accuracy claim can be defended, and without traceability no
institution can deploy it. Build the ability to prove things before building more
things to prove.

---

## 09 · Team

Ownership is enforced in [`.github/CODEOWNERS`](../.github/CODEOWNERS) — reviews
route automatically. Owning an area means being accountable for reviewing it, not
being the only one allowed to touch it.

| Person | Owns | First deliverable |
|---|---|---|
| **Pavan** `@CODER7657` | Architecture, detection core, security, migrations, content + QA + evaluation | Traceability persistence, then the labelled benchmark |
| **Hem** `@Hem60` | Frontend — web app, design system, accessibility | Trace viewer UI, then institution dashboard |
| **Ayush** `@Ayush3422` | Voice, language, Android client | Android shell + SMS auto-scan |

**Content, QA and evaluation** are held by the lead until a fourth contributor
joins. Nothing in the roadmap can be claimed to work until someone can measure
whether it does — and every accuracy question a jury or a bank asks lands on that
work, so it is owned, not deferred.

---

*Interactive version of this document with diagrams:*
<https://claude.ai/code/artifact/d784f09f-81d8-4fb7-a216-450381d3a5e3>
