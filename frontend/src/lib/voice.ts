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
/** Cached so we don't re-ask the backend on every single read-aloud. */
let premiumAvailable: boolean | null = null

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

async function isPremiumAvailable(): Promise<boolean> {
  if (premiumAvailable !== null) return premiumAvailable

  try {
    const response = await apiFetchRaw('/api/tts/status')
    if (!response.ok) {
      premiumAvailable = false
      return false
    }
    const body = await response.json()
    premiumAvailable = !!body.available
  } catch {
    premiumAvailable = false
  }

  return premiumAvailable
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

  if (await isPremiumAvailable()) {
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
