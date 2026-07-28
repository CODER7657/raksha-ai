/** Shared browser TTS helper.
 *
 * Bug this fixes: ResultPage/ChatPage used to just set `utterance.lang` and
 * let the browser pick a voice. Chrome/Edge on Windows resolve an unmatched
 * lang (no installed Gujarati voice, for instance) to WHATEVER default voice
 * is currently loaded — which can differ between calls (voice list loads
 * async, so the very first read-aloud can land before it's ready), so the
 * same page reads out in a different voice/gender each time, and a Gujarati
 * request silently gets read in English pronunciation instead.
 *
 * Fix: explicitly resolve and cache one voice per language (exact locale
 * match, else same base language, else null for browser default), waiting
 * for the async voice list to finish loading first. Callers get back
 * whether an exact-locale voice was found, so the UI can tell the user when
 * pronunciation may be off because the device has no voice pack for that
 * language installed.
 */

let voicesPromise: Promise<SpeechSynthesisVoice[]> | null = null

function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (voicesPromise) return voicesPromise

  voicesPromise = new Promise((resolve) => {
    const existing = window.speechSynthesis.getVoices()
    if (existing.length > 0) {
      resolve(existing)
      return
    }

    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.speechSynthesis.removeEventListener('voiceschanged', finish)
      resolve(window.speechSynthesis.getVoices())
    }

    window.speechSynthesis.addEventListener('voiceschanged', finish)
    // Some browsers never fire voiceschanged if the list stays empty (no
    // voice packs installed at all) — don't hang the caller forever.
    setTimeout(finish, 1000)
  })

  return voicesPromise
}

const pickedVoiceCache = new Map<string, { voice: SpeechSynthesisVoice | null; exactMatch: boolean }>()

async function pickVoiceForLang(bcp47: string): Promise<{ voice: SpeechSynthesisVoice | null; exactMatch: boolean }> {
  const cached = pickedVoiceCache.get(bcp47)
  if (cached) return cached

  const voices = await loadVoices()
  const target = bcp47.toLowerCase()
  const baseLang = target.split('-')[0]

  const exact = voices.find((v) => v.lang.toLowerCase() === target)
  const sameBase = voices.find((v) => v.lang.toLowerCase().startsWith(`${baseLang}-`) || v.lang.toLowerCase() === baseLang)
  const result = { voice: exact ?? sameBase ?? null, exactMatch: !!exact }

  pickedVoiceCache.set(bcp47, result)
  return result
}

export function cancelSpeech() {
  window.speechSynthesis.cancel()
}

/** Speaks `text` in `bcp47` (e.g. "gu-IN"), pinning one resolved voice per
 * language so repeated reads sound consistent. Resolves once speech has
 * started (not once it's finished) with whether an exact-locale voice was
 * available, so the caller can show a "closest available voice" hint. */
export async function speakWithBestVoice(
  text: string,
  bcp47: string,
  handlers: { onEnd?: () => void; onError?: () => void } = {},
): Promise<{ exactMatch: boolean }> {
  const { voice, exactMatch } = await pickVoiceForLang(bcp47)

  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = bcp47
  if (voice) utterance.voice = voice
  if (handlers.onEnd) utterance.onend = handlers.onEnd
  if (handlers.onError) utterance.onerror = handlers.onError
  window.speechSynthesis.speak(utterance)

  return { exactMatch }
}
