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
2. **Scan Input** — text paste box + voice upload/record + language selector
3. **Result / Risk Report** — risk score (Safe/Suspicious/High Risk), highlighted red-flag phrases, plain-language explanation, "what to do next" action card
4. **History Dashboard** — list of past scans, simple trend chart of scam types
5. **About / How it works** — builds credibility for judges + demo narration

## API contract (backend team owns implementation, agree on shape early)
- `POST /api/scan/text` → `{ text, language }` → `{ risk_score, verdict, flagged_phrases[], explanation, recommended_action }`
- `POST /api/scan/audio` → multipart file → same response shape as above
- `GET /api/history` → list of past scans for logged-in user

## Design system
- Mobile-first, but must look great on desktop for the judging demo
- Keep it warm/trustworthy (not "hacker/dark" aesthetic) — target audience is non-technical, first-time digital users
- Use real Indian language sample text in mockups (Hindi/Gujarati), not lorem ipsum
