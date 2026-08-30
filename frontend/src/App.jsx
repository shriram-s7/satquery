import { useEffect, useState } from 'react'
import { checkHealth, inspectFile, runQuery } from './api'
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

function EmptyState() {
  return (
    <div className="flex h-full min-h-[24rem] flex-col items-center justify-center rounded-xl border border-dashed border-navy-600 bg-navy-900 px-8 text-center">
      <p className="text-sm text-mist-300">Upload Image A and enter a query to begin.</p>
      <p className="mt-1 text-xs text-mist-500">
        Evidence, confidence, and geospatial context will appear here once analysis runs.
      </p>
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

  return (
    <div className="flex min-h-screen flex-col">
      <Header backendOnline={backendOnline} />

      <main className="mx-auto grid w-full max-w-[1600px] flex-1 grid-cols-1 gap-6 p-6 lg:grid-cols-[360px_1fr_420px] lg:p-8">
        <UploadPanel
          slotA={slotA}
          slotB={slotB}
          onFile={handleFile}
          query={query}
          onQueryChange={setQuery}
          onAnalyse={handleAnalyse}
          analysing={analysing}
          canAnalyse={canAnalyse}
        />

        <section className="flex flex-col gap-6">
          {fetchError && (
            <div className="rounded-xl border border-danger/50 bg-danger/10 p-4 text-sm text-danger">
              {fetchError}
            </div>
          )}

          {!response && !analysing && !fetchError && <EmptyState />}

          {analysing && !response && (
            <div className="flex h-full min-h-[24rem] flex-col items-center justify-center gap-3 rounded-xl border border-navy-600 bg-navy-900">
              <span className="h-6 w-6 animate-spin rounded-full border-2 border-navy-600 border-t-cyan-glow" />
              <p className="text-xs text-mist-500">Running the pipeline…</p>
            </div>
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

        <section className="flex flex-col gap-6">
          <MapPanel
            geojson={response?.geojson ?? EMPTY_GEOJSON}
            resultVersion={resultVersion}
            fallbackCentroid={fallbackCentroid}
          />
          <TraceTimeline trace={response?.trace} />
        </section>
      </main>
    </div>
  )
}
