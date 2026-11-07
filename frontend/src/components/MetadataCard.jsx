import Badge from './Badge'

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-[11px] text-mist-500">{label}</span>
      <span className="font-mono text-[12px] text-mist-100">{value}</span>
    </div>
  )
}

export default function MetadataCard({ meta, loading, error }) {
  if (loading) {
    return (
      <div className="mt-2 animate-pulse rounded-lg border border-navy-600 bg-navy-850 p-3">
        <div className="h-3 w-2/3 rounded bg-navy-700" />
        <div className="mt-2 h-2 w-full rounded bg-navy-700" />
        <div className="mt-2 h-2 w-5/6 rounded bg-navy-700" />
        <div className="mt-2 h-2 w-4/6 rounded bg-navy-700" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mt-2 rounded-lg border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
        {error}
      </div>
    )
  }

  if (!meta) return null

  const [gx, gy] = meta.gsd_metres ?? [null, null]
  const gsdLabel = gx != null ? `${gx.toFixed(2)} × ${gy.toFixed(2)} m/px` : 'n/a'
  const centroidLabel = meta.centroid
    ? `${meta.centroid.lat.toFixed(4)}, ${meta.centroid.lon.toFixed(4)}`
    : 'n/a'

  return (
    <div className="mt-2 rounded-lg border border-navy-600 bg-navy-850 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="truncate font-mono text-xs text-mist-100">{meta.filename}</p>
        {meta.has_geo ? (
          <Badge modality={meta.modality} />
        ) : (
          <span className="shrink-0 rounded-md border border-warn/40 bg-warn/10 px-2 py-1 text-[11px] font-semibold uppercase text-warn">
            No geo
          </span>
        )}
      </div>
      <div className="divide-y divide-navy-700/70">
        <Row label="CRS" value={meta.crs ?? 'n/a'} />
        <Row label="GSD" value={gsdLabel} />
        <Row label="Bands" value={`${meta.band_count} · ${meta.dtype}`} />
        <Row label="Size" value={`${meta.width} × ${meta.height} px`} />
        <Row label="Centroid (WGS84)" value={centroidLabel} />
      </div>
    </div>
  )
}
