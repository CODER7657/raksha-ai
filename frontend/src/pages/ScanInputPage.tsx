import { useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../lib/api'
import { audioTooLarge } from '../lib/uploadLimits'
import type { ScanResult } from '../lib/scanResult'
import { ArrowRight, CircleCheck, Link2, MessageSquareText, Mic, Square, TriangleAlert, Upload } from 'lucide-react'
import { LanguageSelect } from '../components/LanguageSelect'
import { useLanguage } from '../context/LanguageContext'

type InputMode = 'text' | 'voice' | 'upi'

interface UpiCheckResult {
  is_upi: boolean
  is_suspicious: boolean
  reasons: string[]
}

export function ScanInputPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  // Shared across the whole app now — picking Gujarati here keeps it on the
  // chat screen too, and survives a reload.
  const { language } = useLanguage()

  const [mode, setMode] = useState<InputMode>('text')
  const [text, setText] = useState('')
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
      setError(t('scan.errorMicDenied'))
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
      setError(t('scan.errorEnterUpi'))
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
      setError(err instanceof Error ? err.message : t('scan.errorCheckFailed'))
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
        if (!text.trim()) throw new Error(t('scan.errorPasteFirst'))
        result = await apiFetch('/api/scan/text', {
          method: 'POST',
          body: JSON.stringify({ text, language }),
        })
      } else {
        if (!audioBlob) throw new Error(t('scan.errorRecordFirst'))
        if (audioTooLarge(audioBlob.size)) throw new Error(t('scan.errorAudioTooLarge'))
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
      setError(err instanceof Error ? err.message : t('scan.errorScanFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const tabClass = (active: boolean) =>
    `flex min-h-11 flex-1 items-center justify-start gap-2 border-b-4 px-1 py-2 text-left text-sm font-bold uppercase tracking-[0.06em] transition-colors ${
      active ? 'border-accent text-ink' : 'border-line text-ink/70 hover:border-ink hover:text-ink'
    }`
  const fieldLabel = 'swiss-label text-ink'
  const fieldInput =
    'border-2 border-ink bg-paper px-3 py-3 text-base text-ink placeholder:text-ink/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent'

  return (
    <div className="grid grid-cols-12 gap-x-4 gap-y-8 sm:gap-x-6">
      <div className="col-span-12 lg:col-span-4">
        <p className="swiss-label flex items-center gap-2 text-ink">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          Raksha AI
        </p>
        <h1 className="swiss-display mt-4 text-[clamp(2.25rem,8vw,4rem)]">{t('scan.eyebrow')}</h1>
      </div>

      <div className="col-span-12 border-t-2 border-rule pt-6 lg:col-span-8 lg:pt-8">
        <div className="mb-6 flex gap-3" role="group" aria-label={t('scan.eyebrow')}>
          <button type="button" aria-pressed={mode === 'text'} onClick={() => switchMode('text')} className={tabClass(mode === 'text')}>
            <MessageSquareText aria-hidden="true" size={18} className="shrink-0" />
            {t('scan.tabs.text')}
          </button>
          <button type="button" aria-pressed={mode === 'voice'} onClick={() => switchMode('voice')} className={tabClass(mode === 'voice')}>
            <Mic aria-hidden="true" size={18} className="shrink-0" />
            {t('scan.tabs.voice')}
          </button>
          <button type="button" aria-pressed={mode === 'upi'} onClick={() => switchMode('upi')} className={tabClass(mode === 'upi')}>
            <Link2 aria-hidden="true" size={18} className="shrink-0" />
            {t('scan.tabs.upi')}
          </button>
        </div>

        {mode !== 'upi' && (
          <label className="mb-5 flex flex-col gap-2">
            <span className={fieldLabel}>{t('common.language')}</span>
            <LanguageSelect className="px-3 text-base" />
          </label>
        )}

        {mode === 'text' && (
          <label className="flex flex-col gap-2">
            <span className={fieldLabel}>{t('scan.textLabel')}</span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              maxLength={4000}
              placeholder={t('scan.textPlaceholder')}
              className={`${fieldInput} resize-none`}
            />
            <span className="self-end text-xs text-ink/70">{text.length}/4000</span>
          </label>
        )}

        {mode === 'voice' && (
          <div className="flex flex-col gap-3">
            <span className={fieldLabel}>{t('scan.voiceLabel')}</span>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={recording ? stopRecording : startRecording}
                className={`flex min-h-11 flex-1 items-center gap-2 border-2 px-4 py-3 text-sm font-bold uppercase tracking-[0.06em] transition-colors ${
                  recording ? 'border-accent bg-accent text-accent-ink' : 'border-ink text-ink hover:bg-ink hover:text-paper'
                }`}
              >
                {recording ? <Square aria-hidden="true" size={18} /> : <Mic aria-hidden="true" size={18} />}
                {recording ? t('scan.stopRecording') : t('scan.record')}
              </button>
              <label className="flex min-h-11 flex-1 cursor-pointer items-center gap-2 border-2 border-ink px-4 py-3 text-sm font-bold uppercase tracking-[0.06em] text-ink transition-colors focus-within:ring-2 focus-within:ring-accent hover:bg-ink hover:text-paper">
                <Upload aria-hidden="true" size={18} />
                {t('scan.uploadFile')}
                <input type="file" accept="audio/*" onChange={handleFileChange} className="sr-only" />
              </label>
            </div>

            {audioUrl && (
              <div className="flex items-center gap-3 border-t border-rule pt-3">
                <audio controls src={audioUrl} className="h-11 w-full" />
                <button
                  type="button"
                  onClick={resetAudio}
                  className="min-h-11 shrink-0 px-2 text-xs font-bold uppercase text-ink/70 hover:text-accent"
                >
                  {t('scan.clear')}
                </button>
              </div>
            )}
          </div>
        )}

        {mode === 'upi' && (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-2">
              <span className={fieldLabel}>{t('scan.upiLabel')}</span>
              <input
                type="text"
                value={upiValue}
                onChange={(e) => {
                  setUpiValue(e.target.value)
                  setUpiResult(null)
                }}
                maxLength={256}
                placeholder={t('scan.upiPlaceholder')}
                className={fieldInput}
              />
            </label>
            <p className="text-sm leading-relaxed text-ink/70">{t('scan.upiDescription')}</p>

            {upiResult && (
              <div className={`border-l-4 py-2 pl-4 ${upiResult.is_suspicious ? 'border-accent' : 'border-ink'}`}>
                <p
                  className={`mb-1.5 flex flex-wrap items-center gap-2 text-sm font-bold uppercase tracking-[0.06em] ${
                    upiResult.is_suspicious ? 'text-accent' : 'text-ink'
                  }`}
                >
                  {upiResult.is_suspicious ? (
                    <TriangleAlert aria-hidden="true" size={18} />
                  ) : (
                    <CircleCheck aria-hidden="true" size={18} />
                  )}
                  {upiResult.is_suspicious ? t('scan.upiSuspicious') : t('scan.upiSafe')}
                  {upiResult.is_upi && (
                    <span className="font-normal normal-case tracking-normal text-ink/70">· {t('scan.upiValidFormat')}</span>
                  )}
                </p>
                {upiResult.reasons.length > 0 && (
                  <ul className="list-inside list-disc text-sm leading-relaxed text-ink">
                    {upiResult.reasons.map((reason, i) => (
                      <li key={i}>{reason}</li>
                    ))}
                  </ul>
                )}
                {!upiResult.is_suspicious && <p className="text-sm leading-relaxed text-ink">{t('scan.upiNoIssues')}</p>}
              </div>
            )}
          </div>
        )}

        {error && (
          <p role="alert" className="mt-5 border-l-4 border-accent py-2 pl-4 text-sm text-accent-dark">
            {error}
          </p>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="mt-6 flex min-h-12 w-full items-center justify-between gap-3 bg-accent px-5 py-3 text-left text-sm font-bold uppercase tracking-[0.08em] text-accent-ink transition-colors hover:bg-ink disabled:opacity-60"
        >
          {submitting
            ? mode === 'upi'
              ? t('scan.checking')
              : t('scan.scanning')
            : mode === 'upi'
              ? t('scan.checkUpiLink')
              : t('scan.scanForScams')}
          <ArrowRight aria-hidden="true" size={20} />
        </button>
      </div>
    </div>
  )
}
