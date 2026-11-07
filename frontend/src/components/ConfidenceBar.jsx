import { useEffect, useState } from 'react'
import { cn } from '../lib/cn'

function toneFor(value) {
  if (value > 0.7) return { bar: 'bg-ok', text: 'text-ok', label: 'high' }
  if (value >= 0.4) return { bar: 'bg-warn', text: 'text-warn', label: 'moderate' }
  return { bar: 'bg-danger', text: 'text-danger', label: 'low' }
}

export default function ConfidenceBar({ value, label = 'Confidence' }) {
  const pct = Math.round(Math.min(1, Math.max(0, value ?? 0)) * 100)
  const tone = toneFor(value ?? 0)

  const [displayPct, setDisplayPct] = useState(0)

  useEffect(() => {
    setDisplayPct(0)
    const id = requestAnimationFrame(() => setDisplayPct(pct))
    return () => cancelAnimationFrame(id)
  }, [pct])

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-xs font-medium text-mist-300 uppercase tracking-wide">{label}</span>
        <span className={cn('font-mono text-sm font-semibold', tone.text)}>
          {pct}%
          <span className="ml-2 text-[10px] font-sans font-normal uppercase text-mist-500">{tone.label}</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-navy-700">
        <div
          className={cn('h-full rounded-full transition-all duration-[400ms] ease-out', tone.bar)}
          style={{ width: `${displayPct}%` }}
        />
      </div>
    </div>
  )
}
