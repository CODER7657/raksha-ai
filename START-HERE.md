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

## 1b. Where it runs

None of this was written down, and none of it is discoverable from the code —
you would have to already know. Recording it so nobody has to guess again.

| Piece | Where | Deploys | Notes |
|---|---|---|---|
| Backend | Render, free tier — `https://raksha-ai-c5yu.onrender.com` | **Manually.** Auto-deploy is off | Sleeps after ~15 min idle; cold start is 40-50s |
| Frontend | Vercel | Automatically, per push to `master` | |
| Database | Supabase (Postgres + pgvector) | **Manually.** By hand in the SQL editor | Migrations in `supabase/migrations/` |

**A merge is not a deploy.** Two of the three above need a human, and the first
version of this table did not say so — which is how #18 merged and production
ran without `trace` for a while afterwards, with everyone assuming `master` was
live. If you have merged something that touches the backend, it is not in front
of a user until someone clicks deploy.

**Config that exists only in a dashboard.** These are not in the repo and cannot
be inferred from it:

- `VITE_API_BASE_URL` — set in **Vercel**. The `.env` files in `frontend/` point
  at `http://localhost:8000`, so production depends entirely on this being right.
- `AUDIT_HASH_PEPPER` — set in **Render**. Without it the audit log's message
  digest is a bare SHA-256, which is reversible for anything low-entropy. Changing
  it makes existing digests uncorrelatable with new ones, so treat rotation as
  deliberate.
- Provider keys (`GROQ_API_KEY`, `GEMINI_API_KEY`, `SARVAM_API_KEY`,
  `SUPABASE_*`) — in **Render**, and in your local `backend/.env`, which is
  gitignored.

**Keeping the backend awake** is delegated to an external uptime pinger hitting
`/health` every 5 minutes — see the reasoning in `.github/workflows/keep-alive.yml`
for why it is not a GitHub Actions schedule. If a request takes ~45s, that pinger
has stopped working.

### After merging a backend change

In this order. The order is the whole point: the code assumes the schema, so a
deploy that lands before its migration fails every request that touches the new
column. #18 was explicit about this — it wrote `scans.trace`, and deploying it
against an unmigrated database would have failed **every scan**.

1. **Migration first, if there is one.** Open the SQL file under
   `supabase/migrations/`, run it in the Supabase SQL editor, and confirm it
   reports success. Migrations here are additive by convention, so this is safe
   to do before the code that uses them.
2. **Deploy the backend.** Render dashboard → the service → **Manual Deploy** →
   **Deploy latest commit**.
3. **Check it came up.** `curl https://raksha-ai-c5yu.onrender.com/health`
   should return `{"status":"ok"}`. A 40-50s response means it was asleep, not
   broken — but see the pinger note above.
4. **Verify the change is actually live.** `/openapi.json` is a useful
   fingerprint when the change touches a response model: after #18, `ScanResult`
   gained a `trace` field, which is how we confirmed the deploy rather than
   assuming it. For changes with no API-surface effect, run the thing you
   changed.

### After changing a provider or model id

Run the smoke check before assuming it works:

```bash
cd backend && python scripts/check_providers.py
```

It calls each rung once and distinguishes a dead model from a rate limit. A
retired model id is invisible to the test suite — that is how `gemini-1.5-flash`
sat dead in two separate files (#45, #56).

## 2. One-time machine setup

### Node 22.12.0 or newer

Check before anything else:

```bash
node --version
```

If it prints anything below **22.12.0**, stop and upgrade — the frontend will not
start. Vite 8, rolldown, oxlint and `@vitejs/plugin-react` all require
`^20.19.0 || >=22.12.0`, and `@supabase/supabase-js` requires `>=22.0.0`, so
22.12.0 is the real floor. On an older Node, `npm install` only warns
(`EBADENGINE`) and appears to succeed, then `npm run dev` dies with
`SyntaxError: ... does not provide an export named 'styleText'`. That is the
version mismatch, not a broken dependency.

With [nvm-windows](https://github.com/coreybutler/nvm-windows) or
[nvm](https://github.com/nvm-sh/nvm):

```bash
nvm install 22.12.0
nvm use 22.12.0
```

If you switch Node *after* having installed the frontend deps, delete
`frontend/node_modules` and install again. rolldown ships native binaries built
per Node ABI, so a stale `node_modules` keeps failing even on a correct version.

### Shared skill set

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
| **Pavan** `@CODER7657` | Architecture, detection core, security, migrations, **content + QA + evaluation** | Persist retrieval evidence, then the labelled benchmark |
| **Hem** `@Hem60` | Frontend — web app, design system, accessibility | Trace viewer UI, then the institution dashboard |
| **Ayush** `@Ayush3422` | Voice, language, Android client | Android shell + SMS auto-scan — the first real interception |

**Content, QA and evaluation sit with Pavan for now.** A fourth contributor may
pick it up later.

**On the benchmark:** it is not busywork. Right now we cannot state a precision or
recall figure, which means every accuracy claim we make is unsupported — a jury
already asked and we had no number. Nothing else on the roadmap can be defended
until it exists, which is why it sits in P0 next to the traceability work.

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

When you come to ship the Android app rather than deploy the web one, that is a
different process and it has its own document:
[`docs/RELEASE.md`](docs/RELEASE.md). §1b above is a deploy; a release has a
store review in the middle of it and a signing key that cannot be lost.

Ask in the group before guessing. A five-minute question is cheaper than a
rejected PR.
