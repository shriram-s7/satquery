import { useEffect, useState } from 'react'
import { cn } from '../lib/cn'
import EvidenceCanvas from './EvidenceCanvas'

export default function EvidencePanel({ slotA, slotB, overlayRegions }) {
  const hasB = Boolean(slotB.file && slotB.meta)
  const [active, setActive] = useState('A')

  useEffect(() => {
    if (!hasB) setActive('A')
  }, [hasB])

  const slot = active === 'B' && hasB ? slotB : slotA
  const regions = (overlayRegions ?? []).filter(
    (r) => slot.file && r.source_image?.endsWith(slot.file.name),
  )

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-mist-300">Evidence</h3>
        {hasB && (
          <div className="flex overflow-hidden rounded-md border border-navy-600 text-[11px] font-mono">
            {['A', 'B'].map((slotKey) => (
              <button
                key={slotKey}
                type="button"
                onClick={() => setActive(slotKey)}
                className={cn(
                  'px-3 py-1 transition-colors',
                  active === slotKey ? 'bg-cyan-glow text-navy-950' : 'bg-navy-850 text-mist-300 hover:bg-navy-700',
                )}
              >
                {slotKey === 'A' ? 'T1' : 'T2'}
              </button>
            ))}
          </div>
        )}
      </div>

      <EvidenceCanvas
        imageSrc={slot.meta?.preview_data_url}
        imageBounds={slot.meta?.bounds_wgs84}
        regions={regions}
      />

      <p className="mt-2 truncate font-mono text-[11px] text-mist-500">
        {slot.file?.name ?? 'No image'} {regions.length > 0 && `· ${regions.length} region(s) detected`}
      </p>
    </div>
  )
}
