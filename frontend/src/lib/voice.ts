/** Read-aloud with a quality ladder: ElevenLabs first, browser voice second.
 *
 * Why a ladder rather than just picking one:
 *
 * - Browser speechSynthesis is free and unlimited, but Indic voice packs are
 *   simply absent on most Windows and many Android devices. Gujarati in
 *   particular usually resolves to an English voice reading Gujarati letters,
 *   which is unintelligible (see the header comment in ./speech.ts).
 * - ElevenLabs sounds genuinely good and covers 11 of the app's 12 languages
 *   (Odia is the exception), but the free plan is ~10,000 credits/month across
 *   ALL users — roughly 30-60 spoken replies. It WILL run out.
 *
 * So: try the good one, and when it's unavailable for any reason — quota gone,
 * key missing, network down, language unsupported — quietly drop to the device
 * voice. The user always hears something, and the text is on screen regardless.
 * Voice is an enhancement here, never a dependency.
 */

import { apiFetchRaw } from './api'
import { cancelSpeech, speakWithBestVoice } from './speech'

export type VoiceSource = 'elevenlabs' | 'browser'

export interface SpeakResult {
  source: VoiceSource
  /** Browser path only: whether a voice actually matching the language existed
   * on this device. False means pronunciation is probably wrong. */
  exactMatch: boolean
  /** True when a newer speak() superseded this one before it could produce
   * audio. The caller must leave its UI state alone — a later call now owns
   * it, and clearing "speaking" here would desync the button. */
  stale?: boolean
}

interface SpeakOptions {
  /** App language code, e.g. "gu". */
  language: string
  /** BCP-47 tag for the browser fallback, e.g. "gu-IN". */
  speechLang: string
  onEnd?: () => void
  onError?: () => void
}

let currentAudio: HTMLAudioElement | null = null

/** Monotonic token identifying the most recent speak() call.
 *
 * The Indic providers take 5-10 seconds to return audio, and cancelVoice() can
 * only stop sound that is *already playing* — during that wait `currentAudio`
 * is still null, so there is nothing for it to cancel. Without a token, tapping
 * read-aloud three times fired three requests that all eventually resolved and
 * all called play(), and because each one overwrote `currentAudio`, the earlier
 * elements kept playing with no handle left to stop them: two or three voices
 * talking over each other.
 *
 * Every speak() captures the token it started with and re-checks it after each
 * await. If the token has moved on, a newer call owns the audio and this one
 * discards its result instead of playing it.
 */
let generation = 0

/** The in-flight provider request, so a superseding call can abort it straight
 * away rather than paying for audio nobody will hear. */
let inFlight: AbortController | null = null

/** One slot of speculatively-fetched audio.
 *
 * Synthesis time scales with text length: a full scan result takes ~6-9s in
 * Hindi or Gujarati, which is a long time to stare at a button. But the user
 * spends several seconds *reading* that result before they ever reach for
 * read-aloud, and that gap is free. Fetching during it turns a 8.6s wait into
 * an instant play.
 *
 * Deliberately a single slot rather than a map: only one result is on screen at
 * a time, and an unbounded cache of audio blobs is a memory leak with extra
 * steps. */
let prefetched: { key: string; blob: Blob } | null = null
let prefetchInFlight: AbortController | null = null

const voiceKey = (text: string, language: string) => `${language}::${text}`

interface VoiceStatus {
  available: boolean
  /** Languages the server wants us to speak locally — see below. */
  browserLanguages: string[]
}

/** Cached so we don't re-ask the backend on every single read-aloud. */
let statusPromise: Promise<VoiceStatus> | null = null

/** Stops whichever engine is currently talking, and invalidates any request
 * still on its way back — otherwise a fetch started before this call would
 * arrive afterwards and start speaking over the silence we just created. */
export function cancelVoice() {
  generation += 1

  if (inFlight) {
    inFlight.abort()
    inFlight = null
  }

  if (currentAudio) {
    currentAudio.pause()
    // Release the object URL so repeated reads don't leak blobs.
    if (currentAudio.src.startsWith('blob:')) URL.revokeObjectURL(currentAudio.src)
    currentAudio = null
  }
  cancelSpeech()
}

function fetchStatus(): Promise<VoiceStatus> {
  if (statusPromise) return statusPromise

  statusPromise = (async () => {
    try {
      const response = await apiFetchRaw('/api/tts/status')
      if (!response.ok) return { available: false, browserLanguages: [] }
      const body = await response.json()
      return {
        available: !!body.available,
        browserLanguages: Array.isArray(body.browser_languages) ? body.browser_languages : [],
      }
    } catch {
      return { available: false, browserLanguages: [] }
    }
  })()

  return statusPromise
}

type ProviderOutcome = 'played' | 'failed' | 'stale'

async function speakWithProvider(
  text: string,
  language: string,
  options: SpeakOptions,
  token: number,
): Promise<ProviderOutcome> {
  const controller = new AbortController()
  inFlight = controller

  // If this exact text was already fetched while the user was reading, skip
  // the network entirely — this is what makes read-aloud feel instant.
  const key = voiceKey(text, language)
  let blob: Blob | null = prefetched?.key === key ? prefetched.blob : null

  if (!blob) {
    let response: Response
    try {
      response = await apiFetchRaw('/api/tts', {
        method: 'POST',
        body: JSON.stringify({ text, language }),
        signal: controller.signal,
      })
    } finally {
      // Only clear the shared slot if it is still ours — a newer call may have
      // replaced it while we were waiting.
      if (inFlight === controller) inFlight = null
    }

    if (token !== generation) return 'stale'

    // 503 is the documented "use the browser voice" signal, not a failure worth
    // showing anyone. Anything else non-2xx gets the same treatment.
    if (!response.ok) return 'failed'

    blob = await response.blob()
    // Re-check: reading the body is another await, and on a slow connection a
    // second tap can land right here.
    if (token !== generation) return 'stale'
  }

  if (inFlight === controller) inFlight = null
  if (blob.size === 0) return 'failed'

  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  currentAudio = audio

  const cleanup = () => {
    URL.revokeObjectURL(url)
    if (currentAudio === audio) currentAudio = null
  }

  audio.onended = () => {
    cleanup()
    options.onEnd?.()
  }
  audio.onerror = () => {
    cleanup()
    options.onError?.()
  }

  try {
    await audio.play()
    return 'played'
  } catch {
    // Autoplay policies can reject play() if this wasn't user-initiated.
    cleanup()
    return 'failed'
  }
}

/** Fetches audio ahead of time so a later speak() of the same text plays with
 * no wait. Safe to call on render: it never plays anything, never touches the
 * playback token, and swallows every failure — a missed prefetch just means
 * read-aloud behaves exactly as it did before.
 *
 * Skips languages the server has told us to speak locally (English by default),
 * since the browser voice is already instant and a prefetch there would spend
 * provider credit for nothing. */
export async function prefetchVoice(text: string, language: string): Promise<void> {
  const key = voiceKey(text, language)
  if (!text.trim() || prefetched?.key === key) return

  try {
    const status = await fetchStatus()
    if (!status.available || status.browserLanguages.includes(language)) return

    prefetchInFlight?.abort()
    const controller = new AbortController()
    prefetchInFlight = controller

    const response = await apiFetchRaw('/api/tts', {
      method: 'POST',
      body: JSON.stringify({ text, language }),
      signal: controller.signal,
    })
    if (!response.ok) return

    const blob = await response.blob()
    if (blob.size > 0) prefetched = { key, blob }
  } catch {
    // Aborted, offline, or provider down — read-aloud will just fetch normally.
  } finally {
    prefetchInFlight = null
  }
}

/** Speaks `text`, returning which engine actually produced the audio so the UI
 * can explain itself when it lands on a poor-quality device voice. */
export async function speak(text: string, options: SpeakOptions): Promise<SpeakResult> {
  // Stops anything audible, aborts any pending request, and bumps the token —
  // so every earlier in-flight call is now stale and will discard itself.
  cancelVoice()
  const token = generation

  const stale = (): SpeakResult => ({ source: 'browser', exactMatch: true, stale: true })

  const status = await fetchStatus()
  if (token !== generation) return stale()

  // Some languages are deliberately spoken locally. English is the default
  // case: every platform ships a good English voice, so spending a finite
  // credit pool on it buys nothing, while Gujarati and Hindi are exactly where
  // devices fall short. Checking here rather than server-side skips a pointless
  // network round-trip before every English read-aloud.
  const useBrowserByPolicy = status.browserLanguages.includes(options.language)

  if (status.available && !useBrowserByPolicy) {
    let outcome: ProviderOutcome = 'failed'
    try {
      outcome = await speakWithProvider(text, options.language, options, token)
    } catch {
      // An abort from a superseding tap surfaces here as well as a genuine
      // network failure; the token check below is what tells them apart.
      outcome = 'failed'
    }

    if (token !== generation) return stale()
    if (outcome === 'played') return { source: 'elevenlabs', exactMatch: true }
  }

  // Falling back to the device voice is only correct if we still own the turn.
  // Without this guard a superseded request would fall through and start the
  // browser voice on top of whatever the newer tap is already saying.
  if (token !== generation) return stale()

  const { exactMatch } = await speakWithBestVoice(text, options.speechLang, {
    onEnd: options.onEnd,
    onError: options.onError,
  })

  return { source: 'browser', exactMatch }
}
