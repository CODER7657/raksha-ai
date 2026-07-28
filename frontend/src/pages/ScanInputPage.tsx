import { useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { LANGUAGES, type LanguageOption } from '../lib/languages'
import type { ScanResult } from '../lib/scanResult'
import { CornerBrackets } from '../components/CornerBrackets'

type InputMode = 'text' | 'voice' | 'upi'

interface UpiCheckResult {
  is_upi: boolean
  is_suspicious: boolean
  reasons: string[]
}

export function ScanInputPage() {
  const navigate = useNavigate()

  const [mode, setMode] = useState<InputMode>('text')
  const [text, setText] = useState('')
  const [language, setLanguage] = useState<LanguageOption['code']>('en')
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [upiValue, setUpiValue] = useState('')
  const [upiResult, setUpiResult] = useState<UpiCheckResult | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const resetAudio = () => {
    setAudioBlob(null)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
  }

  const startRecording = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        resetAudio()
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        stream.getTracks().forEach((track) => track.stop())
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch {
      setError('Microphone access denied or unavailable.')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    resetAudio()
    setAudioBlob(file)
    setAudioUrl(URL.createObjectURL(file))
  }

  const switchMode = (next: InputMode) => {
    setMode(next)
    setError('')
  }

  const handleUpiCheck = async () => {
    setError('')
    setUpiResult(null)
    if (!upiValue.trim()) {
      setError('Enter a UPI ID or link first.')
      return
    }
    setSubmitting(true)
    try {
      const result: UpiCheckResult = await apiFetch('/api/check-upi', {
        method: 'POST',
        body: JSON.stringify({ value: upiValue.trim() }),
      })
      setUpiResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check failed — try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmit = async () => {
    if (mode === 'upi') {
      await handleUpiCheck()
      return
    }

    setError('')
    setSubmitting(true)
    try {
      let result: ScanResult

      if (mode === 'text') {
        if (!text.trim()) throw new Error('Paste a message first.')
        result = await apiFetch('/api/scan/text', {
          method: 'POST',
          body: JSON.stringify({ text, language }),
        })
      } else {
        if (!audioBlob) throw new Error('Record or upload audio first.')
        const formData = new FormData()
        formData.append('file', audioBlob, audioBlob instanceof File ? audioBlob.name : 'recording.webm')
        result = await apiFetch(`/api/scan/audio?language=${encodeURIComponent(language)}`, {
          method: 'POST',
          body: formData,
        })
      }

      navigate('/app/result', {
        state: { result, sourceText: mode === 'text' ? text : result.transcript, language },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan failed — try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Scan a message or call</span>
      </div>

      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
        <CornerBrackets />

        <div className="flex gap-2 mb-5">
          <button
            type="button"
            onClick={() => switchMode('text')}
            className={`flex-1 border border-ink py-2 text-[11px] font-bold uppercase tracking-[0.15em] transition-colors ${
              mode === 'text' ? 'bg-ink text-white' : 'text-ink hover:bg-ink/5'
            }`}
          >
            Text
          </button>
          <button
            type="button"
            onClick={() => switchMode('voice')}
            className={`flex-1 border border-ink py-2 text-[11px] font-bold uppercase tracking-[0.15em] transition-colors ${
              mode === 'voice' ? 'bg-ink text-white' : 'text-ink hover:bg-ink/5'
            }`}
          >
            Voice / Call
          </button>
          <button
            type="button"
            onClick={() => switchMode('upi')}
            className={`flex-1 border border-ink py-2 text-[11px] font-bold uppercase tracking-[0.15em] transition-colors ${
              mode === 'upi' ? 'bg-ink text-white' : 'text-ink hover:bg-ink/5'
            }`}
          >
            UPI / Link
          </button>
        </div>

        {mode !== 'upi' && (
          <label className="flex flex-col gap-1.5 mb-4">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Language</span>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as LanguageOption['code'])}
              className="border border-ink bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
        )}

        {mode === 'text' && (
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">
              Paste the SMS / WhatsApp / UPI message
            </span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              maxLength={4000}
              placeholder="e.g. Your KYC is expiring, click this link to update: bit.ly/xyz123"
              className="border border-ink bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent resize-none"
            />
            <span className="self-end text-[10px] text-ink/40">{text.length}/4000</span>
          </label>
        )}

        {mode === 'voice' && (
          <div className="flex flex-col gap-3">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Record or upload a call</span>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={recording ? stopRecording : startRecording}
                className={`flex-1 border border-ink py-2.5 text-xs font-bold uppercase tracking-[0.15em] transition-colors ${
                  recording ? 'bg-red-600 border-red-600 text-white' : 'text-ink hover:bg-ink hover:text-white'
                }`}
              >
                {recording ? 'Stop recording' : 'Record'}
              </button>
              <label className="flex-1 border border-ink py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-ink text-center hover:bg-ink hover:text-white transition-colors cursor-pointer">
                Upload file
                <input type="file" accept="audio/*" onChange={handleFileChange} className="hidden" />
              </label>
            </div>

            {audioUrl && (
              <div className="border border-line p-3 flex items-center gap-3">
                <audio controls src={audioUrl} className="w-full h-8" />
                <button type="button" onClick={resetAudio} className="text-[10px] uppercase text-ink/50 hover:text-accent shrink-0">
                  Clear
                </button>
              </div>
            )}
          </div>
        )}

        {mode === 'upi' && (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">
                UPI ID or link to check
              </span>
              <input
                type="text"
                value={upiValue}
                onChange={(e) => {
                  setUpiValue(e.target.value)
                  setUpiResult(null)
                }}
                maxLength={256}
                placeholder="e.g. paytm-refund.info or friend@oksbi"
                className="border border-ink bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </label>
            <p className="text-[11px] text-ink/50 leading-relaxed">
              Pure pattern-matching against known brand names and suspicious domain endings — no AI call, works
              even if the detection service is down.
            </p>

            {upiResult && (
              <div
                className={`relative border p-4 ${
                  upiResult.is_suspicious ? 'border-red-600 bg-red-50' : 'border-emerald-600 bg-emerald-50'
                }`}
              >
                <p
                  className={`text-xs font-bold uppercase tracking-[0.1em] mb-1.5 ${
                    upiResult.is_suspicious ? 'text-red-700' : 'text-emerald-700'
                  }`}
                >
                  {upiResult.is_suspicious ? '⚠ Looks suspicious' : '✅ Nothing suspicious found'}
                  {upiResult.is_upi && <span className="ml-2 font-normal normal-case text-ink/50">· valid UPI ID format</span>}
                </p>
                {upiResult.reasons.length > 0 && (
                  <ul className="list-disc list-inside text-sm text-ink/80 leading-relaxed">
                    {upiResult.reasons.map((reason, i) => (
                      <li key={i}>{reason}</li>
                    ))}
                  </ul>
                )}
                {!upiResult.is_suspicious && (
                  <p className="text-sm text-ink/70 leading-relaxed">
                    No typosquatting or suspicious domain pattern detected — still verify independently before
                    sending money.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {error && <p className="mt-4 border border-red-600 bg-red-50 px-3 py-2 text-[11px] text-red-700">{error}</p>}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="mt-6 w-full bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors disabled:opacity-50"
        >
          {submitting ? (mode === 'upi' ? 'Checking…' : 'Scanning…') : mode === 'upi' ? 'Check UPI / link' : 'Scan for scams'}
        </button>
      </div>
    </div>
  )
}
