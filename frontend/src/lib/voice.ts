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

interface VoiceStatus {
  available: boolean
  /** Languages the server wants us to speak locally — see below. */
  browserLanguages: string[]
}

/** Cached so we don't re-ask the backend on every single read-aloud. */
let statusPromise: Promise<VoiceStatus> | null = null

/** Stops whichever engine is currently talking. */
export function cancelVoice() {
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

async function speakWithElevenLabs(text: string, language: string, options: SpeakOptions): Promise<boolean> {
  const response = await apiFetchRaw('/api/tts', {
    method: 'POST',
    body: JSON.stringify({ text, language }),
  })

  // 503 is the documented "use the browser voice" signal, not a failure worth
  // showing anyone. Anything else non-2xx gets the same treatment.
  if (!response.ok) return false

  const blob = await response.blob()
  if (blob.size === 0) return false

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
    return true
  } catch {
    // Autoplay policies can reject play() if this wasn't user-initiated.
    cleanup()
    return false
  }
}

/** Speaks `text`, returning which engine actually produced the audio so the UI
 * can explain itself when it lands on a poor-quality device voice. */
export async function speak(text: string, options: SpeakOptions): Promise<SpeakResult> {
  cancelVoice()

  const status = await fetchStatus()

  // Some languages are deliberately spoken locally. English is the default
  // case: every platform ships a good English voice, so spending a finite
  // credit pool on it buys nothing, while Gujarati and Hindi are exactly where
  // devices fall short. Checking here rather than server-side skips a pointless
  // network round-trip before every English read-aloud.
  const useBrowserByPolicy = status.browserLanguages.includes(options.language)

  if (status.available && !useBrowserByPolicy) {
    try {
      const played = await speakWithElevenLabs(text, options.language, options)
      if (played) return { source: 'elevenlabs', exactMatch: true }
    } catch {
      // Fall through to the browser voice below.
    }
  }

  const { exactMatch } = await speakWithBestVoice(text, options.speechLang, {
    onEnd: options.onEnd,
    onError: options.onError,
  })

  return { source: 'browser', exactMatch }
}
