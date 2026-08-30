import { useEffect, useState } from 'react'
import { cn } from '../lib/cn'

const STEP_LABEL = {
  read_rasters: 'Read rasters',
  classify_intent: 'Classify intent',
  validate: 'Validate (Trust Gate)',
  gsd_normalize: 'GSD normalize',
  run_model: 'Run model',
  aggregate: 'Aggregate tiles',
  regions_to_geojson: 'Regions → GeoJSON',
  compute_confidence: 'Compute confidence',
}

export default function TraceTimeline({ trace }) {
  const [visibleCount, setVisibleCount] = useState(0)

  useEffect(() => {
    setVisibleCount(0)
    if (!trace?.length) return undefined

    let i = 0
    const id = setInterval(() => {
      i += 1
      setVisibleCount(i)
      if (i >= trace.length) clearInterval(id)
    }, 130)

    return () => clearInterval(id)
  }, [trace])

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-900 p-4">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wide text-mist-300">Execution trace</h3>
      {!trace?.length ? (
        <p className="text-xs text-mist-500">No query run yet.</p>
      ) : (
        <ol>
          {trace.map((entry, idx) => (
            <li
              key={`${entry.step}-${idx}`}
              className={cn(
                'relative pb-5 pl-6 last:pb-0 transition-all duration-300 ease-out',
                idx < visibleCount ? 'translate-y-0 opacity-100' : 'translate-y-1.5 opacity-0',
              )}
            >
              <span className="absolute left-0 top-1 h-2.5 w-2.5 rounded-full bg-cyan-glow ring-4 ring-navy-900" />
              {idx < trace.length - 1 && (
                <span className="absolute bottom-0 left-[4.5px] top-4 w-px bg-navy-600" />
              )}
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-cyan-glow">
                  {STEP_LABEL[entry.step] ?? entry.step}
                </span>
                <span className="whitespace-nowrap font-mono text-[11px] text-mist-500">
                  {entry.duration_ms} ms
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-mist-300">{entry.detail}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
