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
- **Explainability** — highlights the exact phrases that triggered the scam flags (judges love this for "Technical Accuracy")
- **History dashboard** — past scans, trend of scam types seen in the user's area (aggregate, anonymized)

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
| Database | Supabase free tier (Postgres + Auth) | 500MB DB, free auth, generous limits |
| Deployment | Frontend → **Vercel** · Backend → **Render** | Both free tiers, auto-deploy from GitHub on every push to `master` |
| CI | GitHub Actions | Free for public repos |

**Note on Render free tier**: the backend spins down after ~15 min of inactivity and takes ~30-60s to
wake on the next request. For the live demo, hit the backend URL a minute before presenting so it's warm.

## Repo Structure
```
raksha-ai/
├── frontend/          # React + Tailwind app (owned by frontend teammate)
├── backend/           # FastAPI service, scam-detection logic, LLM integration
├── docs/              # Pitch deck, architecture diagram, demo script
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
