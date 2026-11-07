# Raksha AI 🛡️

**A scam detector for first-time digital banking users in India.** Paste an SMS, WhatsApp
message, email or UPI ID, or record a call. Raksha tells you how risky it is and why, and
what to do next, in English, Hindi or Gujarati.

**Live:** [frontend-one-sage-77.vercel.app](https://frontend-one-sage-77.vercel.app) ·
API [raksha-ai-api.vercel.app/health](https://raksha-ai-api.vercel.app/health)

> New contributor? Start with [START-HERE.md](START-HERE.md), then
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Numbers

Measured on 2026-11-06 unless a different date is given.

| | |
|---|---|
| Backend tests | **949 passing**: 530 test functions in 41 files, about 10 s run |
| Android unit tests | **83** in 12 files, run in CI |
| Frontend build-env tests | **13** |
| Offline rules, en/hi/gu | **48/48 scams caught**; 3 false alarms in 22 benign messages (precision 0.94) |
| LLM benchmark (2026-08-16) | 79 held-out cases, 0 leaked into the prompt: **recall 1.000, precision 0.946** |
| Rules | 56 across 11 language tables. Marathi borrows Hindi's through the shared script |
| Threat feeds | 16,097 URLhaus + 300 OpenPhish URLs, stored only as SHA-256 digests |
| API | 21 routes · 13 web pages · 13 SQL migrations · 9 CI workflows |
| Cost | ₹0: every service runs on a free tier |

The LLM benchmark ran on `llama-3.3-70b-versatile`. Production now uses `openai/gpt-oss-120b`,
and it has not been re-benchmarked. Ground truth is
[`testdata/rule_corpus.jsonl`](testdata/rule_corpus.jsonl): 88 labelled messages, 57 scams and 31 benign.

## How a scan works

```
message ─► [1] offline rules       instant; this result alone is returned if every LLM is down
        ─► [2] link checks         typosquats, domain age, known-bad feed digests
        ─► [3] RAG retrieval       gemini-embedding-001 (768-dim) → pgvector top-k known scams
        ─► [4] LLM verdict         Groq gpt-oss-120b, falls back to Gemini 3.6 Flash, grounded on [3]
        ─► [5] result + trace      risk 0–100, flagged phrases, plain-language reason, safe next step
```

Every verdict carries a trace of which rules fired, which patterns were retrieved and which
model answered, so you can check the "why".

## What it does

- **Scan** text, email, voice notes and UPI IDs. Speech-to-text uses Sarvam, with faster-whisper as fallback.
- **Read the verdict aloud** with Sarvam, Google or ElevenLabs TTS. If none of them works, the browser's own voice is used.
- **Chat** with a scam-safety assistant that stays on topic and grounds its answers on the same pattern base.
- **Practice mode:** a 12-item "Scam or Safe?" game. Each of en, hi and gu has its own version, written separately rather than translated.
- **Campaign radar:** groups reports into scam campaigns using aggregate data only, never message text.
- **Android app** (minSdk 24, target 37):
  - scans incoming SMS on the device, with no network call in the app code
  - screens calls without blocking them: it only notifies, by design
  - accepts shared text from other apps
- **Self-improving loop:** agents red-team the rules and draft new patterns. A person approves every draft before it ships.

## Languages

**Supported: English, Hindi and Gujarati.** For these three, a speaker has read every rule.

Rules also exist for 9 more codes: mr, bn, ta, te, kn, ml, pa, or and ur. Each of those has only
2 corpus cases, so they are not claimed. When a verdict comes from an unreviewed language, the app
says so. The per-language state is `REVIEW_STATUS` in
[`rule_engine.py`](backend/app/services/rule_engine.py), and
[docs/RULE-PARITY.md](docs/RULE-PARITY.md) explains it.

## Security

- **Token checks:** the backend verifies every JWT itself (JWKS ES256/RS256, or legacy HS256)
  and never trusts a user ID sent by the client. The algorithm comes from the key, not from the token.
- **Row Level Security:** turned on for every user-data table. The service-role key exists only on the backend.
- **CORS and rate limits:** CORS allows only listed origins. Rate limits are 10 scans, 15 chats and 20 TTS calls per minute.
- **Privacy:** threat feeds keep URL digests, never URLs. API keys live in git-ignored `.env` files, and GitGuardian scans every PR for secrets.

## Stack

| Layer | Choice |
|---|---|
| Web | React 19 + Vite + TypeScript + Tailwind, hosted on **Vercel** |
| API | FastAPI (Python 3.12), a **Vercel** Python function in Mumbai (`bom1`) |
| Data, auth, vectors | **Supabase**: Postgres, pgvector, and Auth with email and Google sign-in |
| LLM | Groq first, Gemini as fallback |
| Android | Kotlin, with the rule engine as a plain JVM module (`:core:rules`) |
| CI | GitHub Actions: tests, lint, build, APK, deploy |

**Free-tier upkeep:**
- **API:** a serverless function, so there is no instance to keep awake. Voice falls back to Groq's hosted Whisper, so no speech model runs in the function.
- **Supabase:** pauses after 7 days idle, so a workflow queries it every 3 days.
- **Threat feeds:** refreshed daily and land as a PR.
- **Setup:** dashboard steps are in [docs/DEPLOY-CHECKLIST.md](docs/DEPLOY-CHECKLIST.md).

## Run it

```bash
cd backend && cp .env.example .env && pip install -r requirements-dev.txt && pytest -q
```
```bash
cd frontend && cp .env.example .env.local && npm ci && npm run dev
```

Fill in the `.env` files first. The frontend refuses to start without a valid `VITE_API_BASE_URL`
and Supabase config. Apply [`supabase/migrations/`](supabase/migrations) in filename order, then
seed the RAG base with `python -m scripts.seed_scam_patterns`. More detail is in
[backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

```
backend/    FastAPI app, rule engine, RAG, agents, 41 test files
frontend/   React app, 13 pages
android/    SMS + call screening app, on-device rules
supabase/   13 SQL migrations (schema, RLS, RAG functions)
testdata/   labelled corpora shared by Python and Kotlin tests
docs/       architecture, rule parity, deploy checklist
```
