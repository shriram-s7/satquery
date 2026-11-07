import 'leaflet/dist/leaflet.css'
import { useEffect } from 'react'
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'

const INDIA_CENTER = [22.9734, 78.6569]
const DEFAULT_ZOOM = 4

const REGION_STYLE = {
  color: '#22d3ee',
  weight: 2,
  fillColor: '#22d3ee',
  fillOpacity: 0.15,
}

function Recenter({ lat, lon, active }) {
  const map = useMap()
  useEffect(() => {
    if (active && lat != null && lon != null) {
      map.setView([lat, lon], 15)
    }
  }, [active, lat, lon, map])
  return null
}

function onEachFeature(feature, layer) {
  const p = feature.properties ?? {}
  const conf = typeof p.confidence === 'number' ? p.confidence.toFixed(2) : 'n/a'
  layer.bindTooltip(`tile ${JSON.stringify(p.tile_index ?? [])} · confidence ${conf}`, { sticky: true })
}

function RegionsLayer({ geojson, resultVersion }) {
  const map = useMap()

  return (
    <GeoJSON
      key={resultVersion}
      data={geojson}
      style={() => REGION_STYLE}
      onEachFeature={onEachFeature}
      eventHandlers={{
        add: (e) => {
          const bounds = e.target.getBounds()
          if (bounds.isValid()) map.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 })
        },
      }}
    />
  )
}

export default function MapPanel({ geojson, resultVersion, fallbackCentroid }) {
  const hasRegions = Boolean(geojson?.features?.length)

  return (
    <div className="overflow-hidden rounded-xl border border-navy-600 bg-navy-900">
      <div className="border-b border-navy-700 px-4 py-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-mist-300">Geospatial context</h3>
      </div>
      <div className="h-72">
        <MapContainer center={INDIA_CENTER} zoom={DEFAULT_ZOOM} className="h-full w-full">
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Recenter lat={fallbackCentroid?.lat} lon={fallbackCentroid?.lon} active={!hasRegions} />
          {hasRegions && <RegionsLayer geojson={geojson} resultVersion={resultVersion} />}
        </MapContainer>
      </div>
    </div>
  )
}
