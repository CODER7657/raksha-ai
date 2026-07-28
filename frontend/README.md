# Raksha AI — Frontend

React (Vite) + TypeScript + Tailwind CSS.

## Setup
```bash
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install @supabase/supabase-js react-router-dom react-i18next i18next
cp .env.example .env.local        # fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm run dev
```

Auth/API scaffolding already exists — don't rebuild these, build on top of them:
- `src/lib/supabaseClient.ts` — Supabase client (uses the public anon key, safe to expose)
- `src/context/AuthContext.tsx` — `useAuth()` hook: `user`, `signInWithPassword`, `signUpWithPassword`, `signInWithGoogle`, `signOut`
- `src/components/ProtectedRoute.tsx` — wrap any route that needs login
- `src/lib/api.ts` — `apiFetch(path, options)`, auto-attaches the auth token to every backend call

## Screens to build (see main repo README / Figma link in #design channel)
1. **Landing / Hero** — what Raksha AI does, "Paste a message" CTA, trust-building visuals
2. **Login / Signup** — email+password and "Continue with Google", plus a password-reset link. Wire to `useAuth()`, don't hand-roll auth logic
3. **Scan Input** — text paste box + voice upload/record + language selector (12 languages, see main README)
4. **Result / Risk Report** — risk score (Safe/Suspicious/High Risk), highlighted red-flag phrases, plain-language explanation, "what to do next" action card, speaker icon (TTS read-aloud), "Forward to family" share card button
5. **History Dashboard** — list of past scans, simple trend chart of scam types, "Community Scam Radar" counter widget
6. **Practice / Simulator** — quiz-style scam-spotting mini-game (unique feature, see main README)
7. **About / How it works** — builds credibility for judges + demo narration

All screens except Landing/Login are behind `ProtectedRoute` — logged-out users always land on Login.

## API contract (implemented — build against these exact shapes)
- `POST /api/scan/text` — JSON `{ text, language }` → `{ risk_score, verdict, flagged_phrases[], explanation, recommended_action, community_report_count, offline_flags_matched, transcript: null }`
- `POST /api/scan/audio` — multipart form: `file` (audio blob, ≤10MB) + `language` query param → same shape as above, with `transcript` populated
- `GET /api/history` → array of past scan rows for the logged-in user
- `POST /api/check-upi` → `{ value }` → `{ is_upi, is_suspicious, reasons[] }`
- `GET /api/simulator/questions?language=` → not yet implemented — stub with local mock data for now, ping Issue #3 when you're ready to build this screen and I'll prioritize it

All routes require `Authorization: Bearer <token>` — use `apiFetch()`, it's handled for you.

## i18n setup
Use `react-i18next` with one JSON file per language under `frontend/src/locales/<lang-code>/`
(`en`, `hi`, `gu`, `mr`, `bn`, `ta`, `te`, `kn`, `ml`, `pa`, `or`, `ur`). Start with `en`, `hi`, `gu`
fully translated for the demo; the rest can be thinner/LLM-assisted since they're a scalability
talking point, not a demo requirement.

## Design system
- Mobile-first, but must look great on desktop for the judging demo
- Keep it warm/trustworthy (not "hacker/dark" aesthetic) — target audience is non-technical, first-time digital users
- Use real Indian language sample text in mockups (Hindi/Gujarati), not lorem ipsum
- Support right-sized text for Urdu (RTL) if time allows — not a blocker for MVP
