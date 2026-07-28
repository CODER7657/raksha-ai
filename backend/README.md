# Raksha AI — Backend

FastAPI service: RAG-grounded scam detection, JWT-authenticated, rate-limited.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
cp .env.example .env              # fill in Supabase + Groq/Gemini keys
uvicorn main:app --reload
```

Then apply the schema (Supabase SQL editor → paste `supabase/migrations/0001_init.sql` → run),
and seed the RAG knowledge base:
```bash
python -m scripts.seed_scam_patterns
```

## Architecture
```
app/
├── core/
│   ├── config.py           # env-driven settings (pydantic-settings)
│   ├── auth.py              # verifies Supabase JWT on every protected route
│   └── supabase_client.py   # server-side Supabase client (service role key)
├── services/
│   ├── embeddings.py        # multilingual embeddings via Gemini's free embedding API
│   ├── rag.py                # retrieval: pulls similar known scam patterns before classifying
│   ├── llm.py                 # Groq (primary) + Gemini (fallback), grounded by RAG context
│   ├── rule_engine.py        # offline keyword fallback if both LLMs are down
│   └── upi_check.py          # UPI ID / link typosquatting checker, LLM-independent
├── routes/
│   ├── scan.py                # POST /api/scan/text, GET /api/history
│   └── upi.py                  # POST /api/check-upi
└── rate_limit.py             # shared slowapi limiter
main.py                        # app entrypoint: CORS, rate limiter, routers, /health
```

## How RAG works here
1. User's message gets embedded via Gemini's free embedding API (`services/embeddings.py`).
2. We look up the top-k most similar entries in `scam_patterns` (pgvector, Supabase) via the
   `match_scam_patterns` SQL function.
3. Those retrieved patterns are injected into the LLM prompt as grounding context
   (`services/rag.py::format_context_block`).
4. The LLM (`services/llm.py`) classifies the *actual* message, using the retrieved patterns as
   reference — not just pattern-matching, but not an ungrounded guess either.

This is what should be described in the pitch/demo as "RAG-grounded classification" — it's a real
retrieval step against a real vector store, not just prompt engineering.

## Auth model
- Frontend authenticates directly against Supabase Auth (email/password + Google OAuth) and gets a JWT.
- Every backend request carries that JWT in `Authorization: Bearer <token>`.
- `core/auth.py::get_current_user` independently verifies the JWT signature — the backend never
  trusts a client-supplied user id.
- Postgres Row Level Security (see `supabase/migrations/0001_init.sql`) is the second, independent
  layer: even if a route ever queried without filtering by user_id, a user still can't read another
  user's `scans` rows.

## Security / no-loopholes checklist
- [x] JWT verified server-side on every protected route (not just checked for presence)
- [x] Row Level Security enabled on all user-data tables
- [x] Service role key stays backend-only (never in frontend env vars)
- [x] CORS locked to explicit origins from `ALLOWED_ORIGINS`, no wildcard
- [x] Rate limiting on the scan endpoint (protects free LLM quota + basic DoS resistance)
- [x] Pydantic input validation (length limits, enum-restricted language codes)
- [x] Offline fallback if both LLM providers fail, instead of a raw 500
- [x] `/health` endpoint for Render + pre-demo warmup pings
- [ ] TODO before final submission: add `pip-audit`/`npm audit` to CI, add structured request logging

## Endpoints
- `POST /api/scan/text` — auth required, rate-limited. `{ text, language }` → risk report
- `POST /api/scan/audio` — auth required, rate-limited. Multipart: `file` (audio, ≤10MB, mp3/mp4/wav/webm/ogg) + `language` query param → transcribed via `faster-whisper` (local, free, CPU), then same risk report + `transcript` field
- `GET /api/history` — auth required. Returns the caller's own scans only
- `POST /api/check-upi` — auth required. `{ value }` → typosquatting check, independent of LLM
