import { useEffect, useState } from 'react'
import { checkHealth, inspectFile, runQuery } from './api'
import { cn } from './lib/cn'
import AnswerCard from './components/AnswerCard'
import EvidencePanel from './components/EvidencePanel'
import Header from './components/Header'
import MapPanel from './components/MapPanel'
import NormalizationStrip from './components/NormalizationStrip'
import RejectionCard from './components/RejectionCard'
import TraceTimeline from './components/TraceTimeline'
import UploadPanel from './components/UploadPanel'

const EMPTY_SLOT = { file: null, meta: null, loading: false, error: null }
const EMPTY_GEOJSON = { type: 'FeatureCollection', features: [] }

function UploadIcon({ className }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 8.25 12 3.75m0 0L7.5 8.25M12 3.75v12.75"
      />
    </svg>
  )
}

function EmptyState({ compact = false }) {
  if (compact) {
    return (
      <div className="flex h-full min-h-[24rem] flex-col items-center justify-center rounded-xl border border-dashed border-navy-600 bg-navy-900 px-8 text-center">
        <UploadIcon className="mb-3 h-8 w-8 text-mist-500" />
        <p className="text-sm text-mist-300">Upload 1–2 geospatial images to begin.</p>
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-[24rem] flex-col items-center justify-center rounded-xl border border-dashed border-navy-600 bg-navy-900 px-8 text-center">
      <p className="text-sm text-mist-300">Enter a query and run Analyse to begin.</p>
      <p className="mt-2 text-xs text-mist-500">
        Evidence, confidence, and geospatial context will appear here once analysis runs.
      </p>
    </div>
  )
}

function SkeletonBlock({ className }) {
  return <div className={cn('animate-pulse rounded-lg bg-navy-700/60', className)} />
}

function EvidenceSkeleton() {
  return (
    <div className="rounded-xl border border-navy-600 bg-navy-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <SkeletonBlock className="h-3 w-20" />
        <SkeletonBlock className="h-6 w-16" />
      </div>
      <SkeletonBlock className="h-[340px] w-full" />
      <SkeletonBlock className="mt-2 h-2.5 w-1/3" />
    </div>
  )
}

function AnswerSkeleton() {
  return (
    <div className="rounded-xl border border-navy-600 bg-navy-900 p-5">
      <div className="mb-3 flex gap-2">
        <SkeletonBlock className="h-6 w-24" />
        <SkeletonBlock className="h-6 w-40" />
      </div>
      <SkeletonBlock className="h-3 w-full" />
      <SkeletonBlock className="mt-2 h-3 w-5/6" />
      <SkeletonBlock className="mt-2 h-3 w-2/3" />
      <div className="mt-5 border-t border-navy-700 pt-4">
        <SkeletonBlock className="h-2.5 w-1/4" />
        <SkeletonBlock className="mt-2 h-2 w-full" />
      </div>
    </div>
  )
}

export default function App() {
  const [slotA, setSlotA] = useState(EMPTY_SLOT)
  const [slotB, setSlotB] = useState(EMPTY_SLOT)
  const [query, setQuery] = useState('')
  const [analysing, setAnalysing] = useState(false)
  const [response, setResponse] = useState(null)
  const [fetchError, setFetchError] = useState(null)
  const [resultVersion, setResultVersion] = useState(0)
  const [backendOnline, setBackendOnline] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function poll() {
      const ok = await checkHealth()
      if (!cancelled) setBackendOnline(ok)
    }
    poll()
    const id = setInterval(poll, 20000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  async function handleFile(slotKey, file) {
    const setSlot = slotKey === 'A' ? setSlotA : setSlotB
    setSlot({ file, meta: null, loading: true, error: null })
    try {
      const meta = await inspectFile(file)
      setSlot({ file, meta, loading: false, error: null })
    } catch (e) {
      setSlot({ file, meta: null, loading: false, error: e.message })
    }
  }

  function handleRemoveFile(slotKey) {
    const setSlot = slotKey === 'A' ? setSlotA : setSlotB
    setSlot(EMPTY_SLOT)
  }

  async function handleAnalyse() {
    if (!slotA.file || !query.trim()) return
    setAnalysing(true)
    setFetchError(null)
    try {
      const files = [slotA.file]
      if (slotB.file) files.push(slotB.file)
      const data = await runQuery(files, query)
      setResponse(data)
      setResultVersion((v) => v + 1)
    } catch (e) {
      setFetchError(e.message)
      setResponse(null)
    } finally {
      setAnalysing(false)
    }
  }

  const canAnalyse = Boolean(slotA.file) && query.trim().length > 0
  const fallbackCentroid = slotA.meta?.centroid ?? slotB.meta?.centroid ?? null
  const hasUpload = Boolean(slotA.file || slotB.file)

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header backendOnline={backendOnline} />

      <main className="mx-auto grid w-full min-h-0 max-w-[1600px] flex-1 grid-cols-1 gap-6 overflow-hidden p-6 lg:grid-cols-[360px_1fr_420px] lg:p-8">
        <UploadPanel
          slotA={slotA}
          slotB={slotB}
          onFile={handleFile}
          onRemoveFile={handleRemoveFile}
          query={query}
          onQueryChange={setQuery}
          onAnalyse={handleAnalyse}
          analysing={analysing}
          canAnalyse={canAnalyse}
        />

        <section className="flex min-h-0 flex-col gap-6 overflow-y-auto pr-1">
          {fetchError && (
            <div className="rounded-xl border border-danger/50 bg-danger/10 p-4 text-sm text-danger">
              {fetchError}
            </div>
          )}

          {!response && !analysing && !fetchError && <EmptyState compact={!hasUpload} />}

          {analysing && !response && (
            <>
              <EvidenceSkeleton />
              <AnswerSkeleton />
            </>
          )}

          {response && response.rejected && <RejectionCard validations={response.validations} />}

          {response && !response.rejected && (
            <>
              <EvidencePanel slotA={slotA} slotB={slotB} overlayRegions={response.overlay_regions} />
              <NormalizationStrip plans={response.normalization_plan} />
              <AnswerCard response={response} images={[slotA.meta, slotB.meta].filter(Boolean)} />
            </>
          )}
        </section>

        <section className="flex min-h-0 flex-col gap-6 overflow-y-auto pr-1">
          {hasUpload ? (
            <>
              <MapPanel
                geojson={response?.geojson ?? EMPTY_GEOJSON}
                resultVersion={resultVersion}
                fallbackCentroid={fallbackCentroid}
              />
              <TraceTimeline trace={response?.trace} pending={analysing} />
            </>
          ) : (
            <div className="flex h-full min-h-[24rem] flex-col items-center justify-center rounded-xl border border-dashed border-navy-600 bg-navy-900 px-8 text-center">
              <UploadIcon className="mb-3 h-8 w-8 text-mist-500" />
              <p className="text-sm text-mist-300">Upload 1–2 geospatial images to begin.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
