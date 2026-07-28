# Contributing to Raksha AI

Two of us, moving fast. This doc is the whole process — follow it and we never block each other or overwrite each other's work.

## 1. Branch naming
- `frontend/<short-desc>` — e.g. `frontend/scan-input-screen`
- `backend/<short-desc>` — e.g. `backend/scam-classifier-endpoint`
- `fix/<short-desc>` — bug fixes on either side
- Never commit directly to `master`. `master` is always the deployable branch.

## 2. Daily flow
```bash
git checkout master
git pull origin master
git checkout -b frontend/your-feature-name   # or backend/...
# ...work...
git add <specific files>       # never `git add .` blindly — check `git status` first
git commit -m "Add scan input screen with language selector"
git push -u origin frontend/your-feature-name
```
Then open a PR on GitHub into `master`. Fill out the PR template (it auto-loads).

## 3. PR & merge rules
- Every PR needs **1 review from the other person** before merge — even though we're a 2-person team. Catches bugs and keeps both of us aware of the whole codebase.
- CI (GitHub Actions) must be green before merge — it lints and builds automatically on every PR.
- Use **Squash and merge** (keeps `master` history clean and readable for judges).
- Delete the branch after merging (GitHub button does this automatically).
- If your PR only touches `frontend/**` or only `backend/**`, CI only runs the relevant workflow — fast feedback.

## 4. Keeping in sync
- Pull `master` before starting new work every session: `git pull origin master`
- If your branch falls behind: `git checkout your-branch && git pull origin master --rebase`
- If you hit a merge conflict, do NOT force-push over the other person's work. Resolve conflicts locally, test, then push normally.

## 5. Environment variables & secrets
- **Never commit `.env` files or API keys.** Both `frontend/.env` and `backend/.env` are already git-ignored.
- Each of us keeps our own local `.env` (copy from `.env.example`).
- Shared secrets (LLM API keys, Supabase keys) go in **Vercel/Render dashboard env vars** for deployed environments — message them in chat, never paste into a commit, issue, or public PR comment.

## 6. What NOT to do
- Don't `git push --force` to `master`, ever.
- Don't merge your own PR without a review unless it's a genuine emergency 1 hour before deadline — then message the other person first.
- Don't install random new dependencies without a quick heads-up (keeps bundle size / build time sane for a hackathon deploy).
- Don't hardcode API keys anywhere in source — always `process.env` / `os.environ`.
- Don't rewrite the API contract in `frontend/README.md` without updating `backend/README.md` in the same PR (or pinging the other person) — that contract is the thing keeping us unblocked from each other.

## 7. Definition of done (for demo readiness)
- [ ] Deployed URL works end-to-end (not just localhost)
- [ ] Works in at least Hindi, Gujarati, and English (our 3 demo languages)
- [ ] No console errors on the happy path
- [ ] README has an up-to-date "How to run" section
- [ ] For any hero/landing/above-the-fold change: the primary CTA is visible **without scrolling** at 667px height (iPhone SE — our shortest common target) and 720px (common laptop). See §8 for why this matters and how to check it in 10 seconds.

## 8. Above-the-fold check (don't ship a hero that needs a scroll)
We shipped a regression once where enlarging the hero pushed the CTA button below the fold —
you had to scroll to even see the "Get started" button on first load. Root cause was stacking
too much vertical padding/heading size without checking against a real viewport height.

Before merging any change to the Landing page hero, paste this into the browser console
(devtools, on the running page) — it tells you immediately if something's off-screen:
```js
(function() {
  const btn = [...document.querySelectorAll('a')].find(a => a.textContent.includes('Get started'));
  const rect = btn?.getBoundingClientRect();
  console.log({ innerHeight: window.innerHeight, btnBottom: rect?.bottom, fits: rect ? rect.bottom <= window.innerHeight : 'button not found' });
})()
```
`fits` must be `true`. Check it at both 667px and 720px window heights (browser devtools → toggle
device toolbar, or just resize the window). If a change makes the hero taller, either tighten the
padding/heading size or accept the scroll deliberately — don't let it happen by accident.
