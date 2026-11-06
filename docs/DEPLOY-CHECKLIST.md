# Bringing the live deployment back

The code was fine. Every failure below was a dashboard or workflow setting,
verified on 2026-11-06. Repo-side fixes are on the `fix/live-deploy-config`
branch. The steps here need a dashboard and a person.

| Symptom | Cause | Fixed by |
|---|---|---|
| Every scan fails with HTTP 405 | Vercel's `VITE_API_BASE_URL` held the literal text `[SENSITIVE]`, so the bundle called `"[SENSITIVE]/api/scan/text"` on its own origin | Steps 2–3; the build now refuses this value |
| Sign-in can't work | `zqutlhwixrbanrokwjtl.supabase.co` gives NXDOMAIN, meaning the Supabase project is paused or deleted | Step 1 |
| "Refresh threat feeds" failed 35 times in a row | It pushed to protected `master` (GH006), and URLhaus retired keyless downloads (410 Gone) | Steps 5–6; the workflow now opens a PR |
| First request after idle takes about 50 s | Render's free tier sleeps after 15 minutes | Step 7 |

These already work and need nothing: the Render backend (`/health` → `{"status":"ok"}`)
and CORS for `https://frontend-one-sage-77.vercel.app`, checked with a preflight.

## 1. Supabase: restore it or replace it

Open <https://supabase.com/dashboard/projects>.

- **The project is listed as Paused:** click **Restore**. Supabase limits how long a paused
  free project stays restorable, so do it soon. The URL and keys stay the same, so
  skip to step 2 and reuse the old values. Check the old values are still the
  ones on Vercel and Render.
- **It isn't listed, or the restore window has passed:** create a new project
  (free tier, region `ap-south-1` Mumbai to sit near the users). Then:
  1. **Database → Extensions:** enable `vector`. `0001_init.sql` also runs
     `create extension`, so this is a check.
  2. **SQL Editor:** run every file in `supabase/migrations/` **in filename
     order**: `0001`, then `0003` … `0014`. There's no `0002` on master. It only
     exists on the unmerged `backend/chatbot-and-trends` branch, and nothing on
     master uses it. Or use the CLI: `supabase link --project-ref <ref>` then
     `supabase db push`.
  3. **Seed the RAG knowledge base**. Without it, retrieval returns nothing:
     ```bash
     cd backend && python -m scripts.seed_scam_patterns
     ```
     This needs `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `GEMINI_API_KEY`
     in the git-ignored `backend/.env`.
  4. **Authentication → URL Configuration:** set Site URL to
     `https://frontend-one-sage-77.vercel.app` and add the same URL under
     Redirect URLs.
  5. **Project Settings → API:** copy the values for steps 2 and 4.

Scan history doesn't come back with a new project. That is expected.

## 2. Vercel environment variables

Go to Vercel → project → **Settings → Environment Variables**. Set each one
for **Production** and **Preview**:

| Name | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://raksha-ai-c5yu.onrender.com`, with no trailing slash |
| `VITE_SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | the **anon / publishable** key. It's public by design, and RLS is the boundary |

Paste each real value. Don't copy a value back out of a variable marked
*Sensitive*: Vercel shows those as `[SENSITIVE]`, and that text is what got
deployed. Never put the service-role key here.

## 3. Redeploy the frontend

Pick one:

- Vercel → **Deployments** → latest → **⋯ → Redeploy**, with **Use existing
  Build Cache** unticked.
- GitHub → **Actions → Frontend deploy → Run workflow**.

Once this branch is merged, a bad value fails the build with a message such as
`VITE_API_BASE_URL is not an absolute URL (got "[SENSITIVE]")`, so a broken
deploy can't go live again.

To check the deploy, open the site, sign up, and scan a test SMS. In DevTools →
Network, the request should go to
`https://raksha-ai-c5yu.onrender.com/api/scan/text`.

## 4. Render environment (only for a new Supabase project)

Go to Render → service `raksha-ai` → **Environment**. Set these, then
**Save, rebuild and deploy**:

| Name | Where it comes from |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | same page. Backend only, never the frontend |
| `SUPABASE_JWT_SECRET` | Project Settings → JWT. Needed only for legacy HS256 tokens; new projects sign with JWKS, which the backend fetches from `SUPABASE_URL` |
| `ALLOWED_ORIGINS` | keep `https://frontend-one-sage-77.vercel.app` |

`backend/.env.example` lists every other variable, such as the LLM keys and
TTS settings. Those are unaffected.

## 5. Let the feed workflow open PRs

GitHub repo → **Settings → Actions → General → Workflow permissions**. Tick
**Allow GitHub Actions to create and approve pull requests**. It's currently
off, and the workflow can't open its PR without it. The workflow is built to
fail loudly and name this setting if it's still off.

Each run force-pushes the `bot/threat-feeds` branch and opens or updates one
PR. You merge it as admin. PRs opened by `GITHUB_TOKEN` don't trigger other
workflows, so CI won't run on them. That's fine: the PR only changes the hash
lists in `backend/data/feeds/`.

## 6. URLhaus key (optional but recommended)

Since 2026-10-21, abuse.ch only serves URLhaus to holders of a free Auth-Key.

1. Sign in at <https://auth.abuse.ch/> and copy your Auth-Key.
2. GitHub repo → **Settings → Secrets and variables → Actions → New repository
   secret**. Name it `URLHAUS_AUTH_KEY` and paste the key.
3. **Actions → Refresh threat feeds → Run workflow**. The log should show
   `urlhaus: N digests`. The script never prints the key: it removes it from
   every error message.

Without the key, URLhaus is skipped by name and OpenPhish still refreshes.

## 7. Keep the backend warm, for free

A scheduled GitHub Action won't work here. This repo is private, so it gets
2,000 Actions minutes a month, and each run bills a full minute. Render sleeps
after 15 minutes, so a useful ping is every ≤14 minutes, about 3,100 runs a
month. `tests/test_workflows.py` keeps `keep-alive.yml` manual-only for that
reason.

Use UptimeRobot's free tier instead:

1. <https://uptimerobot.com> → **New monitor** → HTTP(s).
2. URL: `https://raksha-ai-c5yu.onrender.com/health`. Interval: 5 minutes.

Render's free plan gives 750 instance-hours a month. One always-on service
uses about 744, so this fits, with nothing to spare for a second free service.
