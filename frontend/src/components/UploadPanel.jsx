import DropZone from './DropZone'
import MetadataCard from './MetadataCard'

export default function UploadPanel({ slotA, slotB, onFile, query, onQueryChange, onAnalyse, analysing, canAnalyse }) {
  return (
    <section className="flex h-full flex-col rounded-xl border border-navy-600 bg-navy-900 p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-mist-300">Imagery</h2>

      <div className="space-y-5">
        <div>
          <DropZone label="Image A / T1" file={slotA.file} onFile={(f) => onFile('A', f)} />
          <MetadataCard meta={slotA.meta} loading={slotA.loading} error={slotA.error} />
        </div>

        <div>
          <DropZone label="Image B / T2" sublabel="optional" file={slotB.file} onFile={(f) => onFile('B', f)} />
          <MetadataCard meta={slotB.meta} loading={slotB.loading} error={slotB.error} />
        </div>
      </div>

      <div className="mt-6 border-t border-navy-700 pt-5">
        <label htmlFor="query" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-mist-300">
          Query
        </label>
        <textarea
          id="query"
          rows={3}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="e.g. what changed between these two images"
          className="w-full resize-none rounded-lg border border-navy-600 bg-navy-850 px-3 py-2 text-sm text-mist-100 placeholder:text-mist-500 outline-none transition-colors focus:border-cyan-glow"
        />

        <button
          type="button"
          onClick={onAnalyse}
          disabled={!canAnalyse || analysing}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-glow px-4 py-2.5 text-sm font-semibold text-navy-950 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {analysing && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-navy-950/30 border-t-navy-950" />
          )}
          {analysing ? 'Analysing…' : 'Analyse'}
        </button>
      </div>
    </section>
  )
}
