# Contributing to Raksha AI

Four of us, one private repo. This doc is the whole process.

## 1. Team and ownership

| Person | GitHub | Owns | Why |
|---|---|---|---|
| **Pavan Patel** | `@CODER7657` | Tech lead, architecture, detection core (RAG, prompts, rules), security, migrations | Accuracy and auth are the two places a mistake is not recoverable |
| **Hem Patel** | `@Hem60` | Frontend — web app, UI, design system, accessibility | Owns everything a user actually sees |
| **Ayush Bawaskar** | `@Ayush3422` | Voice and language — STT/TTS, i18n, language directives | Built the Sarvam/Whisper ladder and the language layer |
| **Harsh Pansuriya** | `@harshpansuriya71-sudo` | Content and QA — scam pattern curation, practice bank, test coverage | Wrong content teaches people the wrong thing; this is a safety role, not a chore |

Ownership is enforced by `.github/CODEOWNERS` — GitHub auto-requests the right
reviewer. It means *accountable for reviewing*, not *only one allowed to edit*.

## 2. Branching — we do NOT fork

The repo is **private**. Forking a private repo does not work for collaborators,
so everyone works on branches **inside this repo**.

```bash
git checkout master
git pull origin master
git checkout -b feat/android-sms-listener
# ...work...
git add <specific files>          # never `git add .` blindly
git commit -m "Add SMS listener that auto-scans incoming messages"
git push -u origin feat/android-sms-listener
```

Then open a PR into `master`.

**Branch naming**
- `feat/<short-desc>` — new capability
- `fix/<short-desc>` — bug fix
- `chore/<short-desc>` — deps, config, cleanup
- `docs/<short-desc>` — documentation only

## 3. PR rules

- **Every PR needs one review** from another member, even for small changes.
- CI must be green before merge.
- **Squash and merge.** Keeps `master` readable.
- Delete the branch after merging.
- Never push directly to `master`.
- Never `--force` push to a shared branch.

## 4. Changes that need extra care

Some paths carry more risk than others. For these, say in the PR description
*how you verified it*, not just what you changed:

| Area | Why it is risky | What to state in the PR |
|---|---|---|
| `services/rag.py`, `llm.py`, prompts | Silently degrades detection accuracy | Which messages you tested, in which languages |
| `core/auth.py`, `core/config.py` | A mistake is a data breach | How you confirmed auth still rejects bad tokens |
| `supabase/migrations/` | Irreversible against production data | The rollback plan |
| `practice_content.py`, seed patterns | Teaches users the wrong instinct | Who reviewed the language |

## 5. Secrets

- **Never commit `.env`.** Both `frontend/.env*` and `backend/.env` are gitignored.
- Copy from `.env.example` and fill in your own.
- Shared keys live in the Render/Vercel dashboards, never in code, issues or PR comments.
- If you ever commit a key by accident: rotate it first, then clean history. Rotating
  is the fix; deleting the commit is not.

## 6. Running locally

```bash
# Backend
cd backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload            # http://localhost:8000

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Point `frontend/.env.local` at `http://localhost:8000` for local work, or at the
deployed backend to test against production data.

## 7. Keeping the deployed backend awake

Render's free tier sleeps after ~15 minutes idle and takes ~40-50s to wake.
Because this repo is private, GitHub Actions cannot do the pinging — a
5-minute schedule would cost ~8,640 minutes/month against a 2,000-minute quota.

Use an **external uptime pinger** instead (UptimeRobot free tier, 5-minute
interval, no cost) hitting:

```
https://raksha-ai-c5yu.onrender.com/health
```

There is also a manual `workflow_dispatch` in `.github/workflows/keep-alive.yml`
to warm it on demand before a demo.

## 8. Definition of done

- [ ] Works against the deployed backend, not just localhost
- [ ] Tested in English **and** at least one Indic language
- [ ] No console errors on the happy path
- [ ] Degrades gracefully when the network or a provider fails
- [ ] Docs updated if you changed the API contract
