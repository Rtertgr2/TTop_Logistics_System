import { useState, useEffect } from 'react'
import axios from 'axios'

function RouteResult({ routes, deferredInfo, onSendLine, onSendDriverLine }) {
  const vehicleColors = ['blue', 'green', 'orange', 'purple']
  const [downloadingExcel, setDownloadingExcel] = useState(false)
  const [sendingLine, setSendingLine] = useState(false)
  const [sendingDriverLine, setSendingDriverLine] = useState(false)
  const [lineUserIdMap, setLineUserIdMap] = useState({})

  useEffect(() => {
    const fetchVehicles = async () => {
      try {
        const res = await fetch('/api/v1/vehicles')
        if (res.ok) {
          const data = await res.json()
          const map = {}
          ;(data.vehicles || []).forEach(v => {
            if (v.id != null && v.line_user_id) map[v.id] = v.line_user_id
          })
          setLineUserIdMap(map)
        }
      } catch (e) {
        console.warn('โหลดข้อมูลรถเพื่อส่ง LINE ไม่สำเร็จ', e)
      }
    }
    fetchVehicles()
  }, [])

  const handleSendDriverLine = async (route) => {
    const driverLineUserId = lineUserIdMap[route.vehicle_id]
    if (!driverLineUserId) {
      alert('ยังไม่ได้กรอก LINE User ID ของคนขับคันนี้\nไปที่เมนู "จัดการรถ" แล้วกรอก LINE User ID ให้รถคันนี้ก่อน')
      return
    }
    if (!onSendDriverLine) return
    setSendingDriverLine(true)
    try {
      await onSendDriverLine(route, driverLineUserId)
      alert(`ส่งลิงก์แมพเข้า LINE ให้คนขับคัน "${route.name || route.vehicle_id}" เรียบร้อยแล้ว`)
    } catch (err) {
      alert(err.message || 'ส่ง LINE ให้คนขับไม่สำเร็จ')
    } finally {
      setSendingDriverLine(false)
    }
  }

  const getMapsUrl = (route) => {
    if (route.google_maps_link) return route.google_maps_link
    const addresses = route.stops.map(s => encodeURIComponent(s.address)).join('/')
    return `https://www.google.com/maps/dir/${addresses}`
  }

  const handleOpenMaps = (route) => {
    window.open(getMapsUrl(route), '_blank')
  }

  const handleCopyMapsUrl = (route) => {
    const url = getMapsUrl(route)
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(() => {
        alert(`คัดลอกลิงก์ Google Maps ของ ${route.name || 'รถคันนี้'} เรียบร้อยแล้ว!`)
      }).catch(() => fallbackCopyTextToClipboard(url, route.name))
    } else {
      fallbackCopyTextToClipboard(url, route.name)
    }
  }

  const fallbackCopyTextToClipboard = (text, routeName) => {
    const textArea = document.createElement('textarea')
    textArea.value = text
    document.body.appendChild(textArea)
    textArea.select()
    try {
      document.execCommand('copy')
      alert(`คัดลอกลิงก์ Google Maps ของ ${routeName || 'รถคันนี้'} เรียบร้อยแล้ว!`)
    } catch (err) {
      console.error('Fallback copy failed', err)
      alert('ไม่สามารถคัดลอกลิงก์อัตโนมัติได้')
    }
    document.body.removeChild(textArea)
  }

  const handleDownloadExcel = async () => {
    setDownloadingExcel(true)
    try {
      const response = await axios.post('/api/v1/export-manifest-excel', { routes }, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `driver_manifest_all_${new Date().toISOString().slice(0, 10)}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error('Download excel failed:', err)
      alert('ไม่สามารถดาวน์โหลดไฟล์ Excel ได้')
    } finally {
      setDownloadingExcel(false)
    }
  }

  const getVehicleCapacityText = (route) => {
    if (route.capacity) {
      return `${(route.capacity / 1000).toFixed(2)} ตัน (${route.capacity} kg)`
    }
    const capMap = {
      1: "3.75 ตัน (3,750 kg)",
      2: "1.8 - 1.9 ตัน (1,900 kg)",
      3: "1.95 - 2.24 ตัน (2,240 kg)",
      4: "3.75 ตัน (3,750 kg)"
    }
    return capMap[route.vehicle_id] || "ไม่ระบุความจุ"
  }

  return (
    <div className="route-result">
      <div className="route-header">
        <div>
          <h2>ผลลัพธ์การจัดเส้นทางตามโซนและน้ำหนักบรรทุก</h2>
          <p>จัดสรรออเดอร์ลงรถตามทิศทางภูมิศาสตร์และขีดจำกัดน้ำหนัก</p>
        </div>
        {routes.length > 0 && (
          <div className="action-buttons-group">
            <button
              className="btn-excel-export"
              onClick={handleDownloadExcel}
              disabled={downloadingExcel}
            >
              {downloadingExcel ? 'กำลังสร้าง Excel...' : 'ดาวน์โหลดใบส่งงานคนขับรถ (Excel)'}
            </button>
            {onSendLine && (
              <button
                className="btn-secondary"
                onClick={async () => {
                  setSendingLine(true)
                  try {
                    await onSendLine(routes)
                  } finally {
                    setSendingLine(false)
                  }
                }}
                disabled={sendingLine}
                style={{ background: '#06b6d4', color: 'white', borderColor: '#06b6d4' }}
              >
                {sendingLine ? 'กำลังส่ง...' : '📤 ส่ง LINE Notification'}
              </button>
            )}
          </div>
        )}
      </div>

      {deferredInfo && deferredInfo.count > 0 && (
        <div className="deferred-warning" style={{
          background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
          border: '2px solid #f59e0b',
          borderRadius: '12px',
          padding: '20px 24px',
          marginBottom: '24px',
          boxShadow: '0 4px 12px rgba(245, 158, 11, 0.15)'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
            <span style={{ fontSize: '28px', lineHeight: 1 }}>⚠️</span>
            <div style={{ flex: 1 }}>
              <h3 style={{ margin: '0 0 8px 0', color: '#92400e', fontSize: '18px' }}>
                ออเดอร์เกินความจุรถ — เลื่อนส่งวันถัดไป
              </h3>
              <p style={{ margin: '0 0 12px 0', color: '#78350f', fontSize: '14px' }}>
                ออเดอร์ <strong>{deferredInfo.count} รายการ</strong> น้ำหนักรวม <strong>{deferredInfo.weight.toLocaleString()} kg</strong> จะถูกส่งในวันถัดไป เนื่องจากน้ำหนักรวมเกินความจุรถที่มี
              </p>
              <details style={{ marginTop: '8px' }}>
                <summary style={{ cursor: 'pointer', color: '#92400e', fontWeight: 600, fontSize: '13px' }}>
                  ดูรายการออเดอร์ที่เลื่อนส่ง ({deferredInfo.count} รายการ)
                </summary>
                <div style={{ marginTop: '10px', maxHeight: '200px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ background: '#fde68a' }}>
                        <th style={{ padding: '6px 10px', textAlign: 'left', borderBottom: '1px solid #f59e0b' }}>ลำดับ</th>
                        <th style={{ padding: '6px 10px', textAlign: 'left', borderBottom: '1px solid #f59e0b' }}>เลขที่ SO</th>
                        <th style={{ padding: '6px 10px', textAlign: 'left', borderBottom: '1px solid #f59e0b' }}>ลูกค้า</th>
                        <th style={{ padding: '6px 10px', textAlign: 'right', borderBottom: '1px solid #f59e0b' }}>น้ำหนัก (kg)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deferredInfo.orders.map((o, i) => (
                        <tr key={i} style={{ background: i % 2 === 0 ? '#fffbeb' : '#fef3c7' }}>
                          <td style={{ padding: '5px 10px', borderBottom: '1px solid #fde68a' }}>{i + 1}</td>
                          <td style={{ padding: '5px 10px', borderBottom: '1px solid #fde68a' }}>{o.order_number || '-'}</td>
                          <td style={{ padding: '5px 10px', borderBottom: '1px solid #fde68a' }}>{o.customer || '-'}</td>
                          <td style={{ padding: '5px 10px', textAlign: 'right', borderBottom: '1px solid #fde68a' }}>{o.weight || 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          </div>
        </div>
      )}

      <div className="routes-grid">
        {routes.map((route, index) => {
          const capText = getVehicleCapacityText(route)
          const maxCapKg = route.capacity || (route.vehicle_id === 2 ? 1900 : route.vehicle_id === 3 ? 2240 : 3750)
          const weightPercent = maxCapKg > 0 ? Math.min(100, Math.round((route.total_weight / maxCapKg) * 100)) : 0

          return (
            <div key={route.vehicle_id} className={`route-card ${vehicleColors[index % 4]}`}>
              <div className="route-card-header">
                <div className="vehicle-info">
                  <h3>{route.name || `รถคันที่ ${route.vehicle_id}`}</h3>
                  <div className="driver-details">
                    <span>คนขับ: {route.driver || 'ไม่ระบุ'}</span>
                    <span>ทะเบียน: {route.plate || 'ไม่ระบุ'}</span>
                    <span>น้ำหนักสูงสุด: {capText}</span>
                  </div>
                </div>
                <div className="route-summary-badge">
                  <div className="stops-count">{route.stops.length} จุดส่ง</div>
                  <div className="total-weight">{route.total_weight} kg</div>
                </div>
              </div>

              <div className="capacity-bar-container">
                <div className="capacity-bar-label">
                  <span>น้ำหนักบรรทุก: {route.total_weight} / {maxCapKg} kg</span>
                  <span className={weightPercent > 90 ? 'danger-text' : ''}>{weightPercent}%</span>
                </div>
                <div className="capacity-bar">
                  <div
                    className={`capacity-bar-fill ${weightPercent > 90 ? 'overload' : ''}`}
                    style={{ width: `${weightPercent}%` }}
                  ></div>
                </div>
              </div>

              <div className="stops-list">
                <h4>ลำดับการจัดส่ง ({route.stops.length} จุด)</h4>
                <ol>
                  {route.stops.map((stop, sIndex) => (
                    <li key={sIndex} className="stop-item">
                      <span className="stop-number">{sIndex + 1}</span>
                      <div className="stop-details">
                        <div className="stop-customer">
                          {stop.customer}
                          {stop.order_number && <span className="order-number-tag"> ({stop.order_number})</span>}
                        </div>
                        <div className="stop-address">{stop.address}</div>
                        <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap', alignItems: 'center' }}>
                          {stop.zone && <span className="stop-zone-badge">{stop.zone}</span>}
                          <span style={{ fontSize: '12px', color: '#475569', fontWeight: 'bold' }}>
                            {stop.is_verified ? '100%' : `${Math.round(stop.confidence_score || 50)}%`}
                          </span>
                        </div>
                      </div>
                      <span className="stop-weight">{stop.weight} kg</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="route-card-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  className="btn-maps"
                  onClick={() => handleOpenMaps(route)}
                  style={{ flex: 1, minWidth: '140px' }}
                >
                  ดูใน Google Maps
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => handleCopyMapsUrl(route)}
                  title="คัดลอกลิงก์ Google Maps นำทางของรถคันนี้"
                  style={{ background: '#f8fafc', borderColor: '#cbd5e1', color: '#1e293b', fontWeight: 600 }}
                >
                  คัดลอกลิงก์แมพ
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => handleSendDriverLine(route)}
                  disabled={sendingDriverLine}
                  title={lineUserIdMap[route.vehicle_id] ? "ส่งลิงก์แมพเข้า LINE ให้คนขับคันนี้" : "กรอก LINE User ID ที่หน้า จัดการรถ ก่อน"}
                  style={{ background: '#06b6d4', color: 'white', borderColor: '#06b6d4' }}
                >
                  {sendingDriverLine ? 'กำลังส่ง...' : 'ส่ง LINE ให้คนขับ'}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default RouteResult
