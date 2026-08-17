# 🛡️ RAKSHA AI — Handoff

**Written:** 15 August 2026. Everything below was verified against `master` at the
time of writing, not recalled.

---

## 00 · Where the project stands

Live on Vercel (frontend) and Render (backend), both free tier. Detection across
twelve languages, RAG-grounded via pgvector, Groq → Gemini → offline-rules
ladder, Sarvam voice, practice game, chat assistant. Android client scans
incoming SMS entirely on-device.

**Verified numbers, not claims:**

| | |
|---|---|
| Test suite | **421 passing** — plus 4 Android unit tests that now actually run (#80) |
| Rule corpus | 79 rows — 77 enforced, 2 known gaps (both accepted false positives) |
| Offline engine | recall **1.000** in all twelve languages |
| LLM path | English precision **0.933** / recall **1.000**; Hindi **0.923** / **1.000**. Held out, re-scored against all 79 rows (#76) |
| Evasion queue | 3 entries, all `fixed` |
| Provider rungs | Groq OK, Gemini OK, embeddings OK — checked live |
| Migrations | `0001`–`0007` applied; `0008` open in a PR |

**The caveat that must travel with those numbers:** nine of the twelve language
codes have two corpus cases each. Their 1.000 means the plumbing works, not that
the vocabulary is right.

**This is now a scope decision rather than a caveat. The product claims three
languages — English, Hindi, Gujarati — and does not say twelve at all.** The
earlier instruction here was "do not put twelve in front of a buyer *without*
the caveat", which left the number sayable by anyone willing to add a sentence.
It was said without the sentence, repeatedly. A claim that survives only when
someone remembers a footnote is not a claim worth keeping.

The rules for the other nine stay in the engine — an unreviewed rule that catches
a real scam beats no rule, and nothing is served by deleting coverage a user
might benefit from. They are simply not advertised. A language becomes supported
when a speaker reads its rules, which is what `testdata/review/` exists for.

---

## 01 · The state that is not in git

**A merge is not a deploy.** Render auto-deploy is **off** and migrations are
applied by hand. Two of three deployment targets need a human.

| Piece | Where | Deploys |
|---|---|---|
| Backend | Render — `raksha-ai-c5yu.onrender.com` | **Manually** |
| Frontend | Vercel | **Via `.github/workflows/frontend-deploy.yml`**, on push to `master` |
| Database | Supabase | **Manually**, SQL editor |

**Dashboard-only config, invisible from the code:**

- `VITE_API_BASE_URL` — Vercel. The repo's `.env` files point at localhost.
- `AUDIT_HASH_PEPPER` — Render. Without it the audit digest is a bare SHA-256.
- Four provider keys — Render, plus four GitHub Actions secrets (interactive and
  `_BATCH` pairs).

Post-merge order is in `START-HERE.md` §1b: **migration first, then deploy, then
verify it is actually live** — `/openapi.json` is a usable fingerprint when the
change touches a response model.

---

## 02 · Nothing is immediate

Everything that sat here has landed. Recording what they were, because the list
being empty is the only evidence that they were worked rather than forgotten.

**Deploy — done.** All of `0005`, `0006` and `0007` applied by hand, backend
deployed, verified against the running service rather than assumed:
`/api/agents`, `/api/agents/runs` and `/api/agents/{agent_id}/switch` are on the
deployed `openapi.json`, `ScanResult` still carries `trace`, and all three write
endpoints return 401 unauthenticated. An unauthenticated stop request against
`a6_redteam` left both agents `enabled` — the switch is genuinely closed.

**#71 — merged**, and the CODEOWNERS deadlock it exposed is fixed (#78).
`/frontend/src/i18n/` now names three owners, so the next i18n PR does not need
an admin override.

**`:app:test` — wired in (#80).** Four unit tests had never executed in CI. They
all pass, in 22s. Anticlimactic, and that is the good outcome: they were correct
the whole time, and nothing would have said so if they had not been.

**LLM benchmark — re-scored (#76)** against all 79 rows. Recall stays 1.000
everywhere; precision moves to 0.933 (`en`) and 0.923 (`hi`). The three benign
messages now warned about are named in the report, and one is the direct cost of
#66 teaching the rules that `disclose` is a share verb — a parcel firm asking
for a delivery address reaches for that word too. Re-run it inside
`backend/.venv`, not the system Python — see §07.

**The one thing left over:** `AGENT_OPERATOR_IDS` must be set in Render to the
operator's Supabase UUID. Unset means nobody can flip an agent switch, including
the lead. That is the fail-closed default working as designed, but it will read
as a bug to whoever meets it cold.

The open work is now in §06, on a person, rather than here.

---

## 03 · What changed, and why it mattered

Twenty-five PRs merged. The through-line: **nearly every serious bug was
invisible from the website, where everything looked fine.**

### The detection engine was quietly broken

- **Rules that never fired.** `\bOTP\b.{0,20}\bshare\b` required OTP *before*
  "share". Three of six English rules could not match realistic text (#18).
- **Nine of twelve languages had no rules at all**, so with both providers down
  `scan.py` returned a 503 — an error page instead of a warning (#31, #42).
- **The rules only knew the acronym.** "the numeric code sent to your phone"
  fired nothing (#44, #46).
- **`suspend\w*` never matched "suspension"** — the stem is not a prefix of the
  noun (#44).
- **Hindi was Devanagari-only**, so the rules fired on how a newsreader writes
  Hindi and not on how anyone texts it (#23, #66).
- **`reveal` and `disclose` were not share verbs** (#63, #66).

### The provider ladder was one rung pretending to be two

`gemini-1.5-flash` was **retired**, so every fallback 404'd — for an unknown
number of weeks. Nothing caught it because nothing ever called it: Groq rarely
fails, so the second rung was only reached under load. When a red-team run
finally rate-limited Groq, the only symptom was "Both Groq and Gemini failed",
which reads like an outage rather than a model id (#45).

The same dead model was **still live in `chat.py`** after #45 fixed `llm.py`,
because the id was a literal string in two files (#56).

### CI could not fail

`pytest -q || echo "No tests yet"`. #18 shipped 47 tests that could not be
collected at all on a clean runner, and the check reported green throughout
(#22, #34).

### Agents competed with users for quota

The benchmark, the red-team loop and live scans all drew on one key. An internal
tool took live detection down (#48, #51, #59).

---

## 04 · Decisions to preserve, with their reasons

Reasons matter more than the decisions; without them the next person reverses
them for sensible-sounding motives.

**Agents never enter the detection hot path.** Latency, determinism,
auditability. `AGENT-LAYER.md` §10 lists every banned location.

**The corpus is the specification; the engines implement it.** `testdata/rule_corpus.jsonl`
is read by both the Python and Kotlin suites. `known_gap` rows are asserted
**strictly in both directions**, so fixing a defect fails the build until the
corpus is updated. Closing a gap is a visible edit, never a silent behaviour
change. *This has caught its own author three times.*

**`fixed` is decided by replaying, never by a human clicking.** A person ticking
a box records an intention; a replay records a fact. `wontfix` is the inverse —
a machine may never set it, because "not worth chasing" is a judgement about our
users.

**Cross-sentence matching is per-rule, not a setting.** `refund_click` and
`kyc_expiry` may cross a sentence; `otp_share` may not, because that boundary is
the only thing keeping *"OTP for your login is 449281. Never share it with
anyone."* clean.

**Romanised Hindi lives in the `hi` rule set, not English.** `band`, `do` and
`bata` are English words. Scoping keeps the false-positive blast radius inside
the language.

**Interactive calls never retry; batch calls do.** A user waiting mid-scam is
better served by falling to the next provider than by a backoff. A test forbids
`time.sleep` on the interactive path.

**The degraded verdict is never cached.** Storing it would serve "AI service
unavailable" as a considered judgement for a week after the outage ended.

**A cached verdict says so in the trace.** Otherwise the audit record credits a
model call that never happened.

**Model ids live in exactly one place** — a constant cannot drift from itself
(#56).

**Over-warning is accepted, but must be nameable.** Both benchmark halves itemise
false positives, because "accepted" means nothing if we cannot say what is being
warned about.

**No aggregate accuracy figure anywhere.** A single number across twelve
languages is dominated by whichever language someone wrote cases for. The
dashboard renders "too few" as words rather than a dimmed percentage — a dimmed
100% is still a 100% somebody can screenshot.

**Blockchain: one narrow use.** Anchoring audit-log Merkle roots. Storing
messages on-chain conflicts with DPDP erasure. The existing `verdict_audit`
chain is append-only **by trigger**, not by policy — the backend holds the
service role key, which bypasses RLS, so a policy would not constrain us. Proven
by attacking it with that key: UPDATE and DELETE both refused.

**HMAC + server pepper for the audit digest.** A bare SHA-256 of a phone number
is ~10¹⁰ guesses, and the audit row also carries a `user_id`.

---

## 05 · Research findings that changed the roadmap

**The screen-share sentinel cannot be built as a consumer app.** Android 15's
`DETECT_SCREEN_RECORDING` is **per-app** — an app learns only that its own UI is
captured. No third-party app can tell that the *banking* app is being shared.
Only the OS or the bank's own app can see it, so it belongs in the **bank-side
SDK**. Google shipped the OS version as a **US pilot**, not available in India.

**Google's on-device scam detection in India is Pixel 9+ only** — under 1% of a
market that is 96% Android. That gap is the opening.

**DoT's FRI/DIP** has 1000+ banks and TPAPs onboarded; integration runs through
being or partnering with a TPAP.

**A2A** is Linux Foundation-hosted with 150+ organisations. Right at the
institution boundary, wrong inside one codebase — it would add discovery and a
wire protocol that is pure attack surface between our own agents.

---

## 06 · Open work

**@Ayush3422 is back.** The redistribution recorded in the previous version of
this section is over, and the Android work has gone back to him. What has not
changed is the reasoning behind it: Android platform work does not go to a
frontend developer, and that held while he was away rather than being an excuse
made at the time.

### @CODER7657

| # | What | Note |
|---|---|---|
| #32 | **Persist review-queue decisions** | Rescoped and moved from Hem. A/B/C/D all render; only the store is missing. Not UI work — where a decision is written, what an accepted draft *becomes* now that 0007 rejects an unapproved `agent` row, and whether a decision is reversible |
| #83 | **Server-side half of the Android trust chain** | New, split out of #29. Bundle signing, Play Integrity verified server-side, device trace held to the backend schema. All three are places where a device-side control is only as good as something on the server |
| #77 | `test_key_pools.py` reads the developer's real `.env` | Small, and it fails for whoever has just finished configuring their machine |

### @Ayush3422

| # | What | Note |
|---|---|---|
| **#39** | Play `RECEIVE_SMS` declaration | **Submitted, awaiting Google.** Still the only item with an external clock. Nothing Android reaches a user until it clears |
| **#82** | **Release readiness — what blocks the first APK** | New. Finite, unlike #29. No `signingConfig` exists at all; Data Safety form; target-API deadlines untracked; plus tapjacking and surviving a reboot |
| #29 | Android enterprise bar | A standing bar, not a task. Audited against the tree: about a third is done. R8 (#69), shared i18n (#71), the whole #38 SMS pipeline. The server-side items moved to #83 |

### @Hem60

Nothing open. #71, #75 and #79 all merged; #32, #41 and #64 are closed or moved.

Worth saying plainly: every rendering surface the human gate asked for now
exists — review queue, benchmark dashboard both halves, evasion queue,
provenance, operator console. The remaining pieces are schema and lifecycle
questions, which is why they moved rather than stayed.

### Not started, worth remembering

- **The A6 loop only attacks seeds we already catch.** It has never been run
  across all twelve languages, or against the `full` detector at scale.
- **A2 phishing investigator** — `AGENT-BUILD-PLAN.md` §03. Needs the CaMeL-style
  dual-LLM split: the reading model gets no tools, the acting model never sees
  page content.
- **`scam_patterns` holds 14 rows.** That is the RAG corpus. It is small.
- **Native-speaker review** — #52 is closed as "reviewers found", but
  `REVIEW_STATUS` in `rule_engine.py` still marks eight languages `unreviewed`.
  Update it as each is actually reviewed; that table is what a buyer is shown.

---

## 07 · Traps that cost time, so they do not cost it twice

**A merge is not a deploy.** Cost us once already: #18 merged and production ran
without `trace` while everyone assumed `master` was live.

**GitHub only auto-closes the first issue in a list.** `Closes #23 and #63` closes
only #23. Repeat the keyword.

**GitHub Actions secrets ≠ Render env vars ≠ GitHub Variables ≠ Environment
secrets.** Four different places. The workflow reads repo-level **Secrets**.

**A check that cannot fail is worse than none**, because people believe it. Two
instances found: `pytest || true`, and a smoke check whose header asked for the
wrong secret names — it would have reported SKIP on every rung and passed,
looking exactly like a healthy run.

**Bash heredocs mangle backslashes.** A `\b` became a literal backspace byte
inside a regex. Use the Write tool for anything containing escapes.

**Raw NUL bytes make git treat a source file as binary**, so it never appears in
a diff and can never be reviewed. Found in `SmsAssembly.kt`; use ` `.

**The sandbox blocks Gradle's daemon socket**, so Android builds cannot be
verified locally. CI is the only proof — which is why #27 exists.

**Git Bash mangles Devanagari in `curl -d`.** Test Indic text via Python.

**Run backend scripts inside `backend/.venv`, never the system Python.** The
pins resolve `protobuf` to 5.x. A global interpreter shared with other projects
drifts to protobuf 7, and then the first embedding call dies with
`MessageToDict() got an unexpected keyword argument 'float_precision'` —
`proto-plus` caps at `<7.0.0`, `requirements.txt` does not re-state that cap, so
nothing stops the global env from violating it. It looks like a broken script;
it is a broken environment. Render is unaffected, because it builds clean from
the pins on Python 3.11.9. The same drift explains any local run where
`google-generativeai` is 0.8.5 rather than the pinned 0.8.2.

---

## 08 · How the team works now

Written in #55, and it held:

- **One issue, one branch, one PR.** No bundling.
- **Do not start the next issue until the current PR merges.**
- **Rebase before pushing** — master moves several times a day.
- **CI green before review.** Vercel's author-access failure **on a teammate's
  pull request** is noise — previews are not wired for anyone but the lead. That
  exemption stops at the PR: the same refusal on a push to `master` was a real
  production outage that ran for four merges, because the frontend deploy went
  by git author and squash-merging preserves the PR author's. Ignoring a check
  is a rule about one trigger, never about one integration.
- **Say what you verified**, not "fixed it". Every good review here turned on
  someone stating a measurement.
- **Push back.** Four times a teammate was right where a written instruction was
  wrong: `UNICODE_CHARACTER_CLASS` (#28), WorkManager (#29), per-draft benchmark
  impact (#32), and the honest scope of a reflection-based test (#61). All four
  left the reasoning in the code.

### Three rules that predict where to look

All came out of review, and each earns its place by pointing at bugs rather than
by describing ones already found.

**An accommodation made to keep an existing test green is a place the tests were
already wrong.** (#130.) A conditional was added to `analyse` so nine existing
stubs would keep passing; the stubs were what hid the bug, and the conditional
reopened the hole in the same commit that was fixing an instance of it. When a
change requires an exception to keep the suite green, the exception is the
finding.

**`value or default` on an optional argument is where *unknown* silently becomes
*a value*.** (#135.) `pattern_counts or {}` turned "nobody supplied counts" into
"every language has zero patterns", which reported English — with forty — as
having no coverage at all. This project has decided the same distinction twice
elsewhere and written down why: `acceptance_rate` returns `None` rather than
`0.0` because zero and unknown are different claims, and `trace_schema.json`
calls `language_covered: null` "a third state, not a falsy second". Keep whether
a thing was *supplied* separate from what it *contains*.

**A result that flatters the design has to clear a higher bar than one that does
not.** (#116 §6.) Measuring whether an ongoing notification resists a swipe, the
first run showed it surviving one gesture and dying on the second — which reads
as "resists a reflex, yields to intent", almost exactly the behaviour the design
wanted. It was wrong coordinates: the swipe landed at y=1523 when the row was at
y=729. Re-dumping the view hierarchy each cycle turned an encouraging result into
the real one, which is that a single ordinary swipe removes it every time.

The tell is that the near-miss was *plausible*. A result that contradicts the
design gets re-run on instinct; one that confirms it gets written up. So the
check is procedural rather than attentional — re-derive the inputs on every
cycle rather than reusing the ones that produced the pleasing answer, and run the
control that would fail if the mechanism were not doing the work.

This is the same family as the other two, arriving from the observer's side
rather than the code's: the earlier premises that turned out false (the bundled
reputation set, the screening window, the contact guard) were all *assumptions
nobody noticed making*. #116 §6 added a fourth, and it was load-bearing for a
sequencing decision rather than for code.

The second rule has a corollary worth stating on its own: **writing a principle
in a docstring is not the same as holding it**, and the gap between the two is
invisible to whoever wrote both. Both of these were violated within four lines
of the comment arguing for them.

---

## 09 · The line to keep

> A scam does not fail when it is detected. It fails when the money stops.

Everything unbuilt that matters most is downstream of that sentence: the payment
interrupt, the bank-side SDK where the screen-share sentinel actually lives, and
the institution dashboard. The detection engine is now measured, the agents that
improve it exist and have found real bugs, and the phone can read an SMS without
the message ever leaving it.

What is missing is still the part that stops the transfer.
