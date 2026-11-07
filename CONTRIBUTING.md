# Contributing to Raksha AI

Three of us, one private repo. This doc is the whole process.

## 1. Team and ownership

| Person | GitHub | Owns | Why |
|---|---|---|---|
| **Pavan Patel** | `@CODER7657` | Tech lead, architecture, detection core (RAG, prompts, rules), security, migrations — **and** content, QA and evaluation | Accuracy and auth are the two places a mistake is not recoverable |
| **Hem Patel** | `@Hem60` | Frontend — web app, UI, design system, accessibility | Owns everything a user actually sees |
| **Ayush Bawaskar** | `@Ayush3422` | Voice and language — STT/TTS, i18n, language directives, Android client | Built the Sarvam/Whisper ladder and the language layer |

> **Content, QA and evaluation** — scam patterns, practice bank, accuracy benchmark —
> sit with the lead for now. A fourth contributor may pick this up later; until then
> treat it as owned, not unowned. It is the work that lets every accuracy claim be
> defended.

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
- CI is visible but not a required check — **do not approve a PR with red CI.**
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
- Shared keys live in the Vercel dashboards, never in code, issues or PR comments.
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

## 7. Deploying the backend

Merging to `master` deploys it (`.github/workflows/backend-deploy.yml`) as a
Vercel function at `https://raksha-ai-api.vercel.app`. There is nothing to keep
awake. Apply any migration **before** merging; see `START-HERE.md`.

## 8. Definition of done

- [ ] Works against the deployed backend, not just localhost
- [ ] Tested in English **and** at least one Indic language
- [ ] No console errors on the happy path
- [ ] Degrades gracefully when the network or a provider fails
- [ ] Docs updated if you changed the API contract
- [ ] If you touched the hero or landing layout: the CTA still fits above the fold (below)

### Does the CTA still fit above the fold?

#12 was a hero that grew — bigger heading, more padding, a stat row — until "Get
started" sat at 714px on a 694px viewport. Nobody noticed, because it looks fine
on the machine it was built on. Everything about that is easy to repeat, so
measure instead of eyeballing.

Load the landing page, set the window to your shortest target, and paste this:

```js
const cta = [...document.querySelectorAll('a,button')]
  .find(e => /get started/i.test(e.textContent || ''))
const { top, bottom } = cta.getBoundingClientRect()
console.log({
  viewport: innerHeight,
  ctaTop: Math.round(top),
  fits: bottom <= innerHeight,
  slack: Math.round(innerHeight - bottom),
})
```

Check these three, not just the one your machine happens to be:

| viewport | why |
|---|---|
| `360 × 640` | low-end Android with browser chrome showing — what most of our users hold |
| `667 × 375` | **the same phone rotated.** Tailwind's `sm:` fires on *width*, so landscape hands a 375px-tall window desktop typography |
| `1280 × 800` | that the shrink did not follow you up to desktop |

Landscape is the one people skip, and it is the one that broke. The first pass
at #12 measured portrait and desktop, called it fixed, and missed a 217px
overflow sitting in the middle of the range.

`fits: false` is a blocker, and so is single-digit slack: it means the next
small copy change breaks it again.

If the hero needs to shrink on short viewports, use the `short:` variant
(`@custom-variant short` in `index.css`) rather than another width breakpoint.
Height is the thing you are actually responding to.

This is a manual check because the frontend has no test runner yet. When one
lands, this belongs in it — a checklist item only works while people remember
to read the checklist.
