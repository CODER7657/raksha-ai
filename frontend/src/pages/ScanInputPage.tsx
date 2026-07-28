import { useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { LANGUAGES, type LanguageOption } from '../lib/languages'
import { CornerBrackets } from '../components/CornerBrackets'

type InputMode = 'text' | 'voice'

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

  const handleSubmit = async () => {
    setError('')
    setSubmitting(true)
    try {
      let result: unknown

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

      navigate('/result', { state: { result } })
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
            onClick={() => setMode('text')}
            className={`flex-1 border border-ink py-2 text-[11px] font-bold uppercase tracking-[0.15em] transition-colors ${
              mode === 'text' ? 'bg-ink text-white' : 'text-ink hover:bg-ink/5'
            }`}
          >
            Text
          </button>
          <button
            type="button"
            onClick={() => setMode('voice')}
            className={`flex-1 border border-ink py-2 text-[11px] font-bold uppercase tracking-[0.15em] transition-colors ${
              mode === 'voice' ? 'bg-ink text-white' : 'text-ink hover:bg-ink/5'
            }`}
          >
            Voice / Call
          </button>
        </div>

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

        {mode === 'text' ? (
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
        ) : (
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

        {error && <p className="mt-4 border border-red-600 bg-red-50 px-3 py-2 text-[11px] text-red-700">{error}</p>}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="mt-6 w-full bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors disabled:opacity-50"
        >
          {submitting ? 'Scanning…' : 'Scan for scams'}
        </button>
      </div>
    </div>
  )
}
