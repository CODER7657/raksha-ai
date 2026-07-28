import { useMemo } from 'react'

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function HighlightedText({ text, phrases }: { text: string; phrases: string[] }) {
  const parts = useMemo(() => {
    const cleanPhrases = phrases.filter((p) => p.trim().length > 0)
    if (cleanPhrases.length === 0) return [{ text, flagged: false }]

    const pattern = new RegExp(`(${cleanPhrases.map(escapeRegExp).join('|')})`, 'gi')
    return text.split(pattern).map((chunk) => ({
      text: chunk,
      flagged: cleanPhrases.some((p) => p.toLowerCase() === chunk.toLowerCase()),
    }))
  }, [text, phrases])

  return (
    <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-words">
      {parts.map((part, i) =>
        part.flagged ? (
          <mark key={i} className="bg-accent/25 text-ink px-0.5 underline decoration-accent decoration-2">
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </p>
  )
}
