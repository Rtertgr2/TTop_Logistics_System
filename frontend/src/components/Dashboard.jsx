import { useState, useEffect } from 'react'
import axios from 'axios'

function Dashboard({ orders, routes, onNavigate }) {
  const [sysStatus, setSysStatus] = useState(null)

  useEffect(() => {
    fetchSystemStatus()
  }, [])

  const fetchSystemStatus = async () => {
    try {
      const res = await axios.get('/api/system-status')
      setSysStatus(res.data)
    } catch (err) {
      console.error('Failed to fetch system status:', err)
    }
  }

  const totalWeightKg = orders.reduce((sum, order) => sum + (parseFloat(order.weight) || 0), 0)
  const totalWeightTons = (totalWeightKg / 1000).toFixed(2)
  const totalVehiclesUsed = routes.length
  const totalStops = routes.reduce((sum, route) => sum + route.stops.length, 0)

  // Calculate zone distribution
  const zoneCounts = {}
  orders.forEach(order => {
    const zone = order.zone || 'ไม่ระบุ'
    zoneCounts[zone] = (zoneCounts[zone] || 0) + 1
  })

  const topZones = Object.entries(zoneCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  return (
    <div className="dashboard-wrapper">
      {/* Header Banner */}
      <div className="dashboard-hero">
        <div className="hero-text">
          <h2>🚚 ระบบบริหารจัดการขนส่งและวางแผนเส้นทาง (Route Optimization)</h2>
          <p>ประมวลผลอ่านไฟล์ PDF Express ERP แปลงพิกัดภูมิศาสตร์ และคำนวณลำดับจุดส่งอัตโนมัติ</p>
        </div>
        <div className="hero-badges">
          <span className={`status-pill ${sysStatus?.google_maps_api === 'active' ? 'green' : 'amber'}`}>
            {sysStatus?.google_maps_api === 'active' ? '🟢 Google Maps API: Active' : '🟡 Smart Geocoding: Active'}
          </span>
        </div>
      </div>

      {/* Metric Stat Cards */}
      <div className="stats-grid">
        <div className="stat-card blue-card" onClick={() => onNavigate('orders')}>
          <div className="stat-icon-wrapper blue-icon">📦</div>
          <div className="stat-info">
            <h3>{orders.length} <span className="stat-unit">รายการ</span></h3>
            <p>ออเดอร์ในระบบทั้งหมด</p>
          </div>
          <div className="stat-arrow">→</div>
        </div>

        <div className="stat-card green-card" onClick={() => onNavigate('routes')}>
          <div className="stat-icon-wrapper green-icon">🚚</div>
          <div className="stat-info">
            <h3>{totalVehiclesUsed} <span className="stat-unit">/ 4 คัน</span></h3>
            <p>รถที่ถูกจัดคิวส่งของ</p>
          </div>
          <div className="stat-arrow">→</div>
        </div>

        <div className="stat-card orange-card">
          <div className="stat-icon-wrapper orange-icon">📍</div>
          <div className="stat-info">
            <h3>{totalStops || orders.length} <span className="stat-unit">จุด</span></h3>
            <p>จุดจัดส่งสินค้าจำแนกตามโซน</p>
          </div>
        </div>

        <div className="stat-card purple-card">
          <div className="stat-icon-wrapper purple-icon">⚖️</div>
          <div className="stat-info">
            <h3>{totalWeightTons} <span className="stat-unit">ตัน</span></h3>
            <p>น้ำหนักรวมสินค้า ({totalWeightKg.toLocaleString()} kg)</p>
          </div>
        </div>
      </div>

      {/* Main Grid: Zone Distribution & Fleet Overview */}
      <div className="dashboard-main-grid">
        {/* Zone Distribution Card */}
        <div className="dash-card">
          <div className="card-header-flex">
            <h3>📍 การกระจายจุดส่งตามเขต/โซน (Top Zones)</h3>
            <span className="badge-pill">{Object.keys(zoneCounts).length} โซนทั้งหมด</span>
          </div>

          {topZones.length > 0 ? (
            <div className="zone-bars-list">
              {topZones.map(([zone, count], idx) => {
                const percent = Math.round((count / orders.length) * 100)
                return (
                  <div key={idx} className="zone-bar-item">
                    <div className="zone-bar-info">
                      <span className="zone-name">📍 {zone}</span>
                      <span className="zone-count">{count} ออเดอร์ ({percent}%)</span>
                    </div>
                    <div className="zone-progress-bg">
                      <div
                        className="zone-progress-fill"
                        style={{ width: `${percent}%`, backgroundColor: getZoneColor(idx) }}
                      ></div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="dash-empty-state">
              <span className="empty-icon">🗺️</span>
              <p>ยังไม่มีข้อมูลโซน — อัปโหลดไฟล์ PDF เพื่อเริ่มวิเคราะห์</p>
            </div>
          )}
        </div>

        {/* Fleet Dispatch Status Card */}
        <div className="dash-card">
          <div className="card-header-flex">
            <h3>🚚 สถานะการจัดคิวรถ (Fleet Utilization)</h3>
            <button className="text-btn" onClick={() => onNavigate('vehicles')}>
              จัดการรถ ⚙️
            </button>
          </div>

          {routes.length > 0 ? (
            <div className="fleet-dispatch-list">
              {routes.map((route, idx) => {
                const maxCap = route.capacity || 3750
                const loadPct = Math.round((route.total_weight / maxCap) * 100)
                return (
                  <div key={idx} className="dispatch-item">
                    <div className="dispatch-header">
                      <span className="dispatch-title">🚛 {route.name || `คันที่ ${route.vehicle_id}`}</span>
                      <span className="dispatch-capacity">{route.total_weight} / {maxCap} kg ({loadPct}%)</span>
                    </div>
                    <div className="dispatch-sub">
                      <span>👤 {route.driver || 'ไม่ระบุคนขับ'}</span>
                      <span>📍 {route.stops.length} จุดส่ง</span>
                    </div>
                    <div className="dispatch-progress-bg">
                      <div
                        className={`dispatch-progress-fill ${loadPct > 90 ? 'overload' : ''}`}
                        style={{ width: `${loadPct}%` }}
                      ></div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="dash-empty-state">
              <span className="empty-icon">🚛</span>
              <p>ยังไม่ได้จัดเส้นทาง — คลิก "คำนวณเส้นทาง" เพื่อจัดสรรคิวรถ 4 คัน</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick Action Panels */}
      <div className="quick-actions-panel">
        <h3>⚡ ทางลัดการใช้งาน (Quick Actions)</h3>
        <div className="quick-grid">
          <div className="quick-card" onClick={() => onNavigate('upload')}>
            <div className="quick-icon-bg indigo">📁</div>
            <div className="quick-info">
              <h4>อัปโหลดไฟล์ PDF ใบสั่งขาย</h4>
              <p>รองรับ Express PDF หลายไฟล์พร้อมกัน ระบบซ่อมคำไทยให้อัตโนมัติ</p>
            </div>
          </div>

          <div className="quick-card" onClick={() => onNavigate('orders')}>
            <div className="quick-icon-bg emerald">📋</div>
            <div className="quick-info">
              <h4>ตรวจสอบรายการสั่งซื้อ ({orders.length})</h4>
              <p>ดูรายการสินค้า น้ำหนัก และตำแหน่งที่ตั้งลูกค้าบนแผนที่</p>
            </div>
          </div>

          <div className="quick-card" onClick={() => onNavigate('vehicles')}>
            <div className="quick-icon-bg amber">⚙️</div>
            <div className="quick-info">
              <h4>จัดการ fleet รถขนส่ง</h4>
              <p>ปรับเปลี่ยนทะเบียนคนขับ ปรับความจุสูงสุด 1.8 - 3.75 ตัน</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function getZoneColor(index) {
  const colors = ['#6366f1', '#10b981', '#f59e0b', '#8b5cf6', '#3b82f6']
  return colors[index % colors.length]
}

export default Dashboard
