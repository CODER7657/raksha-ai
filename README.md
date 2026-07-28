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
- **Multilingual** — Hindi/Gujarati (+ English) input and output
- **Explainability** — highlights the exact phrases that triggered the scam flags (judges love this for "Technical Accuracy")
- **History dashboard** — past scans, trend of scam types seen in the user's area (aggregate, anonymized)

## Tech Stack
| Layer | Choice | Why |
|---|---|---|
| Frontend | React (Vite) + TypeScript + Tailwind CSS | Fast, modern, easy to deploy on Vercel |
| Backend | FastAPI (Python) | Clean async API, great for AI/ML glue code |
| AI/NLP | LLM API (classification + explanation) + rule-based scam-pattern layer for offline fallback | Balances "Innovation" with reliability (no single point of failure) |
| Speech-to-Text | Whisper API (or open-source `faster-whisper`) | Regional language transcription |
| Database | Supabase (Postgres) | Auth + history storage, generous free tier |
| Deployment | Frontend → Vercel · Backend → Render | Free tier, fast CI/CD, matches team's stack choice |

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

## Roadmap / Stretch Goals
- WhatsApp bot integration (Twilio/WhatsApp Cloud API) for real-world reach without needing an app install
- On-device lightweight classifier for offline/low-bandwidth fallback
- Community scam-alert feed (crowdsourced, moderated)
