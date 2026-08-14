# START HERE

You are joining Raksha AI mid-flight. This file gets you from `git clone` to a
reviewed pull request without asking anyone a question.

Read this once, top to bottom. It takes about ten minutes. Then read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) before you write anything —
the design changed direction after the jury round, and code written against the
old model will be rejected in review.

---

## 1. What this project is now

Raksha AI detects financial scams — calls, SMS, fake UPI requests, loan fraud —
for first-time digital banking users in India, in twelve languages, and explains
the verdict in plain language out loud.

**The one thing that changed:** a jury member asked how a *website* helps someone
who has a scammer on the phone right now. It doesn't. A victim who is being
successfully scammed does not feel suspicious, so they never open the app.

So V2 stops waiting to be consulted and starts **intercepting** — on the device,
in the channels fraud actually arrives through. The website becomes the dashboard,
not the product.

If you internalise one sentence before writing code, make it this one:

> A scam does not fail when it is detected. It fails when the money stops.

---

## 2. One-time machine setup

Run these **once per machine**, not per session. They install the shared skill set
this repo expects.

```bash
claude plugin marketplace add alirezarezvani/claude-skills
claude plugin marketplace add obra/superpowers-marketplace

claude plugin install engineering-skills@claude-code-skills
claude plugin install engineering-advanced-skills@claude-code-skills
claude plugin install a11y-audit@claude-code-skills
claude plugin install security-guidance@claude-code-skills
claude plugin install demo-video@claude-code-skills
claude plugin install agenthub@claude-code-skills
claude plugin install zero-hallucination-coder@claude-code-skills
claude plugin install write-a-skill@claude-code-skills
claude plugin install superpowers@superpowers-marketplace
```

After that, `.claude/settings.json` in this repo auto-enables all of them whenever
you open a Claude Code session **inside this folder**. Nothing to configure per
session, and it does not affect your other projects.

### When to reach for which skill

Don't run them at random. Each has a job:

| Skill | Use it when |
|---|---|
| `engineering-skills` | Everyday implementation — the default |
| `engineering-advanced-skills` | Refactors, performance, tricky architecture calls |
| `security-guidance` | **Mandatory** before any PR touching auth, config, migrations, or anything handling a phone number |
| `a11y-audit` | **Mandatory** for frontend PRs — our users include elderly and low-literacy people |
| `zero-hallucination-coder` | Anything involving an API you have not personally verified |
| `write-a-skill` | You've done the same manual sequence three times |
| `demo-video` | Recording a walkthrough for a PR or a pilot |
| `superpowers` / `agenthub` | Multi-step work you want decomposed |

---

## 3. Run it locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: Scripts, macOS/Linux: bin
pip install -r requirements.txt
cp .env.example .env          # then fill in your own keys
uvicorn main:app --reload     # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env.local    # point VITE_API_BASE_URL at http://localhost:8000
npm run dev                   # http://localhost:5173
```

**Get keys from Pavan.** Never commit `.env` — both are git-ignored, and if you
ever push one by accident, say so immediately: the fix is rotating the key, not
deleting the commit.

> **Backend note:** the deployed backend sleeps after ~15 minutes idle and takes
> ~40–50s to wake. If a request seems to hang, it is a cold start, not a bug.

---

## 4. Where you personally start

| You | You own | Your first task |
|---|---|---|
| **Pavan** `@CODER7657` | Architecture, detection core, security, migrations | Persist retrieval evidence; port the rule engine to run on-device |
| **Hem** `@Hem60` | Frontend — web app, design system, accessibility | Trace viewer UI, then the institution dashboard |
| **Ayush** `@Ayush3422` | Voice, language, Android client | Android shell + SMS auto-scan — the first real interception |
| **Harsh** `@harshpansuriya71-sudo` | Content and QA — scam patterns, practice bank, evaluation | Labelled benchmark set and eval harness |

**On the benchmark:** this is not the junior task. Right now we cannot state a
precision or recall figure, which means every accuracy claim we make is
unsupported. A jury already asked and we had no number. Nothing else on the
roadmap can be defended until this exists.

---

## 5. How to contribute

We do **not** fork — the repo is private, so everyone branches inside it.

```bash
git checkout master && git pull origin master
git checkout -b feat/sms-listener
# ...work...
git add <specific files>        # never `git add .` blindly
git commit -m "Add SMS listener that auto-scans incoming messages"
git push -u origin feat/sms-listener
```

Then open a PR into `master`.

**Enforced by branch protection — not suggestions:**
- One approving review required
- CODEOWNERS review required for the area you touched
- Review conversations must be resolved
- No force pushes to `master`

CI is **not** a required check, deliberately: both workflows are path-filtered, so
a docs-only PR never reports one and would sit unmergeable forever. CI still runs
and is visible on the PR — **do not approve a PR with red CI.** That gate is you,
not a setting.

Branch names: `feat/…`, `fix/…`, `chore/…`, `docs/…`

---

## 6. The quality bar

This is what "quality parts" means concretely. A PR that misses these gets sent
back, and that is not personal — the users are people who lose real money when we
get it wrong.

**Every PR**
- [ ] Tested against the running app, not just compiled
- [ ] Tested in English **and** at least one Indic language
- [ ] No console errors on the happy path
- [ ] Degrades gracefully when the network or a provider fails
- [ ] No secrets, no keys, no real phone numbers in code, tests or fixtures

**Frontend PRs additionally**
- [ ] Works at 375px width — most users are on a low-end phone
- [ ] Keyboard reachable, visible focus states
- [ ] Ran `a11y-audit`
- [ ] Every user-facing string added to all three locale bundles (`en`, `hi`, `gu`) —
      never hardcoded in JSX

**Backend PRs additionally**
- [ ] Response shape validated server-side, never trusted from a model
- [ ] Failure path returns something safe, never a bare 500
- [ ] Ran `security-guidance` if it touches auth, config, migrations, or phone numbers

### Three rules with teeth

1. **Fail safe, never confidently wrong.** If detection cannot run, return a
   *conservative* verdict. Over-warning is recoverable; wrongly clearing a real
   scam is not.
2. **Never ship unreviewed machine translation of safety advice.** A mistranslated
   instruction can get someone robbed. English, Hindi and Gujarati are
   human-reviewed; everything else shows an honest notice instead.
3. **Hash phone numbers with HMAC and a server-held pepper, never a bare hash.**
   A plain SHA-256 of an Indian mobile is brute-forceable — the keyspace is about
   10¹⁰ and `+91` is known. Without the pepper, "we only store hashes" is untrue.

---

## 7. Things that will bite you

- **Cold starts.** ~40–50s on the free tier after idle. Not a bug.
- **UTF-8 in shell tools.** Git Bash on Windows mangles Devanagari and Gujarati in
  `curl -d`. Test Indic text with Python or the browser, never a shell heredoc —
  this already caused one false bug report.
- **Sarvam credits are finite.** Repeated identical text hits the server cache and
  is free; new text is not.
- **Actions minutes.** Private repo = 2,000/month. Do not add a frequent cron.
- **`git add .`** will pull in `.env`, PDFs and build junk. Stage explicitly.

---

## 8. Where everything lives

```
backend/app/
  routes/        HTTP layer — auth, validation, rate limits
  services/      the actual logic
    rag.py           retrieval — the grounding step
    llm.py           classification prompt + schema validation
    rule_engine.py   offline detection, no network
    upi_check.py     typosquat detection, deliberately no AI
    tts.py / stt.py  voice ladder: Sarvam → fallback
  core/          auth, config, language registry, db client

frontend/src/
  pages/         one file per screen
  lib/           api client, voice, speech, languages
  i18n/locales/  en / hi / gu bundles — all UI strings

supabase/migrations/   schema, RLS policies
docs/ARCHITECTURE.md   read before writing code
```

---

## 9. Read next

1. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the V2 design and why it changed
2. [`CONTRIBUTING.md`](CONTRIBUTING.md) — full workflow and review rules
3. [`README.md`](README.md) — product overview

Ask in the group before guessing. A five-minute question is cheaper than a
rejected PR.
