# The accessibility-service declaration — draft for submission

> **Status: draft. Nothing here has been submitted.** The Play Console form is
> filled in by [@Ayush3422](https://github.com/Ayush3422); this file is the text
> to paste and the reasoning behind each answer, reviewed before it is sent
> rather than composed in the form field.
>
> Read [`ARCHITECTURE.md`](ARCHITECTURE.md) §01 for what layer 5 is, and
> [`PHASE-2-PLAN.md`](PHASE-2-PLAN.md) §00 for the four constraints every answer
> below has to survive.

---

## 00 · Why this exists before the code does

#116 §5 says the first task of layer 5 is not code, and #39 is the reason it is
worth saying twice. `RECEIVE_SMS` was submitted after it was built, and the
review clock has gated everything since — approval, not submission, is the gate,
and nothing the team does accelerates it.

An accessibility service is a restricted capability with its own declaration and
its own review, and that review is slower and stricter than most, because the
capability is genuinely dangerous. **Submit, then build while it is in review.**
Discovering this clock late cost the project weeks once; doing it knowingly a
second time would be worse.

**The corollary nobody enjoys:** if the declaration is refused, layer 5 does not
ship in this form, and that is better learned before the interception moment is
built than after.

---

## 01 · The awkward paragraph, put first

Google scrutinises accessibility declarations hard because the API is abused,
and the specific abuse pattern is an app that reads and acts on the contents of
other apps' screens — banking apps above all.

That is a description of what this service does.

It is also, precisely, a threat this product already detects: #29 §3 lists
**malicious accessibility-service awareness** as a hardening item, on the
grounds that "an a11y service can read and dismiss our warning". A reviewer who
notices that we warn users about the capability we are requesting is not making
a bad point. **Being able to say why ours is different is the submission** — not
an objection to be worked around at the end of it.

The difference is not intent, which anyone can claim. It is scope, and it is
checkable from the APK:

| Question a reviewer can check | Malicious a11y service | This service |
|---|---|---|
| Which packages does it observe? | All, or a wildcard | An explicit UPI allowlist, in `accessibilityservice` XML |
| What does it do with what it reads? | Exfiltrates | Renders one on-device screen |
| Where does it send it? | A server | **Nowhere — the app holds no `INTERNET` permission** |
| What does it retain? | Everything | Nothing beyond the interrupt being shown |
| Can the user tell it is running? | Designed not to | Protection state says so, and says when it stops |

The fourth row is the one that cannot be faked and is why this app can make the
argument at all: `AndroidManifest.xml` declares no `INTERNET` permission and the
project has no HTTP client (#83 was closed for exactly this reason). A reviewer
does not have to believe a claim about what we do with the data. **There is no
route off the device for it to take.**

---

## 02 · The form answers

Copy these; do not improvise in the field. Each is written to be checkable
against the APK rather than to be persuasive.

### What is your app's core functionality?

> Raksha AI warns people — primarily senior citizens in India — when they are
> being defrauded, at the moment it is happening. It checks incoming SMS against
> a rule engine that runs entirely on the device, warns about calls from numbers
> that have already sent the user a message flagged as a scam, and interrupts a
> UPI payment about to be sent to a payee matching a known fraud pattern.

### Which accessibility service does your app use, and why?

> The service observes UPI payment applications only, from an explicit package
> allowlist declared in the service's configuration XML. When a payment
> confirmation screen shows a payee address that matches a known fraud pattern —
> a typosquatted VPA, a handle impersonating a bank — the app displays a
> full-screen warning before the user confirms.
>
> The accessibility API is used to read the payee address from the payment
> screen. It is not used to perform actions, fill fields, or dismiss anything on
> the user's behalf. The service never interacts with the payment app; it only
> reads, and only on that screen.

### Why can no other Android API achieve this?

> The requirement is to intervene *before* the payment is authorised, while the
> confirmation screen is on top. No public Android API exposes the contents of
> another app's screen. `UsageStatsManager` reports which app is in the
> foreground but nothing about what it shows. Notification listening arrives
> after the transaction. Android's screen-recording detection is per-app by
> design and tells an app only about capture of its own UI. A share-based flow
> requires the user to already be suspicious, which is the failure the product
> exists to address — a scam that is working does not feel like one.
>
> There is no narrower capability that provides the payee address at the moment
> it can still be acted on.

### What user data does the service access, and where does it go?

> The payee address (VPA) and the amount shown on the payment confirmation
> screen. Both are read into memory, compared against on-device patterns, and
> discarded when the screen closes. Neither is written to storage, logged, or
> included in any report.
>
> **Nothing is transmitted. The app declares no `INTERNET` permission**, holds
> no networking library, and sets `usesCleartextTraffic="false"`. There is no
> code path by which the data could leave the device, and this is verifiable
> from the manifest of the uploaded APK rather than on our word.

### Is the accessibility service prominently disclosed to the user?

> Yes. It is off until the user enables it, from a screen that states what is
> read, that nothing is sent anywhere, and that it can be turned off in Android
> settings at any time. The app's protection status reports when the service is
> not running, so a user is never shown a claim of protection the app cannot
> currently deliver.

---

## 03 · What must be true in the build before this is sent

A declaration describing behaviour the APK does not have is worse than a late
one. Every row is checkable by a reviewer, so every row has to be true first.

- [ ] `android:packageNames` in the service XML lists UPI packages explicitly.
      **Never absent and never a wildcard** — an absent attribute means *all
      apps*, which is the single most likely reason for rejection and reads as
      exactly the abuse pattern
- [ ] `android:canRetrieveWindowContent="true"` and nothing broader; no
      `canPerformGestures`, no `FLAG_REQUEST_FILTER_KEY_EVENTS`
- [ ] `accessibilityEventTypes` narrowed to what the interrupt needs, not
      `typeAllMask`
- [ ] No `INTERNET` permission, no HTTP client on the classpath — still true, and
      it is the load-bearing claim in §02
- [ ] Nothing from the payment screen reaches `SafeLog`, storage, or a crash
      report. A VPA is user data in exactly the way a message body is
- [ ] Protection state reports the service being off or killed, the way #93 did
      for force-stop. #116 §5 requires this and it is also §02's last answer
- [ ] The onboarding screen the disclosure answer describes actually exists
- [ ] A demo video showing the interrupt firing on a test payment, and the
      disclosure screen preceding it

---

## 04 · The allowlist

Explicit, and short. Every package here is a decision that has to be defended;
"and anything that looks like a payment app" is not a policy.

The list itself belongs in the service XML rather than in this document, so
there is one source rather than two that drift. What belongs here is the rule:

> A package is added only when someone has confirmed it is a UPI application
> published by the organisation it claims, by package name and signing
> certificate. A typosquatted *payment app* is a plausible attack on the
> allowlist itself, and a fraudulent app added to it would be handed the payee
> address of every legitimate transaction the user makes.

That last sentence is the reason the allowlist is not generated from a search of
installed apps.

---

## 05 · What this submission deliberately does not ask for

Stated because the declaration binds us to it, and widening scope later means
another review.

- **Not remote-access detection.** THREAT-LANDSCAPE §03 names remote-access app
  fraud as the highest-value gap, and an accessibility service can observe
  foreground app changes, so it is technically adjacent. It is not in this
  declaration. Asking for one capability and using it for a second purpose is
  the thing the review exists to catch, and it would put the honest parts of
  §02 in doubt.
- **Not reading the banking app.** UPI payment apps only.
- **Not acting on the user's behalf.** No gesture dispatch, no auto-cancel of a
  payment. Layer 5 is described as terminal because it *stops the user*, not
  because it stops the transaction — the user always presses the button.

---

## 06 · Open, and not to be guessed at

- Whether Play requires the declaration before or alongside the first upload
  containing the service. Confirm in Console rather than assuming; #39's lesson
  is that the sequence is the expensive part.
- Whether an app already holding one restricted permission under review
  (`RECEIVE_SMS`, #39) is treated differently when a second is requested. Nobody
  here knows, and it is worth asking before both are in flight.
- The demo video in §03 needs a payment that does not move money. How to stage
  that safely — a test VPA, a sandbox — is not solved.
