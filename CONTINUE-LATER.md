# Continue later — checkpoint

**Written 26 August 2026, against `master` at `0949030`.** Every number below was
measured at that commit, not carried forward. If you are reading this more than a
few days later, re-measure before quoting anything.

This is a stopping point chosen deliberately, not an interruption. The work that
remains needs hardware, a Play Console account, or people who are not here — and
everything that did not need those is either done or listed in §04 with a reason
for the order.

---

## 00 · Read these first, in this order

| File | For |
|---|---|
| [`START-HERE.md`](START-HERE.md) | Machine setup, where things deploy, the three-language scope |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | §00 verified numbers · §04 decisions and their reasons · §07 traps · §08 how the team works |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | §01 the five layers and what each does **not** reach |
| [`docs/PHASE-2-PLAN.md`](docs/PHASE-2-PLAN.md) | §00 the four constraints · §00b latency budgets · §06 definition of done |
| **#150** | The ordered plan to done. This file is its checkpoint |

**The four constraints override everything.** A user can always see their own data
and trace; nothing agent-generated reaches a user unreviewed; agents never enter
the detection hot path; fail safe, never confidently wrong.

---

## 01 · Verified state at `0949030`

| | |
|---|---|
| Backend tests | **913 passing**, ruff clean |
| Android tests | 83 unit tests; the parity task genuinely executes (#129). Gradle cannot run in a review sandbox — CI is the source |
| Rule corpus | **88 rows** — 85 enforced, 3 `known_gap` (all accepted false positives) |
| Corpus balance | `en` 42 (28 scam/14 benign) · `hi` 14 (12/2) · `gu` 14 (8/6) |
| Threat feeds | **urlhaus 16,097 digests · openphish 300** · safebrowsing and phishtank empty, need keys |
| Migrations | `0001`, `0003`–`0014` — **all 13 applied** |
| Interception layers | **3 of 5** built |
| Agents | **3 of 7** real |
| Languages claimed | **3** — English, Hindi, Gujarati |
| Open PRs | none |
| Open issues | #110, #115, #116, #149, #150 — all live planning documents, none stale |

**Two numbers in `HANDOFF.md` §00 are the wrong shape and are labelled as such.**
The offline recall of 1.000 covers twelve language codes, nine of which have two
corpus cases each. The LLM precision figures were measured against a model that
no longer exists — see §03.

---

## 02 · What this session changed

**A3 and A1's measure got a caller** (`b021c82`). Both had been built, tested and
imported by nothing. `/api/insights/campaigns` and `/api/insights/discovery`,
both authenticated, 13 tests. The route composes and does not compute — every
decision about what counts as a campaign or a gap stays in the services.

**Both dead model ids repinned** (`b836909`). See §03.

**Manual triggers on the three CI workflows that gate correctness** (`138196f`,
corrected by `8cc3e4b`). Four other workflows already had one.

**The threat feed lists are populated, and a bug that could empty them is fixed**
(`0949030`). The script promised never to silently empty a working list; the
exception path honoured that and the success path did not. A feed answering 200
with an empty body wrote zero digests over a working list and returned success.
Demonstrated, fixed, and `--allow-empty` now has to be asked for. Fifteen tests
where there were none, and a daily workflow at 03:30 UTC.

The point of that work: the signal is now
`known_bad_feed / basis: feed / deterministic: True`, verified against live feed
entries. A2's Confirmed tier requires a witness page content cannot influence and
did not have one.

---

## 03 · Things that are wrong or unfinished, stated plainly

**The LLM accuracy numbers describe a model nobody can reach.** `HANDOFF.md` §00
reports English precision 0.933 / recall 1.000 and Hindi 0.923 / 1.000. Those
were measured against `llama-3.3-70b-versatile`, which was retired. The ladder is
restored on `openai/gpt-oss-120b` and `gemini-3.6-flash`, both verified to exist,
accept JSON mode, and classify one canonical scam correctly — **that is not a
benchmark.** Re-run `scripts/run_llm_benchmark.py` before either figure is quoted
again. This is the single highest-value outstanding task that needs no hardware.

**The provider smoke check had been failing since 17 August and nobody looked.**
Two scheduled runs red, both rungs dead, and the check that exists to catch a
retired model was itself the thing nobody read. It is green now. Watch it.

**Two services are still built and wired to nothing**, deliberately:
`page_analysis` needs the sandbox runner and `verdict_revision` needs a
scheduler. Both are infrastructure that does not exist. Half-wiring them would be
worse than leaving them honest.

**The benign half of the corpus is smaller than the scam half in all three
supported languages**, which contradicts the standing rule in `HANDOFF.md` §08.
`hi` at 12 scam to 2 benign is the worst. Over-warning is the accepted direction,
but two benign cases cannot establish that we are not over-warning.

**Committing the feeds costs ~1 MB of git history per day**, roughly 365 MB a
year. Measured on the first real run. Survivable, not free, and the mitigations
are named in `.github/workflows/refresh-threat-feeds.yml`.

**Two claims I made in this session were wrong**, both recorded where they were
made:

- I told #149 and #150 that threat feeds were *"Nothing. Zero are built."* The
  service, the script, the format and a README all existed. I grepped for vendor
  names instead of reading the service list — a claim about a system made without
  reading the system, which is the failure #149 is about
- I claimed a Backend CI run had never fired and used that to justify a commit.
  It fired two minutes after I looked. Silence read as failure, which is the same
  error as silence read as success

---

## 04 · The plan from here

Ordered. **Phase A costs nothing and blocks everything.**

### Phase A — prove it on hardware · @Ayush3422, #116 §1

None of this needs money, and items 1–4 need nobody else.

1. **Dispatch a fresh release build.** The artefact from run `31931926615`
   predates #128 and carries the diverging rule engine
2. **Install on the Pixel 10a.** Never done once. Every Android number in this
   repository is from an emulator
3. **Re-verify on hardware** what the emulator measured: reboot survival, the
   ~25s direct-boot delay, the force-stop notice, #133's layer 3 timings
4. **Write the Data Safety answers into the repository**, not Console — see §06
5. **Macrobenchmark**, with the device named in the sentence. "Under Xms on a
   Pixel 10a", never "meets the budget"
6. **Nine `hi`/`gu` strings** — the eight from #133 plus `call_screening_limitation`

### Phase B — the free level-ups · #149

1. ~~Threat feeds~~ — **done**
2. **Re-run the LLM benchmark.** Promoted from §06 housekeeping to the top of
   this list, because §03 explains why
3. **Map every guard to OWASP ASI01–ASI10.** Documentation, no risk, and it is
   the vocabulary judges use. We already defend ASI01 (#113) and ASI06 (#130)
4. **Claim EU AI Act Article 12.** The hash-chained log already is that artefact.
   **Verify the Article text before claiming it**
5. **Expose Raksha as an MCP server.** Read-only tools first, targeting the
   2026-07-28 spec. Deliberately not started at the end of a long session — it
   deserves its own sitting
6. **AgentDojo subset in CI.** Check the licence first

### Phase C — layer 5, the payment interrupt · #116 §5

The thesis. **Paperwork first**: submit the accessibility declaration, then build
while it is in review. This is the one item that genuinely needs Console access,
so it is where the fee decision actually bites.

### Phase D — layer 4 · #116 §6

Three measurements, any of which may return "no": reach the audio, fit a model on
the target handset, lawful to record. **Layer 4 has no guaranteed deliverable**
(#143) — the no-audio fallback was measured across five routes and none ship
(#148).

### Phase E — the agent layer finishes · @Hem60, #115

A1's model half, then A5 once A3 has produced a real finding.

### Phase F — #110, the QA gate

The definition of done. Nobody marks their own work done.

---

## 05 · Traps that will cost you time

Most are in `HANDOFF.md` §07. These are the ones this session hit:

- **`npx tsc -b` reports success with no `node_modules`.** Run
  `./node_modules/.bin/tsc` after `npm ci`
- **Gradle cannot run in a review sandbox** ("unable to establish loopback
  connection"). CI is the only proof for Kotlin. Plain `java` *does* work, which
  is enough to test regex behaviour directly
- **Bash heredocs break on quotes in long markdown.** Write the body to a file,
  then `--body-file`
- **Backend CI can take ~15 minutes to appear** after a push. It is late, not
  missing. All three CI workflows now have `workflow_dispatch` — use it rather
  than concluding from an absence
- **Do not use the system Python.** Use the venv at
  `.claude/worktrees/handoff-structure-review-de29f6/backend/.venv` — the system
  3.13 has a protobuf that breaks the embedding call
- **Vercel's Git integration is off for production.** The frontend deploys via
  `.github/workflows/frontend-deploy.yml` by token, because Vercel refuses
  deployments whose git author is not on its team and squash-merge preserves the
  PR author. Ten for ten on author before the fix

---

## 06 · State that is not in git

- **A merge is not a deploy.** Render auto-deploy is off; migrations are applied
  by hand in the Supabase SQL editor. The frontend is the only automated one
- **The backend has not been deployed since this session's changes.** `0949030`
  includes the model repin — until it is deployed, production is still calling a
  retired Groq model and falling through to Gemini on every scan
- **All 13 migrations are applied.** Nothing outstanding in the SQL editor
- **The Play developer account costs a one-time US$25 (~₹2,000)** and has not been
  paid. The Data Safety *form* is free; the account you need to reach it is not.
  Play is off the critical path — direct APK install and Firebase App
  Distribution cover a pilot and bypass the `RECEIVE_SMS` declaration entirely
- **`AGENT_OPERATOR_IDS` must be set in Render** or nobody can flip an agent kill
  switch, including the lead
- **Two feeds need keys**: `GOOGLE_SAFE_BROWSING_API_KEY` and `PHISHTANK_APP_KEY`.
  Both are skipped by name and leave their files untouched
- **Four remote branches are stale** (July, ~37k lines behind master):
  `backend/chatbot-and-trends`, `feat/redteam-loop`,
  `frontend/chatbot-radar-upi-game`, `frontend/practice-simulator`. Deleting them
  was blocked mid-run; their SHAs are in the session log if you want to restore

---

## 07 · The line to keep

The reason this project is worth anything is that its claims are true. Three
rules earned that, and they are in `HANDOFF.md` §08:

> An accommodation made to keep an existing test green is a place the tests were
> already wrong.
>
> `value or default` on an optional argument is where *unknown* silently becomes
> *a value*.
>
> A result that flatters the design has to clear a higher bar than one that does
> not.

And the corollary, which cost the most to learn: **writing a principle in a
docstring is not the same as holding it**, and the gap is invisible to whoever
wrote both.

**A box ticked without a number behind it is not ticked.**
