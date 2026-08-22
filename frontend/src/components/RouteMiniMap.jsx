import { MapContainer, TileLayer, Marker, Polyline, useMap } from "react-leaflet"
import L from "leaflet"
import { useEffect, useMemo } from "react"
import { Factory } from "lucide-react"
import { VEHICLE_COLORS, DEPOT_COORDS } from "@/constants"

const vehicleColors = VEHICLE_COLORS

function createStopIcon(color, label) {
  return L.divIcon({
    className: "custom-leaflet-pin",
    html: `
      <div style="transform: scale(0.85); display:flex; flex-direction:column; align-items:center;">
        <div style="background:${color}; color:white; width:22px; height:22px; border-radius:50% 50% 50% 0; transform:rotate(-45deg); display:flex; align-items:center; justify-content:center; border:2px solid white; box-shadow:0 2px 6px rgba(0,0,0,0.4);">
          <span style="transform:rotate(45deg); font-size:9px; font-weight:800; line-height:1;">${label}</span>
        </div>
      </div>`,
    iconSize: [22, 28],
    iconAnchor: [11, 28],
  })
}

function createDepotIcon() {
  return L.divIcon({
    className: "custom-depot-marker",
    html: `
      <div style="display:flex; flex-direction:column; align-items:center;">
        <div style="background:#dc2626; color:white; width:26px; height:26px; border-radius:50% 50% 50% 0; transform:rotate(-45deg); display:flex; align-items:center; justify-content:center; border:2px solid white; box-shadow:0 3px 8px rgba(220,38,38,0.5);">
          <svg transform="rotate(45)" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 1 2-2h7l-3 5v6"/></svg>
        </div>
      </div>`,
    iconSize: [26, 32],
    iconAnchor: [13, 32],
  })
}

function FitBounds({ positions }) {
  const map = useMap()
  useEffect(() => {
    if (!positions || positions.length === 0) return
    const bounds = L.latLngBounds(positions)
    if (positions.length === 1) {
      map.setView(positions[0], 13)
    } else {
      map.fitBounds(bounds, { padding: [30, 30] })
    }
  }, [positions, map])
  return null
}

function RouteMiniMap({ route, depotLat = DEPOT_COORDS.lat, depotLng = DEPOT_COORDS.lng, colorIndex = 0, className = "" }) {
  const color = vehicleColors[colorIndex % vehicleColors.length]
  const stops = route?.stops || []

  const positions = useMemo(() => {
    const pts = [[depotLat, depotLng]]
    stops.forEach((s) => {
      if (s.lat && s.lng) pts.push([s.lat, s.lng])
    })
    if (stops.length > 0 && stops[stops.length - 1].lat && stops[stops.length - 1].lng) {
      pts.push([depotLat, depotLng])
    }
    return pts
  }, [stops, depotLat, depotLng])

  const center = useMemo(() => {
    if (positions.length === 0) return [depotLat, depotLng]
    const lats = positions.map((p) => p[0])
    const lngs = positions.map((p) => p[1])
    return [(lats.reduce((a, b) => a + b, 0) / lats.length), (lngs.reduce((a, b) => a + b, 0) / lngs.length)]
  }, [positions, depotLat, depotLng])

  if (!stops || stops.length === 0) {
    return (
      <div className={className + " flex h-64 items-center justify-center rounded-xl border bg-muted/30 text-xs text-muted-foreground"}>
        ไม่มีข้อมูลพิกัดสำหรับเส้นทางนี้
      </div>
    )
  }

  return (
    <div className={className + " overflow-hidden rounded-xl border shadow-sm"}>
      <MapContainer
        center={center}
        zoom={11}
        style={{ height: "256px", width: "100%" }}
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

        <FitBounds positions={positions} />

        <Marker position={[depotLat, depotLng]} icon={createDepotIcon()} />

        {stops.map((stop, idx) =>
          stop.lat && stop.lng ? (
            <Marker key={idx} position={[stop.lat, stop.lng]} icon={createStopIcon(color, String(idx + 1))} />
          ) : null
        )}

        {positions.length > 1 && (
          <Polyline positions={positions} pathOptions={{ color, weight: 3, opacity: 0.85, dashArray: "6, 5" }} />
        )}
      </MapContainer>
    </div>
  )
}

export default RouteMiniMap
