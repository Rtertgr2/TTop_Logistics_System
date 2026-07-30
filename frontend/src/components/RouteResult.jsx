import { useState } from 'react'
import axios from 'axios'

function RouteResult({ routes, onSendEmail }) {
  const vehicleColors = ['blue', 'green', 'orange', 'purple']
  const [emailModal, setEmailModal] = useState(null) // vehicle_id or 'all'
  const [emailAddress, setEmailAddress] = useState('')
  const [sending, setSending] = useState(false)
  const [sendResult, setSendResult] = useState(null)
  const [downloadingExcel, setDownloadingExcel] = useState(false)

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
        alert(`📋 คัดลอกลิงก์ Google Maps ของ ${route.name || 'รถคันนี้'} เรียบร้อยแล้ว!`)
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
      alert(`📋 คัดลอกลิงก์ Google Maps ของ ${routeName || 'รถคันนี้'} เรียบร้อยแล้ว!`)
    } catch (err) {
      console.error('Fallback copy failed', err)
      alert('ไม่สามารถคัดลอกลิงก์อัตโนมัติได้')
    }
    document.body.removeChild(textArea)
  }

  const handleDownloadExcel = async () => {
    setDownloadingExcel(true)
    try {
      const response = await axios.post('/api/export-manifest-excel', { routes }, { responseType: 'blob' })
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

  const handleSendEmail = async () => {
    if (!emailAddress.trim()) return

    setSending(true)
    setSendResult(null)

    try {
      const routesToSend = emailModal === 'all'
        ? routes
        : routes.filter(r => r.vehicle_id === emailModal)

      const result = await onSendEmail(routesToSend, emailAddress)
      setSendResult({ type: 'success', message: result.message || 'ส่ง email สำเร็จ!' })
    } catch (err) {
      setSendResult({ type: 'error', message: err.message || 'ส่ง email ไม่สำเร็จ' })
    } finally {
      setSending(false)
    }
  }

  const closeModal = () => {
    setEmailModal(null)
    setEmailAddress('')
    setSendResult(null)
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
          <h2>🗺️ ผลลัพธ์การจัดเส้นทางตามโซนและน้ำหนักบรรทุก</h2>
          <p>จัดสรรออเดอร์ลงรถตามทิศทางภูมิศาสตร์และขีดจำกัดน้ำหนัก</p>
        </div>
        {routes.length > 0 && (
          <div className="action-buttons-group">
            <button
              className="btn-excel-export"
              onClick={handleDownloadExcel}
              disabled={downloadingExcel}
            >
              {downloadingExcel ? '⏳ กำลังสร้าง Excel...' : '📊 ดาวน์โหลดใบส่งงานคนขับรถ (Excel)'}
            </button>
            <button className="btn-primary" onClick={() => setEmailModal('all')}>
              📧 ส่ง Email ทั้งหมด
            </button>
          </div>
        )}
      </div>

      <div className="routes-grid">
        {routes.map((route, index) => {
          const capText = getVehicleCapacityText(route)
          const maxCapKg = route.capacity || (route.vehicle_id === 2 ? 1900 : route.vehicle_id === 3 ? 2240 : 3750)
          const weightPercent = Math.min(100, Math.round((route.total_weight / maxCapKg) * 100))

          return (
            <div key={route.vehicle_id} className={`route-card ${vehicleColors[index % 4]}`}>
              <div className="route-card-header">
                <div className="vehicle-info">
                  <h3>🚛 {route.name || `รถคันที่ ${route.vehicle_id}`}</h3>
                  <div className="driver-details">
                    <span>👤 คนขับ: {route.driver || 'ไม่ระบุ'}</span>
                    <span>🚗 ทะเบียน: {route.plate || 'ไม่ระบุ'}</span>
                    <span>📦 น้ำหนักสูงสุด: {capText}</span>
                  </div>
                </div>
                <div className="route-summary-badge">
                  <div className="stops-count">📍 {route.stops.length} จุดส่ง</div>
                  <div className="total-weight">⚖️ {route.total_weight} kg</div>
                </div>
              </div>

              {/* Progress bar สำหรับน้ำหนักบรรทุก */}
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

              {/* รายการจุดจอด */}
              <div className="stops-list">
                <h4>📋 ลำดับการจัดส่ง ({route.stops.length} จุด)</h4>
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
                          {stop.zone && <span className="stop-zone-badge">📍 {stop.zone}</span>}
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

              {/* ปุ่มการทำงาน */}
              <div className="route-card-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  className="btn-maps"
                  onClick={() => handleOpenMaps(route)}
                  style={{ flex: 1, minWidth: '140px' }}
                >
                  🗺️ ดูใน Google Maps
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => handleCopyMapsUrl(route)}
                  title="คัดลอกลิงก์ Google Maps นำทางของรถคันนี้"
                  style={{ background: '#f8fafc', borderColor: '#cbd5e1', color: '#1e293b', fontWeight: 600 }}
                >
                  🔗 คัดลอกลิงก์เเมพ
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => setEmailModal(route.vehicle_id)}
                >
                  📧 ส่ง Email
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Email Modal */}
      {emailModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>📧 ส่งแผนการจัดส่งทาง Email</h3>
            <p>
              {emailModal === 'all'
                ? 'ส่งแผนการจัดส่งของรถทุกคันไปยัง email'
                : `ส่งแผนการจัดส่งของรถคันที่ ${emailModal} ไปยัง email`}
            </p>

            <div className="form-group">
              <label>อีเมลผู้รับ:</label>
              <input
                type="email"
                placeholder="driver@company.com"
                value={emailAddress}
                onChange={(e) => setEmailAddress(e.target.value)}
              />
            </div>

            {sendResult && (
              <div className={`send-result ${sendResult.type}`}>
                {sendResult.message}
              </div>
            )}

            <div className="modal-actions">
              <button
                className="btn-cancel"
                onClick={closeModal}
                disabled={sending}
              >
                ยกเลิก
              </button>
              <button
                className="btn-primary"
                onClick={handleSendEmail}
                disabled={sending || !emailAddress.trim()}
              >
                {sending ? 'กำลังส่ง...' : 'ส่ง Email'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RouteResult
