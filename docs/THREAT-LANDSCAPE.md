# Threat Landscape

Concrete numbers, so nothing in our roadmap rests on a guess. Every figure below
is sourced. Update this file when newer data lands — a stale number cited with
confidence is worse than no number.

**Last reviewed:** August 2026

---

## 01 · The scale we are building against

| Metric | Figure | Period |
|---|---|---|
| Total reported cyber-fraud loss | **₹22,495 crore** | 2025 |
| Cases reported | **28.15 lakh** (up from 22.68 lakh) | 2025 vs 2024 |
| Cumulative reported loss since NCRP launch | **₹36,448 crore** across 3.8M incidents | to Feb 2025 |
| Six-year cumulative loss | **₹52,976 crore** | 2020–2025 |

Case volume rose ~24% year on year while rupee losses stayed roughly flat
(₹22,845 cr in 2024 → ₹22,495 cr in 2025). Read carefully, that is not good news:
**more people are being hit for smaller amounts each.** That shift is toward
exactly our users — lower-value, higher-volume, less sophisticated targets.

---

## 02 · Who is actually being hit

| Group | Complaints | Loss |
|---|---|---|
| Senior citizens | 1,03,488 | **₹4,005 crore** |
| Women | 4,63,114 | **₹3,765 crore** |
| **Combined** | **5.67 lakh** | **₹7,769 crore** |

Senior citizens file **one-fifth** the complaints of women but lose **more money
in total** — average loss per senior is roughly 5× higher. Coercion-based scams
extract far more per victim than opportunistic ones.

**This is our primary user, stated in numbers rather than sentiment.** It also
justifies design decisions that would otherwise look like over-engineering:
read-aloud output, low-literacy phrasing, and interrupting rather than advising.

---

## 03 · Attack vectors, ranked

| Vector | Evidence | Our coverage |
|---|---|---|
| **Investment / trading scams** | >75% of all rupees lost in 2025 | ⚠️ Weak — patterns exist, no dedicated flow |
| **UPI fraud** | Up 85% in FY24, sustained through 2025 | ✅ Checker shipped; payment interrupt planned |
| **Phishing links / fake QR** | Named lead vector in UPI fraud | ⚠️ UPI-only today; general URL scanning planned |
| **Remote-access apps** | RBI issued a specific advisory | ❌ **Not covered — highest-value gap** |
| **Digital arrest** | 2,41,537 cases, ₹3,012 cr (2022–25) | ⚠️ Call analysis planned |
| **SIM swap** | Named in RBI/NPCI fraud typologies | ❌ Not covered |
| **Fake job / part-time income** | Primary vector against younger users | ⚠️ Patterns exist only |

### The gap that matters most

**Remote-access app fraud.** The RBI has issued a direct advisory naming AnyDesk;
Bengaluru cyber police logged **25 cases in two months**, with individual losses
between ₹15,000 and ₹2 lakh. The mechanism is consistent: the victim is talked
into installing a remote-desktop app, shares the access code, and the attacker
operates the banking app themselves.

This is the highest-value thing we do not currently detect, and it is unusually
tractable — *a remote-access app in the foreground while a banking app is open* is
a narrow, high-confidence signal that is almost never legitimate. See
[`AGENTS.md`](AGENTS.md) §Screen-share sentinel.

### The gap that is largest by rupee value

**Investment scams are 75% of all money lost** and our coverage is a handful of
seed patterns. We are optimised for the vector that hurts the most *people*, not
the one that moves the most *money*. That is a defensible choice — but it should
be a stated choice, not an accident.

---

## 04 · What already exists, and why we are not redundant

Government response in 2025 was substantial: **1.2 million SIM cards deactivated,
1.33 million mule accounts frozen, ₹5,489 crore recovered.** The Fraud Risk
Indicator prevented a reported ₹660 crore in losses over six months.

Every one of those is **post-hoc or infrastructure-level**. They freeze the mule
account after the transfer, block the SIM after the campaign, recover a fraction
after the loss. Recovery of ₹5,489 crore against ₹22,495 crore lost is roughly
**24 paise in the rupee**.

> We are not competing with enforcement. We are trying to stop the transfer that
> enforcement would later spend a year partially recovering.

That is the honest positioning: **prevention at the victim's device**, in the
seconds where enforcement structurally cannot reach.

---

## 05 · What this implies for the roadmap

1. **Payment interrupt stays the critical path.** Recovery is 24% at best; the
   only intervention worth 100% is the one that stops the transfer.
2. **Screen-share sentinel jumps the queue.** RBI-flagged, narrow signal, low
   false-positive risk, currently uncovered.
3. **Seniors are the design target, not a segment.** 5× loss-per-victim justifies
   voice-first and interrupt-first choices.
4. **Investment-scam coverage is a known, named weakness.** State it before a
   judge or a buyer finds it.
5. **Volume is rising while per-case value falls** — the system must be cheap per
   scan. Reinforces edge-first: cost cannot scale linearly with case count.

---

## Sources

- [Indians lost Rs 22,495 crore to cyber fraud in 2025 — ThePrint](https://theprint.in/india/cybercrime-saw-24-spike-in-2025-indians-lost-rs-22495-crore-mainly-in-investment-scams/2859930/)
- [Over 1 lakh senior citizens and 4.63 lakh women report Rs 7,769 crore cyber fraud — The News Mill](https://thenewsmill.com/2026/08/over-1-lakh-senior-citizens-and-4-63-lakh-women-report-rs-7769-crore-cyber-fraud-in-2025/)
- [NCRP cyber fraud statistics — Open Government Data Platform India](https://www.data.gov.in/resource/stateut-wise-details-statistics-national-cyber-crime-reporting-portal-ncrp-related-cyber)
- [Digital Arrest Scams and the Limits of Domestic Enforcement — ORF](https://www.orfonline.org/expert-speak/digital-arrest-scams-and-the-limits-of-domestic-enforcement)
- [India Scams 2026: the ₹22,500-Crore Fraud Epidemic — ScamWatch HQ](https://scamwatchhq.com/india-scams-2026-digital-arrest-upi-fraud-epidemic/)
- [RBI Warns of Fraud That Leverages 'AnyDesk' App — CIO](https://www.cio.inc/rbi-warns-fraud-that-leverages-anydesk-app-a-12035)
- [App at heart of new scam — Deccan Herald](https://www.deccanherald.com/india/karnataka/bengaluru/app-at-heart-of-new-scam-768060.html)
- [Government prevents ₹660 crore cyber fraud losses using Fraud Risk Indicator — NewsOnAir](https://www.newsonair.gov.in/government-prevents-%e2%82%b9660-crore-cyber-fraud-losses-in-6-months-using-fraud-risk-indicator)
