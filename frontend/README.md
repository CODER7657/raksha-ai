# Raksha AI — Frontend

React (Vite) + TypeScript + Tailwind CSS.

## Setup
```bash
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm run dev
```

## Screens to build (see main repo README / Figma link in #design channel)
1. **Landing / Hero** — what Raksha AI does, "Paste a message" CTA, trust-building visuals
2. **Scan Input** — text paste box + voice upload/record + language selector (12 languages, see main README)
3. **Result / Risk Report** — risk score (Safe/Suspicious/High Risk), highlighted red-flag phrases, plain-language explanation, "what to do next" action card, speaker icon (TTS read-aloud), "Forward to family" share card button
4. **History Dashboard** — list of past scans, simple trend chart of scam types, "Community Scam Radar" counter widget
5. **Practice / Simulator** — quiz-style scam-spotting mini-game (unique feature, see main README)
6. **About / How it works** — builds credibility for judges + demo narration

## API contract (backend team owns implementation, agree on shape early)
- `POST /api/scan/text` → `{ text, language }` → `{ risk_score, verdict, flagged_phrases[], explanation, recommended_action, community_report_count }`
- `POST /api/scan/audio` → multipart file → same response shape as above
- `GET /api/history` → list of past scans for logged-in user
- `POST /api/check-upi` → `{ upi_id_or_link }` → `{ is_suspicious, reason }` (client-side pattern check can also run standalone as offline fallback)
- `GET /api/simulator/questions?language=` → list of quiz questions for Practice mode

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
