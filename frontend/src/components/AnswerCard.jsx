import { useState } from 'react'
import { fetchReportPdf } from '../api'
import { downloadBlob } from '../lib/download'
import Chip from './Chip'
import ConfidenceBar from './ConfidenceBar'

const INTENT_LABEL = {
  vqa: 'VQA',
  captioning: 'Captioning',
  grounding: 'Grounding',
  change_detection: 'Change detection',
  fusion: 'Fusion',
  unknown: 'Unknown',
}

function formatSignal(sig) {
  const match = /^image_count=(\d+)$/.exec(sig)
  if (!match) return sig
  const count = Number(match[1])
  return `${count} image${count === 1 ? '' : 's'}`
}

function DownloadIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className="h-3.5 w-3.5"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M7.5 12l4.5 4.5m0 0 4.5-4.5m-4.5 4.5V3"
      />
    </svg>
  )
}

export default function AnswerCard({ response, images }) {
  const { answer_text, confidence, intent, validations, geojson } = response
  const warnings = (validations ?? []).filter((v) => v.severity === 'warn')

  const [downloadingReport, setDownloadingReport] = useState(false)
  const [downloadError, setDownloadError] = useState(null)

  async function handleDownloadReport() {
    setDownloadingReport(true)
    setDownloadError(null)
    try {
      const blob = await fetchReportPdf(response, images ?? [])
      downloadBlob(blob, 'satquery-report.pdf')
    } catch (e) {
      setDownloadError(e.message)
    } finally {
      setDownloadingReport(false)
    }
  }

  function handleDownloadGeojson() {
    const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/geo+json' })
    downloadBlob(blob, 'satquery-regions.geojson')
  }

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-900 p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-md border border-cyan-glow/40 bg-cyan-glow/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-cyan-glow">
          {INTENT_LABEL[intent.intent] ?? intent.intent}
        </span>
        <span className="font-mono text-[11px] text-mist-500">
          {intent.method} · intent confidence {(intent.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <p className="text-[15px] leading-relaxed text-mist-100">{answer_text}</p>

      {intent.matched_signals?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {intent.matched_signals.map((sig) => (
            <Chip key={sig}>{formatSignal(sig)}</Chip>
          ))}
        </div>
      )}

      <div className="mt-5 border-t border-navy-700 pt-4">
        <ConfidenceBar value={confidence} label="Overall confidence" />
      </div>

      {warnings.length > 0 && (
        <div className="mt-4 space-y-2 border-t border-navy-700 pt-4">
          {warnings.map((w) => (
            <p key={w.message} className="text-xs leading-relaxed text-warn">
              {w.message}
            </p>
          ))}
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2 border-t border-navy-700 pt-4">
        <button
          type="button"
          onClick={handleDownloadReport}
          disabled={downloadingReport}
          className="inline-flex items-center gap-2 rounded-md border border-navy-500 bg-navy-850 px-3 py-2 text-xs font-medium text-mist-100 transition-colors hover:border-cyan-glow hover:text-cyan-glow disabled:cursor-not-allowed disabled:opacity-50"
        >
          <DownloadIcon />
          {downloadingReport ? 'Generating report…' : 'Download Report'}
        </button>
        <button
          type="button"
          onClick={handleDownloadGeojson}
          className="inline-flex items-center gap-2 rounded-md border border-navy-500 bg-navy-850 px-3 py-2 text-xs font-medium text-mist-100 transition-colors hover:border-cyan-glow hover:text-cyan-glow"
        >
          <DownloadIcon />
          Download GeoJSON
        </button>
      </div>

      {downloadError && <p className="mt-2 text-xs text-danger">{downloadError}</p>}
    </div>
  )
}
