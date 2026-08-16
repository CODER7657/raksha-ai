# Releasing

> The web and the backend deploy continuously-ish and their order is in
> [`START-HERE.md`](../START-HERE.md) §1b. **This document is the Android
> release**, which is different in kind: a store review sits in the middle of
> it, the artifact is signed with a key that must never enter the repository,
> and a mistake is visible to users for as long as it takes to ship another
> build.

---

## 00 · What makes this different from a deploy

A backend deploy is reversible in about a minute. An Android release is not:

- The APK you upload is what users have until the next one clears review.
- **The signing key is permanent.** Lose it and you cannot ship an update to the
  same app listing, ever. Play App Signing exists to make this recoverable — use
  it, and the upload key becomes the replaceable half.
- Review takes days, and a rejection resets that clock.

So the order below front-loads everything that can fail cheaply.

---

## 01 · One-time setup

### The upload key

Generated once, on a machine you trust, and never committed. `.gitignore`
already covers `*.jks` and `*.keystore`; that is a safety net, not a plan.

```bash
keytool -genkeypair -v \
  -keystore raksha-upload.jks \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -alias raksha-upload
```

Then enrol in **Play App Signing** when creating the app listing. Google holds
the app signing key; yours becomes the upload key, and an upload key can be
reset if it leaks. Without this, a lost key ends the listing.

Store the keystore and its passwords in a password manager. Not in the repo, not
in a chat message, not in a note next to the passwords.

### Repository secrets

Four, under **Settings → Secrets and variables → Actions**, as repository
**Secrets**:

| Secret | Value |
|---|---|
| `RAKSHA_KEYSTORE_BASE64` | `base64 -w0 raksha-upload.jks` |
| `RAKSHA_KEYSTORE_PASSWORD` | the keystore password |
| `RAKSHA_KEY_ALIAS` | `raksha-upload` |
| `RAKSHA_KEY_PASSWORD` | **the same password again** — see below |

> **There is only one password, and every guide will tell you there are two.**
>
> JDK 9 changed keytool's default format to PKCS12, and it stays PKCS12 even
> when the file is named `.jks`. **PKCS12 does not support a separate key
> password.** keytool will not prompt for one, and if you force one with
> `-keypass` it says so and ignores you:
>
> ```
> Warning: Different store and key passwords not supported for PKCS12
> KeyStores. Ignoring user-specified -keypass value.
> ```
>
> So the "re-enter password" prompt during `-genkeypair` is a confirmation, not
> a second password. `RAKSHA_KEY_PASSWORD` takes the same value as
> `RAKSHA_KEYSTORE_PASSWORD`.
>
> The Android signing config has separate `storePassword` and `keyPassword`
> fields because the older JKS format genuinely allowed them to differ. Two
> fields, one value.

> **Check the secret names character by character.** A typo caught this on the
> first real run: the secret had been created as `RAKSHA_KEY_PASSWORDG`, and a
> trailing character is invisible in `gh secret list` unless you are hunting for
> it. The workflow reports a misnamed secret and an absent one **identically** —
> both are "missing" from its point of view:
>
> ```
> ##[error]Missing repository secrets: RAKSHA_KEY_PASSWORD
> ```
>
> If that appears and you are certain you set it, list the secrets and compare
> the names rather than re-entering the value.

> **The four-places trap** (#70). "Secret" means four different things on
> GitHub: repository Secrets, repository Variables, Environment secrets, and the
> `env:` block in a workflow. `android-release.yml` reads repository **Secrets**.
> Setting three of the four correctly fails in a way that reads like a keystore
> problem rather than a naming one, which is why the workflow checks all four
> before it builds anything.

Locally, the same values are read from the environment as
`RAKSHA_KEYSTORE_PATH` (a path, not base64), `RAKSHA_KEYSTORE_PASSWORD`,
`RAKSHA_KEY_ALIAS`, `RAKSHA_KEY_PASSWORD`. Missing any one and the signing
config is simply not created — the build succeeds and produces an **unsigned**
APK, exactly as it did before signing existed. That is deliberate: a
half-configured setup that silently signs with the wrong key is worse than one
that obviously did not sign, and `verifyReleaseSigning` turns the silence into a
failure when signing was actually intended.

---

## 02 · Before you build

- [ ] `master` is green, and the commit you are releasing is on it
- [ ] Every backend change the app depends on is **deployed**, not merely merged
      (`START-HERE.md` §1b). The app talks to Render; a release pinned against an
      API that has not shipped is a support problem with no local reproduction
- [ ] Migrations for those changes are applied
- [ ] `versionCode` incremented — Play rejects a duplicate, and it is the one
      mistake that wastes a whole upload
- [ ] The **Data Safety form** matches the implementation. For this app every
      answer is "No": SMS is read, scored on device, and not transmitted. A
      mismatch is not a policy problem, it is a credibility problem for a product
      whose pitch is that messages never leave the phone
- [ ] Restricted-permission declarations are current — `RECEIVE_SMS` is one, and
      **approval, not submission, is what unblocks shipping**

---

## 03 · Build

Run the **Android release build** workflow from the Actions tab.
`workflow_dispatch` only; it costs nothing until asked.

It will, in order: confirm all four secrets exist, decode the keystore into the
runner temp directory, `clean assembleRelease`, run `verifyReleaseSigning`, run
`apksigner verify --print-certs`, assert v2 **and** v3 schemes are present, and
upload the APK as an artifact for 60 days. It shreds the keystore afterwards
even if a step failed.

`clean` is not superstition. `assembleRelease` reports `UP-TO-DATE` and does not
re-sign, so a stale unsigned APK survives next to a signed one — and that is
precisely the file someone uploads by mistake.

### Building locally instead

```bash
cd android
export RAKSHA_KEYSTORE_PATH=/path/to/raksha-upload.jks
export RAKSHA_KEYSTORE_PASSWORD=...
export RAKSHA_KEY_ALIAS=raksha-upload
export RAKSHA_KEY_PASSWORD=...
./gradlew clean assembleRelease verifyReleaseSigning
apksigner verify --verbose --print-certs app/build/outputs/apk/release/*.apk
```

If `verifyReleaseSigning` says the block is absent while all four variables are
set, the usual cause is a Gradle daemon still running with the old environment.
`--no-daemon` rules it out.

---

## 04 · Verify the artifact, before Play sees it

- [ ] `apksigner verify` reports **v2 and v3 true**. v1 is off deliberately —
      `minSdk` is 24 and a v1 signature that is present but invalid reports as
      `v1 scheme: false`, which is the most confusing state to debug (#86)
- [ ] The certificate fingerprint is the one you expect. On a re-release, compare
      it against the previous build; a changed fingerprint means the wrong
      keystore and Play will reject the upload
- [ ] **Install it on a real device** and scan a message. Emulator-only
      verification has never caught an install problem, because there has not
      been one yet — that is not the same as there not being one
- [ ] Confirm the app scans after a **reboot** without being opened. It does
      (#86 measured it) — this is a regression check, not an open question
- [ ] Check the warning notification renders in **Hindi and Gujarati**, not only
      English

---

## 05 · Upload

- [ ] Internal testing track first. Always. It is the only way to find an
      install-time failure without a user finding it
- [ ] Release notes written
- [ ] Then a staged rollout, not 100%

---

## 06 · After it is live

- [ ] Tag the commit: `git tag -a android-vX.Y.Z -m "..." && git push --tags`.
      Without this, "which commit is on people's phones" becomes guesswork
- [ ] Record the `versionCode`, the commit, and the certificate fingerprint
      somewhere durable
- [ ] Watch crash reports for the first day of the rollout

---

## 07 · What this process has actually been run against

**The workflow has produced a signed APK.** Run `31931926615`, 16 August:

```
All four signing secrets are present.
BUILD SUCCESSFUL in 2m 23s
Release APK signature present: app-release.apk
Verified using v1 scheme (JAR signing): false     <- correct, minSdk 24
Verified using v2 scheme: true
Verified using v3 scheme: true
```

So the keystore decodes, the password is right, the base64 survived the round
trip, and the signature validates rather than merely existing. That is the whole
of §01 and §03 proven end to end.

Two failures on the way there, both caught by the secret check before any build
ran, and both now documented in §01: a missing secret, and a misnamed one.

## 08 · Known gaps in this process

Written down rather than discovered:

- **No real-device install has been done yet.** #95. Everything to date is
  emulator-verified, and §04 above asks for something that has not happened once.
  The signed artifact now exists, so this is unblocked rather than theoretical:
  `gh run download 31931926615 -n raksha-release-signed`.
- **`verifyReleaseSigning` is a smoke test.** It proves a signature block is
  present, not that it validates. `apksigner verify` is the real check, which is
  why the workflow runs both and why §04 lists it separately.
- **No automated upload.** Deliberate for now: an automated upload to a store is
  a large blast radius for a team of three, and the manual step is where the
  Data Safety and versionCode checks actually get done.
- **No `bundletool`/AAB path.** Play prefers an App Bundle. This ships an APK,
  which is fine for internal testing and will need revisiting before a public
  production track.
