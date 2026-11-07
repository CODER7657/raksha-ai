# Bringing the live deployment back

The code was fine. Every failure below was a dashboard or workflow setting,
verified on 2026-11-06. Repo-side fixes are on the `fix/live-deploy-config`
branch. The steps here need a dashboard and a person.

| Symptom | Cause | Fixed by |
|---|---|---|
| Every scan fails with HTTP 405 | Vercel's `VITE_API_BASE_URL` held the literal text `[SENSITIVE]`, so the bundle called `"[SENSITIVE]/api/scan/text"` on its own origin | Steps 2–3; the build now refuses this value |
| Sign-in can't work | `zqutlhwixrbanrokwjtl.supabase.co` gives NXDOMAIN, meaning the Supabase project is paused or deleted | Step 1 |
| "Refresh threat feeds" failed 35 times in a row | It pushed to protected `master` (GH006), and URLhaus retired keyless downloads (410 Gone) | Steps 5–6; the workflow now opens a PR |
| First request after idle took about 50 s | Render's free tier slept after 15 minutes | Step 4: the backend is now a Vercel function |

The backend is the Vercel project `raksha-ai-api` (`https://raksha-ai-api.vercel.app`),
deployed by `backend-deploy.yml`; it needs the environment in step 4 before it can start.

## 1. Supabase: restore it or replace it

Open <https://supabase.com/dashboard/projects>.

- **The project is listed as Paused:** click **Restore**. Supabase limits how long a paused
  free project stays restorable, so do it soon. The URL and keys stay the same, so
  skip to step 2 and reuse the old values. Check the old values are still the
  ones on both Vercel projects.
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

### Stop it pausing again

Supabase pauses a free project after 7 days with no activity. The
**Keep Supabase active** workflow (`.github/workflows/supabase-keep-alive.yml`)
reads one row of `scam_patterns` every 3 days, which costs about 10 Actions
minutes a month. It needs two repository secrets: GitHub → **Settings →
Secrets and variables → Actions**.

| Secret | Value |
|---|---|
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | Project Settings → API Keys: the **publishable** key (`sb_publishable_…`), or the legacy **anon** key under *Legacy API keys*. The same value Vercel uses. Never the secret or `service_role` key |

Then use **Actions → Keep Supabase active → Run workflow** once. A green run
shows `scam_patterns -> HTTP 200`. A red run names the problem: a missing
secret, a paused project, or a bad key. A yellow warning means the RAG seed
hasn't been run on this project.

## 2. Vercel environment variables

Go to Vercel → project → **Settings → Environment Variables**. Set each one
for **Production** and **Preview**:

| Name | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://raksha-ai-api.vercel.app`, with no trailing slash |
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
`https://raksha-ai-api.vercel.app/api/scan/text`.

## 4. Backend environment (Vercel project `raksha-ai-api`)

Go to Vercel → project **raksha-ai-api** → **Settings → Environment Variables**,
Production. Mark every key **Sensitive**. If the old Render service still
exists, its **Environment** page has the current values to copy.

| Name | Needed | Where it comes from |
|---|---|---|
| `SUPABASE_URL` | yes, or the function cannot start | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | yes, or the function cannot start | same page. Backend only, never the frontend |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | yes, for scans and voice | the providers' consoles |
| `AUDIT_HASH_PEPPER` | yes | the value already in use (changing it breaks correlation with old digests) |
| `AGENT_OPERATOR_IDS` | yes, or nobody can flip an agent kill switch | Supabase user ids, comma separated |
| `SUPABASE_JWT_SECRET` | only for legacy HS256 tokens | Project Settings → JWT |
| `SARVAM_API_KEY` | optional: better Gujarati speech; Groq Whisper is the fallback | Sarvam dashboard |
| `GROQ_API_KEY_BATCH`, `GEMINI_API_KEY_BATCH` | optional | separate quota for agent runs |
| `ALLOWED_ORIGINS` | already set | `https://frontend-one-sage-77.vercel.app` |

`backend/.env.example` lists the rest (TTS settings, rate limits); all have
defaults. Then **Actions → Backend deploy → Run workflow**: its last step fails
unless `/health` answers 200.

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

## 7. Nothing to keep warm

The backend moved from Render to a Vercel function (`backend-deploy.yml`), so
there is no idle instance to sleep and no pinger to run. If an UptimeRobot
monitor still points at the old Render URL, delete it along with the Render
service.
