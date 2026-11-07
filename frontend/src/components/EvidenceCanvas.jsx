import { useEffect, useRef, useState } from 'react'

const MAX_CANVAS_DIM = 720
const DISPLAY_HEIGHT = 340

function project(lon, lat, bounds) {
  const [west, south, east, north] = bounds
  const x = (lon - west) / (east - west || 1)
  const y = (north - lat) / (north - south || 1)
  return [x, y]
}

export default function EvidenceCanvas({ imageSrc, imageBounds, regions }) {
  const canvasRef = useRef(null)
  const [img, setImg] = useState(null)

  useEffect(() => {
    setImg(null)
    if (!imageSrc) return
    const el = new Image()
    el.onload = () => setImg(el)
    el.src = imageSrc
    return () => {
      el.onload = null
    }
  }, [imageSrc])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    if (!img) {
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      return
    }

    const scale = Math.min(1, MAX_CANVAS_DIM / Math.max(img.naturalWidth, img.naturalHeight))
    const w = Math.max(1, Math.round(img.naturalWidth * scale))
    const h = Math.max(1, Math.round(img.naturalHeight * scale))
    canvas.width = w
    canvas.height = h

    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, w, h)
    ctx.drawImage(img, 0, 0, w, h)

    if (!imageBounds || !regions?.length) return

    ctx.lineWidth = 2
    ctx.strokeStyle = '#22d3ee'
    ctx.font = '600 12px "JetBrains Mono", monospace'

    regions.forEach((region, idx) => {
      const ring = region.bbox_wgs84
      if (!ring?.length) return
      const lons = ring.map((p) => p[0])
      const lats = ring.map((p) => p[1])
      const [x0, y0] = project(Math.min(...lons), Math.max(...lats), imageBounds)
      const [x1, y1] = project(Math.max(...lons), Math.min(...lats), imageBounds)

      const rx = x0 * w
      const ry = y0 * h
      const rw = (x1 - x0) * w
      const rh = (y1 - y0) * h

      ctx.strokeStyle = '#22d3ee'
      ctx.fillStyle = 'rgba(34, 211, 238, 0.10)'
      ctx.fillRect(rx, ry, rw, rh)
      ctx.strokeRect(rx, ry, rw, rh)

      const tag = `#${idx + 1} · ${(region.confidence ?? 0).toFixed(2)}`
      const tagPad = 2
      const tagW = ctx.measureText(tag).width + tagPad * 2
      const tagH = 12 + tagPad * 2
      const tagX = Math.min(Math.max(rx, 0), Math.max(0, w - tagW))
      const tagY = Math.max(0, ry - tagH)
      ctx.fillStyle = '#04070d'
      ctx.fillRect(tagX, tagY, tagW, tagH)
      ctx.fillStyle = '#22d3ee'
      ctx.fillText(tag, tagX + tagPad, tagY + tagH - tagPad - 3)
    })
  }, [img, imageBounds, regions])

  return (
    <div
      className="relative flex items-center justify-center overflow-hidden rounded-lg border border-navy-600 bg-navy-950"
      style={{ height: DISPLAY_HEIGHT }}
    >
      <canvas ref={canvasRef} className={img ? 'block h-full w-full object-contain' : 'hidden'} />
      {!img && (
        <div className="text-xs text-mist-500">{imageSrc ? 'Loading imagery…' : 'No preview available'}</div>
      )}
    </div>
  )
}
