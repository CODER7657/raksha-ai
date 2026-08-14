# SMS Auto-Scan — Implementation Plan (P1)

> Owner: Ayush `@Ayush3422` · Status: proposed, not started · Layer: 2 of 5
>
> Read [`ARCHITECTURE.md`](ARCHITECTURE.md) first. This plan assumes the V2
> interception model and does not restate it.

---

## 00 · What this delivers

Layer 2 of the interception model: an Android client that reads incoming SMS,
scores each one **on the device**, and raises a notification when it looks like
fraud. Zero user action — the victim does not have to suspect anything, which is
the entire point of V2.

Scope of this plan is the Android shell plus SMS interception. Call screening
(layer 3) and the UPI payment interrupt (layer 5) are later phases and are only
referenced here where they constrain a decision made now.

---

## 01 · The blocker, stated first

**SMS auto-scan cannot be built on the existing `/api/scan/text` endpoint.**

The roadmap lists "Android shell + SMS auto-scan" (Ayush) and "On-device rule
engine port" (Pavan) as sibling P1 items. They are not siblings. The second is a
hard dependency of the first, and building in the listed order produces something
that has to be thrown away.

The obvious implementation — a `BroadcastReceiver` that forwards each incoming
message to `/api/scan/text` — breaks four things at once:

| Problem | Where | Consequence |
|---|---|---|
| Raw message persisted | `routes/scan.py` writes `input_text` into `scans` | Every SMS a user receives lands in our cloud in plaintext — the precise thing §02 and §04 say we do not do |
| Rate limit is per-IP | `rate_limit.py` keys on `get_remote_address`, `10/minute` | Carrier-grade NAT means mobile users share an IP and throttle strangers |
| Requires connectivity | Network call in the hot path | Scam SMS arrive regardless of signal; misses are silent |
| Cold start | Free tier sleeps, ~40–50s wake | A warning that lands a minute late is not an interception |

The first row is the serious one. The others are tuning; that one is a
contradiction of the product's central privacy claim, and it is the claim the
embedded-SDK pitch to banks rests on.

> Detection must run on the device before any of this is worth shipping.
> The Kotlin rule-engine port is therefore step one, whoever writes it.

---

## 02 · Phases

### Phase 0 — Agree the dependency (no code)

Two decisions needed from the lead before implementation starts, because both
touch files under `@CODER7657` in `CODEOWNERS`:

1. **Who ports the rule engine to Kotlin?** `services/rule_engine.py` is ~40
   lines of regex tables. Porting is roughly a day. Either it lands as Pavan's
   P1 first, or it is absorbed into this work with his review.
2. **Does `/api/scan/text` get a no-persist mode?** Needed for Phase 3. Options
   are a request flag, a separate endpoint, or reusing the existing hashed
   community-radar path and returning a verdict without writing to `scans`.

### Phase 1 — Android shell

New `android/` module. Nothing exists today; the repo is `backend/` + `frontend/`.

- Supabase JWT auth, reusing the contract in `core/auth.py` — the backend needs
  no change, since it already verifies JWKS-signed tokens and reads `sub`.
- Language selection over the same twelve codes as `core/languages.py`. Keep
  them in sync with the list that file already names as sources of truth.
- No SMS permissions requested yet. Shell first, so auth and language are proven
  before the restricted-permission conversation starts.

### Phase 2 — SMS listener and on-device scoring

- `BroadcastReceiver` on incoming SMS.
- Kotlin rule engine scores locally. Zero network, zero user action.
- Notification on a hit, with the flagged phrases shown in the user's language.
- Message text never leaves the device on this path.

This phase alone satisfies the layer-2 description in the architecture.

### Phase 3 — Opt-in cloud escalation

Per §02, escalate **only** when on-device confidence is low **and** the user
consents. Depends on the Phase 0 decision about persistence. Until that exists,
Phase 2 ships standalone and degrades honestly: uncertain messages stay
unflagged rather than being silently uploaded.

---

## 03 · Dependencies owned by others

| Dependency | Owner | Status | Blocks |
|---|---|---|---|
| Kotlin rule-engine port | Pavan | Not started | Phase 2 — everything |
| Phone-number HMAC with server pepper | Pavan | **Required for mobile, not shipped** | Any phone-number identity |
| No-persist scan path | Pavan | Not designed | Phase 3 |
| Rule patterns beyond en/hi/gu | Pavan (file), Ayush (language) | 3 of 12 languages | Honest multilingual claim |

**On phone-number identity.** §07 marks HMAC-with-pepper as required for mobile
and lists it as unshipped. If the Android client ever keys identity on a phone
number, that control lands first — the doc is explicit that a plain SHA-256 of an
Indian mobile number is reversible, so shipping without it would make the "we
only store hashes" claim false. Avoidable in Phase 1 by staying on the existing
Supabase email auth.

**On language coverage.** `rule_engine.py` has patterns for `en`, `hi` and `gu`
only, against twelve languages in `core/languages.py`. "SMS auto-scan in twelve
languages" is not true today and should not be claimed until the tables are
filled. The file is owned by the lead; the language expertise is not.

---

## 04 · To verify before a store build

`RECEIVE_SMS` is a Play Console **restricted** permission. The roadmap describes
this phase as having "no alarming permissions", which is optimistic — SMS access
is among the most gated permissions Google grants, and approval is not automatic.

This has not been checked against current policy and must be before any store
distribution is planned. A direct-APK pilot avoids the question entirely and is
likely the right first move regardless, since the pilot audience is small and
known.

---

## 05 · Known limits of this plan

State these rather than be asked:

- On-device model size versus low-end Android RAM is still unvalidated (§05).
  Phase 2 is rules-only for that reason; the classifier is a later question.
- Rules-only detection will miss more than the LLM path does. That is the
  correct trade for Phase 2 — a local miss is no worse than today, where the
  message is never scanned at all, whereas a cloud round trip breaks the privacy
  claim on every message.
- There is still no labelled benchmark (§05, P0). Until it exists, no precision
  or recall figure can be attached to anything below.
