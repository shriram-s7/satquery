import { cn } from '../lib/cn'

export default function Chip({ children, tone = 'default' }) {
  const tones = {
    default: 'bg-navy-700 text-mist-300 border-navy-500',
    cyan: 'bg-cyan-glow/10 text-cyan-glow border-cyan-glow/40',
    warn: 'bg-warn/10 text-warn border-warn/40',
    danger: 'bg-danger/10 text-danger border-danger/40',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-3 py-1 font-mono text-[11px] leading-none',
        tones[tone] ?? tones.default,
      )}
    >
      {children}
    </span>
  )
}
