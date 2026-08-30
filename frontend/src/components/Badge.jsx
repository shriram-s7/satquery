import { cn } from '../lib/cn'

const MODALITY_LABEL = {
  optical_rgb: 'Optical RGB',
  sar: 'SAR',
  multispectral: 'Multispectral',
  panchromatic: 'Panchromatic',
  unknown: 'Unknown modality',
}

export default function Badge({ modality }) {
  const label = MODALITY_LABEL[modality] ?? modality ?? 'Unknown'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-teal-glow/30 bg-teal-glow/10',
        'px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-teal-glow',
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-teal-glow" />
      {label}
    </span>
  )
}
