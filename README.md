# Raksha AI 🛡️
### Financial Safety Assistant for Rural & First-Time Digital Banking Users

Built for **The Maverick Effect AI Challenge** (GTU × Dewang Mehta Foundation Trust × Harish Mehta / NASSCOM spirit).

## Problem
First-time digital banking users in India are prime targets for scam calls, fake UPI payment requests,
phishing messages, and fraudulent loan offers — often in their local language, where most fraud-detection
tools don't help at all.

## Solution
Raksha AI lets a user paste/forward a suspicious SMS, WhatsApp message, UPI request, or upload/record a
call snippet. It analyzes the content (in English + regional Indian languages), flags scam patterns,
explains *why* it's risky in plain language, and gives a safe next action — all in under a few seconds.

## Core Features (MVP)
- **Text/message scan** — paste any SMS/WhatsApp/email text → risk score + red flags + plain-language explanation
- **Voice/call scan** — upload or record a call snippet → transcribed (speech-to-text) → same scam analysis
- **Multilingual** — 12 languages, input and output (see below)
- **RAG-grounded classification** — every message is checked against a real vector database of known
  scam patterns before the LLM judges it, so results are grounded in retrieved evidence, not a raw
  model guess (see [Architecture](#architecture--how-rag-works))
- **Explainability** — highlights the exact phrases that triggered the scam flags (judges love this for "Technical Accuracy")
- **Login required, data is yours only** — Supabase Auth (email + Google) + Postgres Row Level Security,
  so your scan history is never visible to anyone else, including other logged-in users
- **History dashboard** — past scans, trend of scam types seen in the user's area (aggregate, anonymized)

## Architecture / how RAG works
```
User message
   │
   ▼
[1] Offline rule-engine pre-check (instant, no network — catches obvious cases)
   │
   ▼
[2] Embed message locally (sentence-transformers, multilingual, free, no API call)
   │
   ▼
[3] Vector similarity search against `scam_patterns` (Postgres + pgvector, Supabase)
   │      → top-k most similar known scams retrieved
   ▼
[4] LLM classification (Groq primary, Gemini fallback), prompted WITH the retrieved
   │  patterns as grounding context — not just "guess if this is a scam"
   ▼
[5] Structured result: risk score, verdict, flagged phrases, plain-language explanation,
      recommended action → saved to the user's own scan history (RLS-protected)
```
Full detail in [`backend/README.md`](./backend/README.md#how-rag-works-here) and the schema in
[`supabase/migrations/0001_init.sql`](./supabase/migrations/0001_init.sql).

## Auth & Security — no loopholes
- **Login**: Supabase Auth, email+password and Google OAuth. Every screen except Landing/Login is
  behind a protected route.
- **Every backend request is independently verified** — the API never trusts a user id sent by the
  client, it verifies the JWT signature itself (`backend/app/core/auth.py`).
- **Row Level Security** on every user-data table — a user can only ever read their own scan history,
  enforced at the database layer, not just in application code.
- **Service role key never leaves the backend** — the frontend only ever holds the public anon key.
- **CORS locked to explicit origins**, no wildcard.
- **Rate limiting** on the scan endpoint — protects the free LLM API quota from being drained by abuse.
- **Input validation** (length limits, restricted language codes) on every request body.
- **Graceful degradation** — if both LLM providers are down, the offline rule-engine still returns a
  conservative result instead of a bare error.
- Full checklist: [`backend/README.md`](./backend/README.md#security--no-loopholes-checklist)

## Supported Languages
English, Hindi, Gujarati, Marathi, Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi, Odia, Urdu.
(Demo will focus on **English, Hindi, Gujarati** — the rest come free from the same LLM prompt-based
translation layer, so listing all 12 is a legitimate "scalability" talking point without extra build cost.)

## Unique / Out-of-the-Box Features
These are what differentiate us from a plain "paste text, get a label" classifier:

1. **Speaks the verdict back to you** — free browser Text-to-Speech reads the risk explanation aloud
   in the user's language. Built for low-literacy users, zero backend cost (`window.speechSynthesis`).
2. **Community Scam Radar** — every scan (anonymized) increments a live counter of scam patterns seen
   recently, shown as "This exact scam has been reported N times this week." Turns individual scans into
   a shared early-warning signal — strong "societal impact / scalability" story for judges.
3. **Scam Simulator (practice mode)** — a short quiz of real (defanged) scam messages where the user
   guesses the red flags before we reveal them. Builds lasting digital literacy, not just one-off detection.
4. **Forward-to-Family safety card** — one tap turns a scan result into a shareable WhatsApp-ready
   image/text card, so a user can warn an elderly parent/relative directly — extends reach beyond the app's own users.
5. **UPI ID / link lookalike checker** — detects typosquatted UPI handles and phishing domains
   (e.g. `paytm-refund.info` vs `paytm.com`) using pattern-matching, independent of the LLM call —
   works even if the AI service is down.
6. **Offline-first fallback** — a small bundled keyword/pattern dictionary flags obvious scams
   client-side with zero network call, before falling back to the LLM for nuanced cases. Matters for
   rural/low-bandwidth users, which is the whole point of the problem statement.

## Tech Stack — 100% Free Tier, $0 to Ship
| Layer | Choice | Why it's free |
|---|---|---|
| Frontend | React (Vite) + TypeScript + Tailwind CSS | Vercel free plan (hobby) |
| Backend | FastAPI (Python) | Render free web service |
| AI/NLP (LLM) | **Groq API** (Llama 3.3 70B) as primary, **Google Gemini API** free tier as backup | Both have generous free-forever developer tiers, fast inference, strong Indian-language support |
| Speech-to-Text | Browser **Web Speech API** for live recording (free, no server cost) + `faster-whisper` (open-source, self-hosted) for uploaded audio files | No paid STT API needed |
| Text-to-Speech | Browser `speechSynthesis` API | Free, built into every modern browser |
| Database + Auth + Vector store | Supabase free tier (Postgres + pgvector + Auth) | 500MB DB, free auth, generous limits, pgvector included at no extra cost |
| Deployment | Frontend → **Vercel** · Backend → **Render** | Both free tiers, auto-deploy from GitHub on every push to `master` |
| CI | GitHub Actions | Free for public repos |

**Note on Render free tier**: the backend spins down after ~15 min of inactivity and takes ~30-60s to
wake on the next request. For the live demo, hit the backend URL a minute before presenting so it's warm.

## Repo Structure
```
raksha-ai/
├── frontend/          # React + Tailwind app (owned by frontend teammate)
├── backend/           # FastAPI service: RAG pipeline, LLM integration, auth, rate limiting
├── supabase/
│   └── migrations/    # DB schema: scans, scam_patterns (pgvector), RLS policies, RAG SQL functions
├── docs/              # Figma link, pitch deck, architecture diagram, demo script
└── README.md
```

## Team
- **Frontend & UI/UX**: [teammate]
- **Backend, AI/ML, Infra, Deployment**: [you]

## Getting Started
See [`frontend/README.md`](./frontend/README.md) and [`backend/README.md`](./backend/README.md).

## Contributing / Git workflow
Read [`CONTRIBUTING.md`](./CONTRIBUTING.md) before your first PR — branch naming, review rules,
env var handling, and what not to do. CI runs automatically via GitHub Actions on every PR.

## Roadmap / Stretch Goals
- WhatsApp bot integration (Twilio/WhatsApp Cloud API) for real-world reach without needing an app install
- On-device lightweight classifier for offline/low-bandwidth fallback
- Community scam-alert feed (crowdsourced, moderated)
