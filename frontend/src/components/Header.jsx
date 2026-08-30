import { cn } from '../lib/cn'

export default function Header({ backendOnline }) {
  return (
    <header className="flex items-center justify-between border-b border-navy-700 bg-navy-900/80 px-8 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-glow to-teal-glow text-sm font-bold text-navy-950">
          SQ
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-mist-100">SatQuery AI</h1>
          <p className="text-[11px] text-mist-500">SIH 2026 · PS 26167 · ISRO</p>
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-full border border-navy-600 bg-navy-850 px-3 py-1.5">
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            backendOnline === null ? 'bg-mist-500' : backendOnline ? 'bg-ok' : 'bg-danger',
          )}
        />
        <span className="font-mono text-[11px] text-mist-300">
          {backendOnline === null ? 'checking backend…' : backendOnline ? 'backend online' : 'backend unreachable'}
        </span>
      </div>
    </header>
  )
}
