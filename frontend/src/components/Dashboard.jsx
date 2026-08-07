import { useState, useEffect } from 'react'
import axios from 'axios'
import NotificationPanel from './NotificationPanel'

const STATUS_COLORS = {
  PENDING: '#6b7280',
  IN_TRANSIT: '#3b82f6',
  ARRIVED: '#f59e0b',
  DELIVERED: '#10b981',
  FAILED: '#ef4444',
  PARTIAL: '#8b5cf6',
  RESCHEDULED: '#06b6d4',
}

function Dashboard({ orders, routes, onNavigate, onClearData }) {
  const [sysStatus, setSysStatus] = useState(null)
  const [deliveryDashboard, setDeliveryDashboard] = useState(null)

  useEffect(() => {
    fetchSystemStatus()
    fetchDeliveryDashboard()
  }, [])

  const fetchSystemStatus = async () => {
    try {
      const res = await axios.get('/api/v1/system-status')
      setSysStatus(res.data)
    } catch (err) {
      // silent
    }
  }

  const fetchDeliveryDashboard = async () => {
    try {
      const res = await axios.get('/api/v1/delivery/dashboard')
      setDeliveryDashboard(res.data)
    } catch (err) {
      // silent
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
        <div className="hero-badges" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <NotificationPanel />
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
            <h3>{totalVehiclesUsed} <span className="stat-unit">คัน</span></h3>
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
              <p>ยังไม่ได้จัดเส้นทาง — คลิก "คำนวณเส้นทาง" เพื่อจัดสรรคิวรถ</p>
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

          <div className="quick-card" onClick={() => onNavigate('driver')}>
            <div className="quick-icon-bg blue">📱</div>
            <div className="quick-info">
              <h4>Driver Mobile</h4>
              <p>อัปเดตสถานะจัดส่งแบบ real-time สำหรับคนขับรถ</p>
            </div>
          </div>

          <div className="quick-card" onClick={() => onNavigate('load-balance')}>
            <div className="quick-icon-bg purple">⚖️</div>
            <div className="quick-info">
              <h4>Load Balancing</h4>
              <p>วิเคราะห์และกระจายภาระระหว่างรถขนส่งอัตโนมัติ</p>
            </div>
          </div>

          {onClearData && (
            <div className="quick-card danger" onClick={onClearData} style={{ cursor: 'pointer', border: '1px solid #fecdd3' }}>
              <div className="quick-icon-bg rose" style={{ background: '#ffe4e6', color: '#e11d48' }}>🗑️</div>
              <div className="quick-info">
                <h4 style={{ color: '#e11d48' }}>รีเซ็ตข้อมูลระบบทั้งหมด</h4>
                <p>ล้างข้อมูลออเดอร์ แผนจัดส่ง และ fleet กลับเป็นค่าเริ่มต้น</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Delivery Status Section */}
      {deliveryDashboard?.has_plan && deliveryDashboard.summary && (
        <div className="dash-card" style={{ margin: '20px' }}>
          <div className="card-header-flex">
            <h3>📦 สถานะการจัดส่งวันนี้</h3>
            <button className="text-btn" onClick={() => onNavigate('driver')}>
              Driver Mobile 📱
            </button>
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
            {Object.entries({
              'delivered': { label: 'ส่งสำเร็จ', icon: '✅', color: STATUS_COLORS.DELIVERED },
              'in_transit': { label: 'กำลังขนส่ง', icon: '🚚', color: STATUS_COLORS.IN_TRANSIT },
              'arrived': { label: 'ถึงจุดส่ง', icon: '📍', color: STATUS_COLORS.ARRIVED },
              'pending': { label: 'รอจัดส่ง', icon: '⏳', color: STATUS_COLORS.PENDING },
              'failed': { label: 'ไม่สำเร็จ', icon: '❌', color: STATUS_COLORS.FAILED },
              'partial': { label: 'ส่งบางส่วน', icon: '⚠️', color: STATUS_COLORS.PARTIAL },
            }).map(([key, cfg]) => (
              <div key={key} style={{
                flex: '1 1 120px',
                background: `${cfg.color}10`,
                border: `1px solid ${cfg.color}30`,
                borderRadius: '12px',
                padding: '12px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: '24px', fontWeight: 800, color: cfg.color }}>
                  {deliveryDashboard.summary[key] || 0}
                </div>
                <div style={{ fontSize: '12px', color: cfg.color, fontWeight: 600 }}>
                  {cfg.icon} {cfg.label}
                </div>
              </div>
            ))}
          </div>
          <div style={{ background: '#e2e8f0', borderRadius: '6px', height: '10px', overflow: 'hidden' }}>
            <div style={{
              width: `${deliveryDashboard.summary.completion_pct || 0}%`,
              background: 'linear-gradient(90deg, #10b981, #34d399)',
              height: '100%',
              borderRadius: '6px',
              transition: 'width 0.5s ease',
            }} />
          </div>
          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '6px', fontWeight: 600 }}>
            {deliveryDashboard.summary.completion_pct || 0}% เสร็จสิ้น
          </p>
        </div>
      )}
    </div>
  )
}

function getZoneColor(index) {
  const colors = ['#6366f1', '#10b981', '#f59e0b', '#8b5cf6', '#3b82f6']
  return colors[index % colors.length]
}

export default Dashboard
