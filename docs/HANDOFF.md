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
| Test suite | **394 passing** |
| Rule corpus | 79 rows — 77 enforced, 2 known gaps (both accepted false positives) |
| Offline engine | recall **1.000** in all twelve languages |
| LLM path (English) | precision **0.963**, recall **1.000**, held out |
| Evasion queue | 3 entries, all `fixed` |
| Provider rungs | Groq OK, Gemini OK, embeddings OK — checked live |

**The caveat that must travel with those numbers:** nine of the twelve languages
have two corpus cases each. Their 1.000 means the plumbing works, not that the
vocabulary is right. Only `en` (42 cases) and `hi` (14) are measured in any
meaningful sense. Do not put "twelve languages" in front of a buyer without it.

---

## 01 · The state that is not in git

**A merge is not a deploy.** Render auto-deploy is **off** and migrations are
applied by hand. Two of three deployment targets need a human.

| Piece | Where | Deploys |
|---|---|---|
| Backend | Render — `raksha-ai-c5yu.onrender.com` | **Manually** |
| Frontend | Vercel | Automatically on push to `master` |
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

## 02 · ⚠️ Immediate, before anything else

**1. Deploy.** The only item here that no PR can close, and the oldest. `#66`,
`#68` and `#69` are on `master` and **not live**. #68 carries migration
`0005_verdict_cache.sql`, which goes in **before** the deploy. Until then the
verdict cache does nothing and the rule fixes protect nobody.

**2. Merge #71 with `--admin`** (Hem, one source of truth for UI strings), once
reviewed. It cannot be merged any other way: `/frontend/src/i18n/` is owned by
`@Hem60 @Ayush3422`, Hem is the author, and Ayush is unavailable — so no
available person satisfies the CODEOWNERS review. This is the deadlock the
CODEOWNERS header describes, reached by a second route: not a single owner, but
a second owner who is not here. **Adding `@CODER7657` to that line is the fix**,
and it is the same fix #26 applied everywhere else.

**3. Wire `:app:test` into `android-ci.yml`.** It runs `:core:rules:test`,
`assembleDebug` and `assembleRelease` — never `:app:test`. Four unit tests under
`android/app/src/test/` have therefore never executed in CI, including the
shadowing guard #71 adds, whose whole subject is the one thing the generator
cannot see. The generator's own `GradleException` does run, so cross-locale
coverage is genuinely enforced; the shadowing check is not. A check that cannot
fail is worse than none, and this is four of them.

The LLM benchmark re-run that used to sit here is done. It re-scored against all
79 rows: recall stays 1.000 everywhere, precision moves to 0.933 (`en`) and
0.923 (`hi`), and the three benign messages now warned about are named in the
report. One of them is the cost of #66 teaching the rules that `disclose` is a
share verb — a parcel firm asking for a delivery address reaches for that word
too. Re-run it inside `backend/.venv`, not the system Python — see §07.

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

### @CODER7657

| # | What | Note |
|---|---|---|
| **#39** | Play `RECEIVE_SMS` declaration | **Submitted, awaiting Google.** The only item with an external clock. Nothing Android reaches a user until it clears |
| #29 | Android enterprise bar | R8 done (#69). Next: tapjacking `filterTouchesWhenObscured`, signing config, instrumentation matrix |
| #54 | Ops hygiene | Closes when #70 merges |

### @Hem60

| # | What |
|---|---|
| #71 | UI strings, one source of truth — **open PR, needs review** |
| #32 | Human gate — queue shipped read-only; the decision store is mine to design |
| #41 | Agent surfaces — evasion queue shipped; run log remains |
| #64 | Superseded by #71 once merged |

### @Ayush3422 — unavailable

His work was redistributed. #23 and #29 came to me; #64 went to Hem. **Do not
give Android platform work to a frontend developer** — that was the reasoning,
and it still holds.

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
- **CI green before review.** The one check to ignore is Vercel's author-access
  failure on a teammate's PR.
- **Say what you verified**, not "fixed it". Every good review here turned on
  someone stating a measurement.
- **Push back.** Four times a teammate was right where a written instruction was
  wrong: `UNICODE_CHARACTER_CLASS` (#28), WorkManager (#29), per-draft benchmark
  impact (#32), and the honest scope of a reflection-based test (#61). All four
  left the reasoning in the code.

---

## 09 · The line to keep

> A scam does not fail when it is detected. It fails when the money stops.

Everything unbuilt that matters most is downstream of that sentence: the payment
interrupt, the bank-side SDK where the screen-share sentinel actually lives, and
the institution dashboard. The detection engine is now measured, the agents that
improve it exist and have found real bugs, and the phone can read an SMS without
the message ever leaving it.

What is missing is still the part that stops the transfer.
