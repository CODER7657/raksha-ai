# Raksha AI — Backend

FastAPI service for scam detection.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn python-multipart
uvicorn main:app --reload
```

## Planned modules
- `app/routes/scan.py` — `/api/scan/text`, `/api/scan/audio` endpoints
- `app/services/llm_classifier.py` — LLM-based scam classification + explanation
- `app/services/rule_engine.py` — offline fallback: known scam phrase/pattern matching (keyword lists per language)
- `app/services/transcribe.py` — Whisper-based speech-to-text
- `app/db/` — Supabase client, history persistence

## API contract
See [`frontend/README.md`](../frontend/README.md#api-contract) — keep in sync.
