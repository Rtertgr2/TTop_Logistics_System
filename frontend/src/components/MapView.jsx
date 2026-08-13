import { useState, useEffect, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Map, Satellite, Maximize2, Minimize2, Search, Truck, Package, MapPin, Scale, Navigation, Save, Factory, ExternalLink, Crosshair, Info, Target } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { VEHICLE_COLORS, DEPOT_COORDS } from '@/constants'

const vehicleColors = VEHICLE_COLORS

function htmlEscape(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function MapFlyToController({ targetLocation }) {
  const map = useMap()
  useEffect(() => {
    if (targetLocation && targetLocation.lat && targetLocation.lng) {
      map.flyTo([targetLocation.lat, targetLocation.lng], 16, { animate: true, duration: 1.5 })
    }
  }, [targetLocation, map])
  return null
}

function createCustomMarkerIcon(color, label, isSelected) {
  const scale = isSelected ? 'scale(1.3)' : 'scale(1)'
  const borderCol = isSelected ? '#fbbf24' : 'white'
  const safeColor = htmlEscape(color)
  const safeLabel = htmlEscape(label)

  return L.divIcon({
    className: 'custom-leaflet-pin',
    html: `
      <div style="
        transform: ${scale};
        transition: transform 0.2s ease;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        align-items: center;
      ">
        <div style="
          background: ${safeColor};
          color: white;
          width: 26px;
          height: 26px;
          border-radius: 50% 50% 50% 0;
          transform: rotate(-45deg);
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid ${borderCol};
          box-shadow: 0 3px 8px rgba(0,0,0,0.4);
        ">
          <span style="
            transform: rotate(45deg);
            font-size: 10px;
            font-weight: 800;
            line-height: 1;
            white-space: nowrap;
          ">${safeLabel}</span>
        </div>
      </div>
    `,
    iconSize: [26, 32],
    iconAnchor: [13, 32],
    popupAnchor: [0, -30],
  })
}

function createDepotIcon() {
  return L.divIcon({
    className: 'custom-depot-marker',
    html: `
      <div style="cursor: pointer; display: flex; flex-direction: column; align-items: center;">
        <div style="
          background: #dc2626;
          color: white;
          width: 32px;
          height: 32px;
          border-radius: 50% 50% 50% 0;
          transform: rotate(-45deg);
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2.5px solid white;
          box-shadow: 0 4px 10px rgba(220,38,38,0.5);
        ">
          <svg transform="rotate(45)" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 1 2-2h7l-3 5v6"/></svg>
        </div>
      </div>
    `,
    iconSize: [32, 38],
    iconAnchor: [16, 38],
    popupAnchor: [0, -36],
  })
}

function roundCoord(val) {
  return Math.round(val * 1000000) / 1000000
}

function MapView({ routes = [], orders = [], onVerified = null, depotLat = DEPOT_COORDS.lat, depotLng = DEPOT_COORDS.lng }) {
  const [mapType, setMapType] = useState('standard')
  const [selectedStop, setSelectedStop] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [localRoutes, setLocalRoutes] = useState(routes)
  const [localOrders, setLocalOrders] = useState(orders)

  useEffect(() => { setLocalRoutes(routes) }, [routes])
  useEffect(() => { setLocalOrders(orders) }, [orders])

  const [placeSearchQuery, setPlaceSearchQuery] = useState('')
  const [placeSearchResults, setPlaceSearchResults] = useState([])
  const [isSearchingPlace, setIsSearchingPlace] = useState(false)
  const searchDebounceRef = useRef(null)

  const updateStopLocationInState = (stopItem, newLat, newLng, newAddress = null) => {
    setLocalRoutes(prevRoutes => {
      if (!prevRoutes || prevRoutes.length === 0) return prevRoutes
      return prevRoutes.map(r => ({
        ...r,
        stops: r.stops.map(s => {
          if (
            (s.order_number && s.order_number === stopItem.order_number) ||
            (s.id && s.id === stopItem.id) ||
            (s.customer === stopItem.customer && s.address === stopItem.address)
          ) {
            return { ...s, lat: newLat, lng: newLng, raw_lat: s.raw_lat || newLat, raw_lng: s.raw_lng || newLng, verified_lat: newLat, verified_lng: newLng, address: newAddress || s.address, verified_address: newAddress || s.verified_address, confidence_score: 100.0, is_verified: true }
          }
          return s
        })
      }))
    })
    setLocalOrders(prevOrders => {
      if (!prevOrders || prevOrders.length === 0) return prevOrders
      return prevOrders.map(o => {
        if (
          (o.order_number && o.order_number === stopItem.order_number) ||
          (o.id && o.id === stopItem.id) ||
          (o.customer === stopItem.customer && o.address === stopItem.address)
        ) {
          return { ...o, lat: newLat, lng: newLng, raw_lat: o.raw_lat || newLat, raw_lng: o.raw_lng || newLng, verified_lat: newLat, verified_lng: newLng, address: newAddress || o.address, confidence_score: 100.0, is_verified: true }
        }
        return o
      })
    })
  }

  const handleSearchPlaceOnline = async (queryStr) => {
    if (!queryStr || queryStr.trim().length < 2) { setPlaceSearchResults([]); return }
    setIsSearchingPlace(true)
    try {
      const res = await fetch(`/api/v1/search-place?address=${encodeURIComponent(queryStr)}`)
      if (res.ok) {
        const data = await res.json()
        setPlaceSearchResults(data.results || [])
      }
    } catch (err) {
      console.error('Search location error:', err)
    } finally {
      setIsSearchingPlace(false)
    }
  }

  const handleSaveLocationToDB = async (stopItem, customLat, customLng) => {
    if (!stopItem) return
    const latToSave = customLat || stopItem.lat
    const lngToSave = customLng || stopItem.lng
    updateStopLocationInState(stopItem, latToSave, lngToSave)
    try {
      if (stopItem.id) {
        const res = await fetch(`/api/v1/orders/${stopItem.id}/verify-location`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lat: latToSave, lng: lngToSave, verified_by: 'user_frontend_map' })
        })
        if (res.ok && onVerified) onVerified(stopItem.id, latToSave, lngToSave)
      }
      setSelectedStop({ ...stopItem, lat: latToSave, lng: lngToSave, is_verified: true, confidence_score: 100.0 })
      toast.success(`บันทึกสถานที่จัดส่งของ "${stopItem.customer}" (Lat: ${latToSave}, Lng: ${lngToSave}) เรียบร้อยแล้ว`)
    } catch (err) {
      console.error('Save location to DB error:', err)
      toast.error('เกิดข้อผิดพลาดในการบันทึกลงฐานข้อมูล')
    }
  }

  const handleApplySearchedLocation = async (place, stopItem) => {
    if (!stopItem) return
    const newLat = roundCoord(place.lat)
    const newLng = roundCoord(place.lng)
    const newAddress = place.display_name
    updateStopLocationInState(stopItem, newLat, newLng, newAddress)
    await handleSaveLocationToDB(stopItem, newLat, newLng)
    setPlaceSearchResults([])
    setPlaceSearchQuery('')
  }

  const tileUrls = {
    standard: {
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    },
    satellite: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri'
    }
  }

  const allStops = []
  if (localRoutes && localRoutes.length > 0) {
    localRoutes.forEach((route, rIdx) => {
      route.stops.forEach((stop, sIdx) => {
        allStops.push({ ...stop, vehicle_id: route.vehicle_id, vehicle_name: route.name, driver: route.driver, plate: route.plate, color: vehicleColors[rIdx % vehicleColors.length], stop_number: sIdx + 1, label: `${route.vehicle_id}.${sIdx + 1}` })
      })
    })
  } else if (localOrders && localOrders.length > 0) {
    localOrders.forEach((order, idx) => {
      allStops.push({ ...order, vehicle_id: 1, color: '#6366f1', stop_number: idx + 1, label: `${idx + 1}` })
    })
  }

  const validPositions = allStops.filter(s => s.lat && s.lng).map(s => [s.lat, s.lng])
  if (validPositions.length === 0) validPositions.push([depotLat, depotLng])
  const centerLat = validPositions.reduce((sum, p) => sum + p[0], 0) / validPositions.length
  const centerLng = validPositions.reduce((sum, p) => sum + p[1], 0) / validPositions.length

  const filteredStops = searchQuery.trim()
    ? allStops.filter(s =>
        (s.customer || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (s.address || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (s.order_number || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : allStops

  const handleOpenGoogleMapsReal = (lat, lng, address) => {
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      window.open(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`, '_blank')
    } else if (address) {
      window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`, '_blank')
    }
  }

  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className={cn("flex flex-col gap-3", isExpanded && "fixed inset-0 z-50 bg-background p-4")}>
      {/* Control Bar */}
      <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setMapType('standard')}
            className={cn("flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors", mapType === 'standard' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent")}
          >
            <Map className="h-4 w-4" /> แผนที่ถนน
          </button>
          <button
            onClick={() => setMapType('satellite')}
            className={cn("flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors", mapType === 'satellite' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent")}
          >
            <Satellite className="h-4 w-4" /> ดาวเทียม
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600"
          >
            {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            {isExpanded ? 'ย่อแผนที่' : 'ขยายแผนที่'}
          </button>
        </div>
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="ค้นหาชื่อลูกค้า, ที่อยู่ หรือ SO..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-transparent pl-9 pr-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
      </div>

      <div className={cn("grid gap-3", isExpanded ? "grid-cols-1" : "grid-cols-1 lg:grid-cols-3")}>
        {/* Map */}
        <div className={cn(isExpanded ? "order-1" : "lg:col-span-2")}>
          <div className="overflow-hidden rounded-xl border shadow-sm">
            <MapContainer
              center={[centerLat, centerLng]}
              zoom={11}
              style={{ height: isExpanded ? '80vh' : '600px', width: '100%' }}
            >
              <TileLayer url={tileUrls[mapType].url} attribution={tileUrls[mapType].attribution} />
              <MapFlyToController targetLocation={selectedStop} />

              <Marker position={[depotLat, depotLng]} icon={createDepotIcon()}>
                <Popup>
                  <div className="space-y-1">
                    <p className="flex items-center gap-1.5 font-semibold"><Factory className="h-4 w-4 text-red-600" /> คลังสินค้าหลัก (Depot)</p>
                    <p className="text-sm">บริษัท ทรีท็อปเคมิคัลแอนด์ฟู้ดส์ คอร์ปอเรชั่น จำกัด</p>
                    <p className="text-xs text-muted-foreground">20/2 ถนนบรมราชชนนี ตลิ่งชัน กรุงเทพฯ 10170</p>
                  </div>
                </Popup>
              </Marker>

              {allStops.map((stop, idx) => {
                const sLat = stop.lat || (depotLat + (idx * 0.005))
                const sLng = stop.lng || (depotLng + (idx * 0.005))
                const isSelected = selectedStop?.order_number === stop.order_number
                const confScore = stop.confidence_score !== undefined ? stop.confidence_score : 30.0
                return (
                  <Marker
                    key={`${stop.vehicle_id}-${idx}-${sLat}-${sLng}`}
                    position={[sLat, sLng]}
                    draggable={true}
                    icon={createCustomMarkerIcon(stop.color, stop.label, isSelected)}
                    eventHandlers={{
                      click: () => setSelectedStop({ ...stop, lat: sLat, lng: sLng }),
                      dragend: async (e) => {
                        const newLatLng = e.target.getLatLng()
                        const newLat = roundCoord(newLatLng.lat)
                        const newLng = roundCoord(newLatLng.lng)
                        let newAddress = stop.verified_address || stop.address
                        try {
                          const res = await fetch(`/api/v1/reverse-geocode?lat=${newLat}&lng=${newLng}`)
                          const data = await res.json()
                          if (data.formatted_address) newAddress = data.formatted_address
                          if (stop.id) {
                            await fetch(`/api/v1/orders/${stop.id}/verify-location`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ lat: newLat, lng: newLng, verified_by: 'user_dragged_pin' })
                            })
                          }
                        } catch (err) { console.warn('Reverse geocode error:', err) }
                        updateStopLocationInState(stop, newLat, newLng, newAddress)
                        setSelectedStop({ ...stop, lat: newLat, lng: newLng, address: newAddress, verified_address: newAddress, is_verified: true, confidence_score: 100.0 })
                      }
                    }}
                  >
                    <Popup>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="rounded px-2 py-0.5 text-xs font-semibold text-white" style={{ backgroundColor: stop.color }}>
                            <Truck className="mr-1 inline h-3 w-3" /> รถคันที่ {stop.vehicle_id} · จุดที่ {stop.stop_number}
                          </span>
                          <span className="text-xs font-bold text-slate-600">{stop.is_verified ? '100%' : `${Math.round(confScore)}%`}</span>
                        </div>
                        <p className="flex items-center gap-1.5 font-semibold"><Package className="h-4 w-4" /> {stop.customer}</p>
                        {stop.order_number && <p className="text-xs text-muted-foreground">SO: {stop.order_number}</p>}
                        <p className="flex items-center gap-1.5 text-sm text-muted-foreground"><MapPin className="h-3.5 w-3.5" /> {stop.verified_address || stop.address}</p>
                        <div className="flex gap-3 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1"><Scale className="h-3.5 w-3.5" /> {stop.weight} kg</span>
                          {stop.zone && <span className="flex items-center gap-1"><Map className="h-3.5 w-3.5" /> {stop.zone}</span>}
                        </div>
                        <p className="text-xs text-muted-foreground">พิกัด: {sLat.toFixed(6)}, {sLng.toFixed(6)}</p>
                        <p className="flex items-center gap-1 text-xs font-semibold text-emerald-600"><Info className="h-3.5 w-3.5" /> สามารถลากหมุดเพื่อยืนยันพิกัดได้ทันที</p>
                        <button
                          onClick={() => handleOpenGoogleMapsReal(sLat, sLng, stop.address)}
                          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90"
                        >
                          <ExternalLink className="h-3.5 w-3.5" /> นำทาง (Google Maps)
                        </button>
                        <button
                          onClick={() => handleSaveLocationToDB(stop, sLat, sLng)}
                          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-600"
                        >
                          <Save className="h-3.5 w-3.5" /> บันทึกตำแหน่งถาวร
                        </button>
                      </div>
                    </Popup>
                  </Marker>
                )
              })}

              {(localRoutes || []).map((route, rIdx) => {
                const color = vehicleColors[rIdx % vehicleColors.length]
                const pos = [[depotLat, depotLng]]
                route.stops.forEach(s => { if (s.lat && s.lng) pos.push([s.lat, s.lng]) })
                if (pos.length > 1) pos.push([depotLat, depotLng])
                return (
                  <Polyline key={rIdx} positions={pos} pathOptions={{ color, weight: 4, opacity: 0.8, dashArray: '8, 6' }} />
                )
              })}
            </MapContainer>
          </div>
        </div>

        {/* Inspector Panel */}
        <div className="rounded-xl border bg-card shadow-sm">
          <div className="border-b p-4">
            <h3 className="flex items-center gap-2 font-semibold"><MapPin className="h-4 w-4 text-primary" /> รายการหมุด ({filteredStops.length})</h3>
            <p className="mt-1 text-xs text-muted-foreground">คลิกสถานที่เพื่อซูมดูบนแผนที่</p>
          </div>
          <div className="max-h-[560px] space-y-2 overflow-y-auto p-3">
            {filteredStops.map((stop, idx) => {
              const isSelected = selectedStop?.order_number === stop.order_number
              return (
                <div
                  key={idx}
                  className={cn("cursor-pointer rounded-lg border p-3 transition-colors hover:bg-accent", isSelected && "border-primary bg-primary/5")}
                  onClick={() => setSelectedStop({ ...stop, lat: stop.lat || (depotLat + idx * 0.005), lng: stop.lng || (depotLng + idx * 0.005) })}
                >
                  <div className="flex items-center justify-between">
                    <span className="rounded px-2 py-0.5 text-xs font-semibold text-white" style={{ backgroundColor: stop.color }}>
                      รถคันที่ {stop.vehicle_id} · จุดที่ {stop.stop_number}
                    </span>
                    <span className="text-xs text-muted-foreground">{stop.weight} kg</span>
                  </div>
                  <h4 className="mt-1.5 font-medium">{stop.customer}</h4>
                  <p className="truncate text-xs text-muted-foreground">{stop.address}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); setSelectedStop({ ...stop, lat: stop.lat || (depotLat + idx * 0.005), lng: stop.lng || (depotLng + idx * 0.005) }) }}
                      className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted"
                    >
                      <Target className="h-3.5 w-3.5" /> ซูม
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleOpenGoogleMapsReal(stop.lat, stop.lng, stop.address) }}
                      className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted"
                    >
                      <Navigation className="h-3.5 w-3.5" /> Maps
                    </button>
                  </div>

                  {isSelected && (
                    <div className="mt-3 space-y-2 border-t pt-3" onClick={(e) => e.stopPropagation()}>
                      <p className="flex items-center gap-1.5 text-xs font-medium"><Search className="h-3.5 w-3.5" /> ค้นหาสถานที่จริงเพื่อปักหมุด:</p>
                      <input
                        type="text"
                        placeholder="ชื่อสถานที่, ร้านค้า, ถนน..."
                        value={placeSearchQuery}
                        onChange={(e) => {
                          const val = e.target.value
                          setPlaceSearchQuery(val)
                          if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
                          searchDebounceRef.current = setTimeout(() => handleSearchPlaceOnline(val), 300)
                        }}
                        className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      />
                      {isSearchingPlace && <p className="text-xs text-muted-foreground">กำลังค้นหาสถานที่...</p>}
                      {placeSearchResults.length > 0 && (
                        <div className="space-y-1">
                          {placeSearchResults.map((place, pIdx) => (
                            <div
                              key={pIdx}
                              onClick={() => handleApplySearchedLocation(place, stop)}
                              className="flex cursor-pointer items-center gap-2 rounded-md border p-2 text-xs hover:bg-muted"
                            >
                              <MapPin className="h-4 w-4 shrink-0 text-primary" />
                              <span className="flex-1 truncate">{place.display_name}</span>
                              <span className="rounded bg-primary px-2 py-0.5 text-white">ปักหมุด</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MapView
