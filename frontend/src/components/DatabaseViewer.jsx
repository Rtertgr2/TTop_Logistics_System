import { useState, useEffect } from 'react'

function DatabaseViewer({ onClearData }) {
  const [activeTab, setActiveTab] = useState('orders') // 'orders', 'memories', 'history'
  const [orders, setOrders] = useState([])
  const [memories, setMemories] = useState([])
  const [history, setHistory] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [scoreFilter, setScoreFilter] = useState('ALL') // 'ALL', 'HIGH', 'MID', 'LOW'

  useEffect(() => {
    fetchData()
  }, [activeTab])

  const fetchData = async () => {
    setLoading(true)
    try {
      if (activeTab === 'orders') {
        const res = await fetch('/api/v1/orders-history?limit=200')
        if (res.ok) {
          const data = await res.json()
          setOrders(data.orders || [])
        }
      } else if (activeTab === 'memories') {
        const res = await fetch('/api/v1/customer-locations?limit=200')
        if (res.ok) {
          const data = await res.json()
          setMemories(data.locations || [])
        }
      } else if (activeTab === 'history') {
        const res = await fetch('/api/v1/history?limit=100')
        if (res.ok) {
          const data = await res.json()
          setHistory(data.history || [])
        }
      } else if (activeTab === 'vehicles') {
        const res = await fetch('/api/v1/vehicles')
        if (res.ok) {
          const data = await res.json()
          setVehicles(data.vehicles || [])
        }
      }
    } catch (err) {
      console.error('Fetch database data error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteMemory = async (id, custKey) => {
    if (!window.confirm(`คุณต้องการลบพิกัดความจำของ "${custKey}" ใช่หรือไม่?`)) return
    try {
      const res = await fetch(`/api/v1/customer-locations/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setMemories(memories.filter(m => m.id !== id))
        alert('🗑️ ลบพิกัดความจำเรียบร้อยแล้ว')
      }
    } catch (err) {
      console.error('Delete memory error:', err)
      alert('เกิดข้อผิดพลาดในการลบ')
    }
  }

  const handleToggleVehicleActive = async (vehicle) => {
    const updatedVehicles = vehicles.map(v =>
      v.id === vehicle.id ? { ...v, active: !v.active } : v
    )
    setVehicles(updatedVehicles)
    try {
      await fetch('/api/v1/vehicles', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedVehicles)
      })
    } catch (err) {
      console.error('Failed to toggle vehicle status:', err)
    }
  }

  const handleDeleteVehicleInDB = async (vehicleId, vehicleName) => {
    if (!window.confirm(`คุณต้องการลบ "${vehicleName}" ออกจากฐานข้อมูลใช่หรือไม่?`)) return
    try {
      const res = await fetch(`/api/v1/vehicles/${vehicleId}`, { method: 'DELETE' })
      if (res.ok) {
        const data = await res.json()
        setVehicles(data.vehicles || [])
        alert('🗑️ ลบรถออกจากฐานข้อมูลเรียบร้อยแล้ว')
      }
    } catch (err) {
      console.error('Failed to delete vehicle:', err)
    }
  }

  const filteredOrders = orders.filter(o => {
    const q = searchQuery.toLowerCase().trim()
    const matchesSearch = !q || (
      (o.customer || '').toLowerCase().includes(q) ||
      (o.address || '').toLowerCase().includes(q) ||
      (o.order_number || '').toLowerCase().includes(q) ||
      (o.zone || '').toLowerCase().includes(q)
    )

    const score = o.confidence_score !== undefined ? o.confidence_score : 50.0
    let matchesScore = true
    if (scoreFilter === 'HIGH') matchesScore = score >= 90 || o.is_verified
    else if (scoreFilter === 'MID') matchesScore = score >= 70 && score < 90 && !o.is_verified
    else if (scoreFilter === 'LOW') matchesScore = score < 70 && !o.is_verified

    return matchesSearch && matchesScore
  })

  const filteredMemories = memories.filter(m => {
    const q = searchQuery.toLowerCase().trim()
    return !q || (
      (m.customer_key || '').toLowerCase().includes(q) ||
      (m.formatted_address || '').toLowerCase().includes(q)
    )
  })

  return (
    <div className="page-container" style={{ padding: '24px' }}>
      {/* Header Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        color: 'white',
        padding: '24px 32px',
        borderRadius: '16px',
        marginBottom: '24px',
        boxShadow: '0 10px 25px rgba(15, 23, 42, 0.15)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '10px' }}>
            🗄️ คลังจัดการข้อมูล ฐานข้อมูล PostgreSQL (Database Viewer)
          </h2>
          <p style={{ margin: '6px 0 0 0', opacity: 0.8, fontSize: '14px' }}>
            เรียกดู ค้นหา ตรวจสอบ และบริหารจัดการข้อมูลออเดอร์ พิกัดจดจำถาวร และประวัติการจัดคิวรถ
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={fetchData}
            style={{
              padding: '10px 18px',
              background: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '10px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            🔄 รีเฟรชข้อมูล (Refresh)
          </button>
          {onClearData && (
            <button
              onClick={onClearData}
              title="ล้างข้อมูลออเดอร์ แผนจัดส่ง และ Fleet ทั้งหมดในระบบ"
              style={{
                padding: '10px 18px',
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                borderRadius: '10px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'all 0.2s ease'
              }}
            >
              🧹 ล้างข้อมูลทั้งหมด
            </button>
          )}
        </div>
      </div>

      {/* Stats Quick Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: 'white', padding: '20px', borderRadius: '14px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px rgba(0,0,0,0.03)' }}>
          <div style={{ color: '#64748b', fontSize: '13px', fontWeight: 600 }}>📦 ออเดอร์ในฐานข้อมูลทั้งหมด</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#1e293b', marginTop: '4px' }}>{orders.length} <span style={{ fontSize: '14px', fontWeight: 500 }}>รายการ</span></div>
        </div>
        <div style={{ background: 'white', padding: '20px', borderRadius: '14px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px rgba(0,0,0,0.03)' }}>
          <div style={{ color: '#64748b', fontSize: '13px', fontWeight: 600 }}>🧠 พิกัดจดจำความแม่นยำถาวร (100%)</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#10b981', marginTop: '4px' }}>{memories.length} <span style={{ fontSize: '14px', fontWeight: 500 }}>พิกัดยืนยันแล้ว</span></div>
        </div>
        <div style={{ background: 'white', padding: '20px', borderRadius: '14px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px rgba(0,0,0,0.03)' }}>
          <div style={{ color: '#64748b', fontSize: '13px', fontWeight: 600 }}>📜 แผนการจัดคิวรถย้อนหลัง</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#6366f1', marginTop: '4px' }}>{history.length} <span style={{ fontSize: '14px', fontWeight: 500 }}>รอบประมวลผล</span></div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '2px solid #e2e8f0', paddingBottom: '2px' }}>
        <button
          onClick={() => setActiveTab('orders')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: activeTab === 'orders' ? '#3b82f6' : 'transparent',
            color: activeTab === 'orders' ? 'white' : '#64748b',
            borderRadius: '10px 10px 0 0',
            fontWeight: 700,
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          📦 รายการออเดอร์ (Orders Table)
        </button>
        <button
          onClick={() => setActiveTab('memories')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: activeTab === 'memories' ? '#10b981' : 'transparent',
            color: activeTab === 'memories' ? 'white' : '#64748b',
            borderRadius: '10px 10px 0 0',
            fontWeight: 700,
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          🧠 คลังความจำพิกัดถาวร (Customer Location Memory)
        </button>
        <button
          onClick={() => setActiveTab('history')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: activeTab === 'history' ? '#6366f1' : 'transparent',
            color: activeTab === 'history' ? 'white' : '#64748b',
            borderRadius: '10px 10px 0 0',
            fontWeight: 700,
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          📜 ประวัติการจัดคิวรถ (Route History)
        </button>
        <button
          onClick={() => setActiveTab('vehicles')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: activeTab === 'vehicles' ? '#8b5cf6' : 'transparent',
            color: activeTab === 'vehicles' ? 'white' : '#64748b',
            borderRadius: '10px 10px 0 0',
            fontWeight: 700,
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          🚛 ข้อมูลรถขนส่ง (Vehicles Fleet DB)
        </button>
      </div>

      {/* Filter and Search Bar */}
      {activeTab !== 'history' && (
        <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <input
              type="text"
              placeholder={activeTab === 'orders' ? "🔎 ค้นหาชื่อลูกค้า, ที่อยู่, SO หรือโซน..." : "🔎 ค้นหาชื่อลูกค้าในความจำถาวร..."}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 16px',
                borderRadius: '10px',
                border: '1px solid #cbd5e1',
                fontSize: '14px'
              }}
            />
          </div>

          {activeTab === 'orders' && (
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                onClick={() => setScoreFilter('ALL')}
                style={{
                  padding: '8px 14px',
                  borderRadius: '8px',
                  border: 'none',
                  background: scoreFilter === 'ALL' ? '#1e293b' : '#e2e8f0',
                  color: scoreFilter === 'ALL' ? 'white' : '#475569',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                ทั้งหมด
              </button>
              <button
                onClick={() => setScoreFilter('HIGH')}
                style={{
                  padding: '8px 14px',
                  borderRadius: '8px',
                  border: 'none',
                  background: scoreFilter === 'HIGH' ? '#10b981' : '#e2e8f0',
                  color: scoreFilter === 'HIGH' ? 'white' : '#475569',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                🟢 แม่นยำสูง (&gt;=90%)
              </button>
              <button
                onClick={() => setScoreFilter('MID')}
                style={{
                  padding: '8px 14px',
                  borderRadius: '8px',
                  border: 'none',
                  background: scoreFilter === 'MID' ? '#f59e0b' : '#e2e8f0',
                  color: scoreFilter === 'MID' ? 'white' : '#475569',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                🟡 ปานกลาง (70-89%)
              </button>
              <button
                onClick={() => setScoreFilter('LOW')}
                style={{
                  padding: '8px 14px',
                  borderRadius: '8px',
                  border: 'none',
                  background: scoreFilter === 'LOW' ? '#ef4444' : '#e2e8f0',
                  color: scoreFilter === 'LOW' ? 'white' : '#475569',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                🔴 คลาดเคลื่อน (&lt;70%)
              </button>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#64748b', fontSize: '16px' }}>
          ⏳ กำลังดึงข้อมูลจาก Database...
        </div>
      ) : (
        <div style={{ background: 'white', borderRadius: '14px', border: '1px solid #e2e8f0', overflow: 'hidden', boxShadow: '0 4px 6px rgba(0,0,0,0.02)' }}>
          {/* Orders Table */}
          {activeTab === 'orders' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                    <th style={{ padding: '12px 16px' }}>#ID</th>
                    <th style={{ padding: '12px 16px' }}>เลขที่ SO</th>
                    <th style={{ padding: '12px 16px' }}>ชื่อลูกค้า/บริษัท</th>
                    <th style={{ padding: '12px 16px' }}>ที่อยู่จัดส่ง</th>
                    <th style={{ padding: '12px 16px' }}>โซน</th>
                    <th style={{ padding: '12px 16px' }}>น้ำหนัก (kg)</th>
                    <th style={{ padding: '12px 16px' }}>พิกัด (Lat, Lng)</th>
                    <th style={{ padding: '12px 16px' }}>คะแนนความแม่นยำ</th>
                    <th style={{ padding: '12px 16px' }}>จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.length === 0 ? (
                    <tr>
                      <td colSpan="9" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                        ไม่พบข้อมูลรายการสั่งซื้อตามเงื่อนไข
                      </td>
                    </tr>
                  ) : (
                    filteredOrders.map((o, idx) => {
                      const score = o.confidence_score !== undefined ? o.confidence_score : 50.0
                      return (
                        <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>#{o.id || idx + 1}</td>
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#3b82f6' }}>{o.order_number || '-'}</td>
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#1e293b' }}>{o.customer}</td>
                          <td style={{ padding: '12px 16px', color: '#475569', maxWidth: '280px' }}>{o.address}</td>
                          <td style={{ padding: '12px 16px' }}>
                            <span style={{ background: '#f1f5f9', color: '#334155', padding: '4px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 600 }}>
                              {o.zone || 'ไม่ระบุ'}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', fontWeight: 700 }}>{o.weight} kg</td>
                          <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: '12px' }}>
                            {o.lat && o.lng ? `${o.lat.toFixed(5)}, ${o.lng.toFixed(5)}` : 'ไม่มีพิกัด'}
                          </td>
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#334155' }}>
                            {o.is_verified ? '100%' : `${Math.round(score)}%`}
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            {o.lat && o.lng && (
                              <a
                                href={`https://www.google.com/maps/search/?api=1&query=${o.lat},${o.lng}`}
                                target="_blank"
                                rel="noreferrer"
                                style={{
                                  color: '#2563eb',
                                  textDecoration: 'none',
                                  fontWeight: 600,
                                  fontSize: '12px',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px'
                                }}
                              >
                                🗺️ ดูบนแผนที่ ↗
                              </a>
                            )}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Customer Location Memory Table */}
          {activeTab === 'memories' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                    <th style={{ padding: '12px 16px' }}>#ID</th>
                    <th style={{ padding: '12px 16px' }}>Customer Key (ชื่อ + ที่อยู่)</th>
                    <th style={{ padding: '12px 16px' }}>สถานที่ยืนยัน (Formatted Address)</th>
                    <th style={{ padding: '12px 16px' }}>พิกัดยืนยันจริง (Lat, Lng)</th>
                    <th style={{ padding: '12px 16px' }}>ความแม่นยำ</th>
                    <th style={{ padding: '12px 16px' }}>อัปเดตล่าสุด</th>
                    <th style={{ padding: '12px 16px' }}>จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMemories.length === 0 ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                        ยังไม่มีข้อมูลพิกัดความจำถาวร (เมื่อมีการยืนยันพิกัดหรือลากหมุด ข้อมูลจะมาปรากฏที่นี่อัตโนมัติ)
                      </td>
                    </tr>
                  ) : (
                    filteredMemories.map((m, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>#{m.id}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0f172a' }}>{m.customer_key}</td>
                        <td style={{ padding: '12px 16px', color: '#475569' }}>{m.formatted_address || '-'}</td>
                        <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontWeight: 700, color: '#10b981' }}>
                          {m.lat?.toFixed(6) ?? '-'}, {m.lng?.toFixed(6) ?? '-'}
                        </td>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#334155' }}>
                          100%
                        </td>
                        <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '12px' }}>{m.updated_at || '-'}</td>
                        <td style={{ padding: '12px 16px' }}>
                          <button
                            onClick={() => handleDeleteMemory(m.id, m.customer_key)}
                            style={{
                              background: '#fee2e2',
                              color: '#ef4444',
                              border: 'none',
                              padding: '6px 12px',
                              borderRadius: '6px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              fontSize: '12px'
                            }}
                          >
                            🗑️ ลบความจำ
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Route Optimization History Table */}
          {activeTab === 'history' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                    <th style={{ padding: '12px 16px' }}>#Plan ID</th>
                    <th style={{ padding: '12px 16px' }}>วันที่ประมวลผล</th>
                    <th style={{ padding: '12px 16px' }}>จำนวนออเดอร์</th>
                    <th style={{ padding: '12px 16px' }}>จำนวนรถที่ใช้</th>
                    <th style={{ padding: '12px 16px' }}>คลังสินค้า (Depot)</th>
                  </tr>
                </thead>
                <tbody>
                  {history.length === 0 ? (
                    <tr>
                      <td colSpan="5" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                        ยังไม่มีประวัติการคำนวณจัดคิวรถ
                      </td>
                    </tr>
                  ) : (
                    history.map((h, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#6366f1' }}>#PLAN-{h.id}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 600 }}>{h.plan_date || '-'}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700 }}>{h.total_orders} รายการ</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#10b981' }}>{h.total_vehicles} คัน</td>
                        <td style={{ padding: '12px 16px', color: '#64748b' }}>{h.depot_address || 'คลังบรมราชชนนี (ตลิ่งชัน)'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Vehicles Fleet Table */}
          {activeTab === 'vehicles' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                    <th style={{ padding: '12px 16px' }}>#ID</th>
                    <th style={{ padding: '12px 16px' }}>ชื่อคันรถ</th>
                    <th style={{ padding: '12px 16px' }}>ทะเบียนรถ</th>
                    <th style={{ padding: '12px 16px' }}>พนักงานขับรถ</th>
                    <th style={{ padding: '12px 16px' }}>ความจุบรรทุกสูงสุด</th>
                    <th style={{ padding: '12px 16px' }}>สถานะ</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right' }}>จัดการข้อมูล</th>
                  </tr>
                </thead>
                <tbody>
                  {vehicles.length === 0 ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                        ไม่พบข้อมูลรถขนส่งในฐานข้อมูล
                      </td>
                    </tr>
                  ) : (
                    vehicles.map((v, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#8b5cf6' }}>#{v.id}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#1e293b' }}>{v.name || `รถคันที่ ${v.id}`}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700, color: '#2563eb' }}>{v.plate}</td>
                        <td style={{ padding: '12px 16px', color: '#475569' }}>{v.driver || '-'}</td>
                        <td style={{ padding: '12px 16px', fontWeight: 700 }}>{v.capacity} kg ({(v.capacity / 1000).toFixed(2)} ตัน)</td>
                        <td style={{ padding: '12px 16px' }}>
                          {v.active ? (
                            <span style={{ color: '#10b981', fontWeight: 700 }}>🟢 เปิดใช้งาน</span>
                          ) : (
                            <span style={{ color: '#ef4444', fontWeight: 600 }}>🔴 ปิดใช้งาน</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            <button
                              onClick={() => handleToggleVehicleActive(v)}
                              style={{
                                padding: '6px 12px',
                                borderRadius: '6px',
                                border: 'none',
                                background: v.active ? '#f1f5f9' : '#ecfdf5',
                                color: v.active ? '#475569' : '#047857',
                                fontSize: '12px',
                                fontWeight: 700,
                                cursor: 'pointer'
                              }}
                              title={v.active ? 'คลิกเพื่อปิดใช้งาน' : 'คลิกเพื่อเปิดใช้งาน'}
                            >
                              {v.active ? '🔴 ปิดใช้งาน' : '🟢 เปิดใช้งาน'}
                            </button>
                            <button
                              onClick={() => handleDeleteVehicleInDB(v.id, v.name || v.plate)}
                              style={{
                                padding: '6px 10px',
                                borderRadius: '6px',
                                border: 'none',
                                background: '#fee2e2',
                                color: '#ef4444',
                                fontSize: '12px',
                                fontWeight: 700,
                                cursor: 'pointer'
                              }}
                              title="ลบรถคันนี้ออกจากฐานข้อมูล"
                            >
                              🗑️ ลบรถ
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DatabaseViewer
