import { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const vehicleColors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4']

// Leaflet Map Controller to fly to selected location
function MapFlyToController({ targetLocation }) {
  const map = useMap()
  useEffect(() => {
    if (targetLocation && targetLocation.lat && targetLocation.lng) {
      map.flyTo([targetLocation.lat, targetLocation.lng], 16, {
        animate: true,
        duration: 1.5
      })
    }
  }, [targetLocation, map])
  return null
}

function createCustomMarkerIcon(color, label, isSelected) {
  const scale = isSelected ? 'scale(1.3)' : 'scale(1)'
  const borderCol = isSelected ? '#fbbf24' : 'white'

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
          background: ${color};
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
          ">${label}</span>
        </div>
      </div>
    `,
    iconSize: [26, 32],
    iconAnchor: [13, 32],
    popupAnchor: [0, -30]
  })
}

function createDepotIcon() {
  return L.divIcon({
    className: 'custom-depot-marker',
    html: `
      <div style="
        cursor: pointer;
        display: flex;
        flex-direction: column;
        align-items: center;
      ">
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
          <span style="
            transform: rotate(45deg);
            font-size: 14px;
            line-height: 1;
          ">🏭</span>
        </div>
      </div>
    `,
    iconSize: [32, 38],
    iconAnchor: [16, 38],
    popupAnchor: [0, -36]
  })
}

function roundCoord(val) {
  return Math.round(val * 1000000) / 1000000
}

function MapView({ routes = [], orders = [], depotLat = 13.781882, depotLng = 100.425041 }) {
  const [mapType, setMapType] = useState('standard') // 'standard' or 'satellite'
  const [selectedStop, setSelectedStop] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Local state to keep UI updated dynamically when markers are edited
  const [localRoutes, setLocalRoutes] = useState(routes)
  const [localOrders, setLocalOrders] = useState(orders)

  useEffect(() => {
    setLocalRoutes(routes)
  }, [routes])

  useEffect(() => {
    setLocalOrders(orders)
  }, [orders])

  // Live Place Search States for Pinning
  const [placeSearchQuery, setPlaceSearchQuery] = useState('')
  const [placeSearchResults, setPlaceSearchResults] = useState([])
  const [isSearchingPlace, setIsSearchingPlace] = useState(false)

  // Update stop coordinates dynamically in React state
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
            return {
              ...s,
              lat: newLat,
              lng: newLng,
              raw_lat: s.raw_lat || newLat,
              raw_lng: s.raw_lng || newLng,
              verified_lat: newLat,
              verified_lng: newLng,
              address: newAddress || s.address,
              verified_address: newAddress || s.verified_address,
              confidence_score: 100.0,
              is_verified: true
            }
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
          return {
            ...o,
            lat: newLat,
            lng: newLng,
            raw_lat: o.raw_lat || newLat,
            raw_lng: o.raw_lng || newLng,
            verified_lat: newLat,
            verified_lng: newLng,
            address: newAddress || o.address,
            confidence_score: 100.0,
            is_verified: true
          }
        }
        return o
      })
    })
  }

  const handleSearchPlaceOnline = async (queryStr) => {
    if (!queryStr || queryStr.trim().length < 2) {
      setPlaceSearchResults([])
      return
    }
    setIsSearchingPlace(true)
    try {
      const res = await fetch(`/api/search-place?address=${encodeURIComponent(queryStr)}`)
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
        await fetch(`/api/orders/${stopItem.id}/verify-location`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lat: latToSave,
            lng: lngToSave,
            verified_by: 'user_frontend_map'
          })
        })
      }
      setSelectedStop({ ...stopItem, lat: latToSave, lng: lngToSave, is_verified: true, confidence_score: 100.0 })
      alert(`💾 บันทึกสถานที่จัดส่งของ "${stopItem.customer}" (Lat: ${latToSave}, Lng: ${lngToSave}) ลงฐานข้อมูลเรียบร้อยแล้ว!`)
    } catch (err) {
      console.error('Save location to DB error:', err)
      alert('เกิดข้อผิดพลาดในการบันทึกลงฐานข้อมูล')
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

  // Tile URLs
  const tileUrls = {
    standard: {
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    },
    satellite: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    }
  }

  // Combine items to render from local state
  const allStops = []
  
  if (localRoutes && localRoutes.length > 0) {
    localRoutes.forEach((route, rIdx) => {
      route.stops.forEach((stop, sIdx) => {
        allStops.push({
          ...stop,
          vehicle_id: route.vehicle_id,
          vehicle_name: route.name,
          driver: route.driver,
          plate: route.plate,
          color: vehicleColors[rIdx % vehicleColors.length],
          stop_number: sIdx + 1,
          label: `${route.vehicle_id}.${sIdx + 1}`
        })
      })
    })
  } else if (localOrders && localOrders.length > 0) {
    localOrders.forEach((order, idx) => {
      allStops.push({
        ...order,
        vehicle_id: 1,
        color: '#6366f1',
        stop_number: idx + 1,
        label: `${idx + 1}`
      })
    })
  }

  // Compute map center
  const validPositions = allStops
    .filter(s => s.lat && s.lng)
    .map(s => [s.lat, s.lng])

  if (validPositions.length === 0) {
    validPositions.push([depotLat, depotLng])
  }

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
    if (lat && lng) {
      window.open(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`, '_blank')
    } else {
      window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`, '_blank')
    }
  }

  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className={`map-view-wrapper ${isExpanded ? 'map-expanded-mode' : ''}`}>
      {/* Map Control Bar */}
      <div className="map-control-bar">
        <div className="map-type-selector">
          <button
            className={`btn-map-type ${mapType === 'standard' ? 'active' : ''}`}
            onClick={() => setMapType('standard')}
          >
            🗺️ แผนที่ถนน (Standard)
          </button>
          <button
            className={`btn-map-type ${mapType === 'satellite' ? 'active' : ''}`}
            onClick={() => setMapType('satellite')}
          >
            🛰️ ภาพถ่ายดาวเทียม (Satellite)
          </button>
          <button
            className={`btn-map-type ${isExpanded ? 'active' : ''}`}
            style={{ background: isExpanded ? '#10b981' : undefined, color: isExpanded ? 'white' : undefined }}
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? '🔍 ย่อแผนที่กลับเท่าเดิม' : '🖥️ ขยายแผนที่ขนาดใหญ่พิเศษ (Full View)'}
          </button>
        </div>

        <div className="map-search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="ค้นหาชื่อลูกค้า, ที่อยู่ หรือ SO..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className={`map-container-grid ${isExpanded ? 'expanded-grid' : ''}`}>
        {/* Leaflet Real Interactive Map */}
        <div className="map-box">
          <MapContainer
            center={[centerLat, centerLng]}
            zoom={11}
            style={{ height: isExpanded ? '850px' : '720px', width: '100%', borderRadius: '14px' }}
          >
            <TileLayer
              url={tileUrls[mapType].url}
              attribution={tileUrls[mapType].attribution}
            />

            <MapFlyToController targetLocation={selectedStop} />

            {/* Depot Marker */}
            <Marker position={[depotLat, depotLng]} icon={createDepotIcon()}>
              <Popup>
                <div className="popup-card">
                  <h4>🏭 คลังสินค้าหลัก (Depot)</h4>
                  <p><strong>บริษัท ทรีท็อปเคมิคัลแอนด์ฟู้ดส์ คอร์ปอเรชั่น จำกัด</strong></p>
                  <p>20/2 ถนนบรมราชชนนี แขวงฉิมพลี เขตตลิ่งชัน กรุงเทพมหานคร 10170</p>
                  <div className="popup-coords">📍 สถานที่จัดส่งจริง: 20/2 ถ.บรมราชชนนี ตลิ่งชัน กรุงเทพฯ</div>
                </div>
              </Popup>
            </Marker>

            {/* Stop Markers */}
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
                        const res = await fetch(`/api/reverse-geocode?lat=${newLat}&lng=${newLng}`)
                        const data = await res.json()
                        if (data.formatted_address) {
                          newAddress = data.formatted_address
                        }
                        if (stop.id) {
                          await fetch(`/api/orders/${stop.id}/verify-location`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ lat: newLat, lng: newLng, verified_by: 'user_dragged_pin' })
                          })
                        }
                      } catch (err) {
                        console.warn('Reverse geocode error:', err)
                      }

                      updateStopLocationInState(stop, newLat, newLng, newAddress)
                      setSelectedStop({ ...stop, lat: newLat, lng: newLng, address: newAddress, verified_address: newAddress, is_verified: true, confidence_score: 100.0 })
                    }
                  }}
                >
                  <Popup>
                    <div className="popup-card">
                      <div className="popup-badge-row" style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '8px' }}>
                        <div className="popup-badge" style={{ background: stop.color }}>
                          🚛 รถคันที่ {stop.vehicle_id} (จุดส่งที่ {stop.stop_number})
                        </div>
                        <span style={{ fontSize: '12px', color: '#475569', fontWeight: 'bold' }}>
                          {stop.is_verified ? '100%' : `${Math.round(confScore)}%`}
                        </span>
                      </div>

                      <h4>📦 {stop.customer}</h4>
                      {stop.order_number && <p className="so-tag">SO: {stop.order_number}</p>}
                      <p className="pop-address">📍 {stop.verified_address || stop.address}</p>
                      <div className="pop-details">
                        <span>⚖️ น้ำหนัก: {stop.weight} kg</span>
                        {stop.zone && <span>🗺️ โซน: {stop.zone}</span>}
                      </div>
                      <div className="pop-coords">📍 พิกัด: {sLat.toFixed(6)}, {sLng.toFixed(6)}</div>
                      <div className="drag-hint" style={{ color: '#10b981', fontWeight: '600' }}>💡 สามารถลากหมุดไปวาง ณ ตำแหน่งจริงเพื่อยืนยันพิกัดได้ทันที</div>

                      <button
                        className="btn-check-gmaps"
                        onClick={() => handleOpenGoogleMapsReal(sLat, sLng, stop.address)}
                      >
                        🗺️ นำทางไปยังสถานที่จริง (Google Maps) ↗
                      </button>

                      <button
                        style={{
                          marginTop: '6px',
                          width: '100%',
                          padding: '6px 12px',
                          background: '#10b981',
                          color: 'white',
                          border: 'none',
                          borderRadius: '8px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                        onClick={() => handleSaveLocationToDB(stop, sLat, sLng)}
                      >
                        💾 บันทึกตำแหน่งนี้ลงฐานข้อมูลถาวร (Save Location to DB)
                      </button>
                    </div>
                  </Popup>
                </Marker>
              )
            })}

            {/* Route Polylines */}
            {(localRoutes || []).map((route, rIdx) => {
              const color = vehicleColors[rIdx % vehicleColors.length]
              const pos = [[depotLat, depotLng]]
              route.stops.forEach(s => {
                if (s.lat && s.lng) pos.push([s.lat, s.lng])
              })
              if (pos.length > 1) {
                pos.push([depotLat, depotLng])
              }

              return (
                <Polyline
                  key={rIdx}
                  positions={pos}
                  pathOptions={{
                    color: color,
                    weight: 4,
                    opacity: 0.8,
                    dashArray: '8, 6'
                  }}
                />
              )
            })}
          </MapContainer>
        </div>

        {/* Side Inspector Panel */}
        <div className="stops-inspector-panel">
          <div className="inspector-header">
            <h3>📍 รายการหมุดสถานที่จัดส่ง ({filteredStops.length})</h3>
            <small>คลิกที่สถานที่เพื่อซูมดูหมุดบนแผนที่จริง</small>
          </div>

          <div className="inspector-stops-list">
            {filteredStops.map((stop, idx) => {
              const isSelected = selectedStop?.order_number === stop.order_number
              return (
                <div
                  key={idx}
                  className={`inspector-stop-card ${isSelected ? 'active' : ''}`}
                  onClick={() => setSelectedStop({ ...stop, lat: stop.lat || (depotLat + idx*0.005), lng: stop.lng || (depotLng + idx*0.005) })}
                >
                  <div className="stop-card-top">
                    <span className="stop-vehicle-tag" style={{ background: stop.color }}>
                      รถคันที่ {stop.vehicle_id} · จุดที่ {stop.stop_number}
                    </span>
                    <span className="stop-weight-tag">{stop.weight} kg</span>
                  </div>
                  <h4 className="stop-cust-name">{stop.customer}</h4>
                  <p className="stop-addr">{stop.address}</p>

                  <div className="stop-card-actions">
                    <button className="btn-zoom-pin">🎯 ซูมหมุดในแผนที่</button>
                    <button
                      className="btn-gmaps-link"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleOpenGoogleMapsReal(stop.lat, stop.lng, stop.address)
                      }}
                    >
                      🗺️ เปิด Google Maps
                    </button>
                  </div>

                  {/* Interactive Real Place Search Bar */}
                  {isSelected && (
                    <div className="place-pin-search-box" onClick={(e) => e.stopPropagation()}>
                      <div className="place-search-label">🔍 ค้นหาสถานที่จริงเพื่อปักหมุดออเดอร์นี้:</div>
                      <div className="place-search-input-wrapper">
                        <input
                          type="text"
                          className="input-place-search"
                          placeholder="พิมพ์ชื่อสถานที่, ร้านค้า, อาคาร หรือถนน..."
                          value={placeSearchQuery}
                          onChange={(e) => {
                            setPlaceSearchQuery(e.target.value)
                            handleSearchPlaceOnline(e.target.value)
                          }}
                        />
                      </div>

                      {isSearchingPlace && (
                        <div className="place-search-loading">⏳ กำลังค้นหาสถานที่จริงในประเทศไทย...</div>
                      )}

                      {placeSearchResults.length > 0 && (
                        <div className="place-results-dropdown">
                          {placeSearchResults.map((place, pIdx) => (
                            <div
                              key={pIdx}
                              className="place-result-item"
                              onClick={() => handleApplySearchedLocation(place, stop)}
                            >
                              <span className="place-icon">📍</span>
                              <div className="place-info-text">
                                <div className="place-title">{place.display_name}</div>
                                <div className="place-coords">📍 สถานที่จัดส่งจริงในไทย</div>
                              </div>
                              <span className="badge-select-place">ปักหมุดที่นี่</span>
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
