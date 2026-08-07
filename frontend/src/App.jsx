import { useState, useEffect, useMemo } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import FileUpload from './components/FileUpload'
import RouteResult from './components/RouteResult'
import MapView from './components/MapView'
import VehicleManager from './components/VehicleManager'
import DatabaseViewer from './components/DatabaseViewer'
import DriverMobile from './components/DriverMobile'
import LoadBalancer from './components/LoadBalancer'
import AdminDashboard from './components/AdminDashboard'
import LoginScreen from './components/LoginScreen'
import BookingDashboard from './components/BookingDashboard'
import { getToken, setToken, logout } from './api'

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [orders, setOrders] = useState([])
  const [routes, setRoutes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [deferredInfo, setDeferredInfo] = useState(null)

  useEffect(() => {
    const handleUnauthorized = () => {
      setToken(null)
      setUser(null)
      setCurrentPage('dashboard')
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    window.addEventListener('auth:logout', handleUnauthorized)
    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized)
      window.removeEventListener('auth:logout', handleUnauthorized)
    }
  }, [])

  // Restore session from stored token on page load
  useEffect(() => {
    const restoreSession = async () => {
      if (!getToken()) {
        setAuthChecked(true)
        return
      }
      try {
        const res = await fetch('/api/v1/auth/me')
        if (res.ok) {
          const data = await res.json()
          setUser(data.user)
        } else if (res.status === 401 || res.status === 403) {
          setToken(null)
        }
        // network/other errors: keep token, user can retry
      } catch {
        // network error — don't clear token, just let user re-login manually
      } finally {
        setAuthChecked(true)
      }
    }
    restoreSession()
  }, [])

  // 🔄 โหลดข้อมูลของวันปัจจุบันจาก Database อัตโนมัติเมื่อรีเฟรชหน้าเว็บ (ตัดรอบเที่ยงคืน)
  useEffect(() => {
    fetchTodayData()
  }, [])

  const fetchTodayData = async () => {
    try {
      const [resOrders, resRoutes] = await Promise.all([
        fetch('/api/v1/orders/today'),
        fetch('/api/v1/routes/today')
      ])
      if (resOrders.ok) {
        const dataOrders = await resOrders.json()
        if (dataOrders.orders && dataOrders.orders.length > 0) {
          setOrders(dataOrders.orders)
        }
      }
      if (resRoutes.ok) {
        const dataRoutes = await resRoutes.json()
        if (dataRoutes.routes && dataRoutes.routes.length > 0) {
          setRoutes(dataRoutes.routes)
        }
      }
    } catch (err) {
      // Silent fail for auto-restore
    }
  }

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedZoneFilter, setSelectedZoneFilter] = useState('ALL')

  // Extract unique zones for filtering
  const availableZones = useMemo(
    () => Array.from(new Set(orders.map(o => o.zone || 'ไม่ระบุ').filter(Boolean))),
    [orders]
  )

  // Filtered orders calculation
  const filteredOrders = useMemo(() => orders.filter(order => {
    const q = searchQuery.toLowerCase().trim()
    const matchesSearch = !q || (
      (order.customer || '').toLowerCase().includes(q) ||
      (order.address || '').toLowerCase().includes(q) ||
      (order.order_number || '').toLowerCase().includes(q) ||
      (order.zone || '').toLowerCase().includes(q) ||
      (order.products || []).some(p => (p.name || '').toLowerCase().includes(q))
    )

    const matchesZone = selectedZoneFilter === 'ALL' || (order.zone === selectedZoneFilter)

    return matchesSearch && matchesZone
  }), [orders, searchQuery, selectedZoneFilter])

  const totalFilteredWeight = useMemo(
    () => filteredOrders.reduce((sum, o) => sum + (o.weight || 0), 0),
    [filteredOrders]
  )

  const handleUploadSuccess = (data) => {
    setOrders(data.orders)
    setError(null)
    setCurrentPage('orders')
  }

  const handlePlanRoutes = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/v1/plan-routes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orders })
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Server error: ${response.status}`)
      }

      const data = await response.json()
      setRoutes(data.routes)
      setDeferredInfo(
        data.deferred_count > 0
          ? {
              orders: data.deferred_orders || [],
              weight: data.deferred_weight || 0,
              count: data.deferred_count || 0,
            }
          : null
      )
      setCurrentPage('routes')
    } catch (err) {
      setError(err.message || 'เกิดข้อผิดพลาดในการคำนวณเส้นทาง')
    } finally {
      setLoading(false)
    }
  }

  const handleSendLineNotification = async (routesToSend) => {
    try {
      const response = await fetch('/api/v1/send-line-notification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ routes: routesToSend })
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'ส่ง LINE notification ไม่สำเร็จ')
      }

      const data = await response.json()
      return data
    } catch (err) {
      throw err
    }
  }

  const handleSendDriverNotification = async (route, driverLineUserId) => {
    try {
      const response = await fetch('/api/v1/send-driver-notification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ route, driver_line_user_id: driverLineUserId })
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'ส่ง LINE ให้คนขับไม่สำเร็จ')
      }

      const data = await response.json()
      return data
    } catch (err) {
      throw err
    }
  }

  const handleLocationVerified = (orderId, lat, lng) => {
    setOrders(prev => prev.map(o =>
      o.id === orderId
        ? { ...o, lat, lng, verified_lat: lat, verified_lng: lng, is_verified: true }
        : o
    ))
    setRoutes(prev => prev.map(r => ({
      ...r,
      stops: (r.stops || []).map(s =>
        (s.id === orderId || s.order_id === orderId)
          ? { ...s, lat, lng, verified_lat: lat, verified_lng: lng, is_verified: true }
          : s
      )
    })))
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return (
          <Dashboard
            orders={orders}
            routes={routes}
            onNavigate={setCurrentPage}
            onClearData={handleClearData}
          />
        )
      case 'upload':
        return <FileUpload onSuccess={handleUploadSuccess} />
      case 'orders':
        return (
          <div className="page-container">
            <div className="page-header">
              <div>
                <h2>รายการสั่งซื้อ ({orders.length} รายการ)</h2>
                <small className="sub-title-desc">ค้นหา กรองโซน และตรวจสอบรายละเอียดออเดอร์</small>
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                {orders.length > 0 && (
                  <>
                    <button
                      className="btn-danger-outline"
                      onClick={handleClearData}
                      style={{
                        padding: '10px 16px',
                        background: '#fff1f2',
                        color: '#e11d48',
                        border: '1px solid #fecdd3',
                        borderRadius: '10px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      🗑️ ล้างข้อมูล
                    </button>
                    <button
                      className="btn-primary"
                      onClick={handlePlanRoutes}
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <span className="spinner"></span>
                          กำลังคำนวณ...
                        </>
                      ) : (
                        '🚀 คำนวณเส้นทาง'
                      )}
                    </button>
                  </>
                )}
              </div>
            </div>

            {error && (
              <div className="error-banner">
                <span>⚠️ {error}</span>
                <button onClick={() => setError(null)}>✕</button>
              </div>
            )}

            {orders.length === 0 ? (
              <div className="empty-state">
                <p>ยังไม่มีข้อมูลรายการสั่งซื้อ กรุณาอัปโหลดไฟล์ PDF</p>
                <button
                  className="btn-primary"
                  onClick={() => setCurrentPage('upload')}
                >
                  📁 อัปโหลดไฟล์ PDF
                </button>
              </div>
            ) : (
              <>
                {/* Modern Order Search & Filter Control Bar */}
                <div className="order-search-bar-container">
                  <div className="search-input-group">
                    <span className="search-icon">🔍</span>
                    <input
                      type="text"
                      className="order-search-input"
                      placeholder="ค้นหาชื่อลูกค้า, ที่อยู่จัดส่ง, เลขที่ SO หรือสินค้า..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    {searchQuery && (
                      <button className="btn-clear-search" onClick={() => setSearchQuery('')}>✕</button>
                    )}
                  </div>

                  <div className="zone-filter-group">
                    <label>🗺️ โซนพื้นที่:</label>
                    <select
                      className="zone-filter-select"
                      value={selectedZoneFilter}
                      onChange={(e) => setSelectedZoneFilter(e.target.value)}
                    >
                      <option value="ALL">📍 แสดงทุกโซน ({orders.length})</option>
                      {availableZones.map((zone, zIdx) => {
                        const count = orders.filter(o => o.zone === zone).length
                        return (
                          <option key={zIdx} value={zone}>
                            {zone} ({count} รายการ)
                          </option>
                        )
                      })}
                    </select>
                  </div>
                </div>

                {/* Filter Summary Stats */}
                <div className="search-stats-row">
                  <span>
                    พบ <strong>{filteredOrders.length}</strong> จาก {orders.length} ออเดอร์
                    {selectedZoneFilter !== 'ALL' && <span className="active-filter-badge">โซน: {selectedZoneFilter}</span>}
                    {searchQuery && <span className="active-filter-badge">คำค้น: "{searchQuery}"</span>}
                  </span>
                  <span className="stats-weight-sum">
                    ⚖️ น้ำหนักรวมกลุ่มที่เลือก: <strong>{totalFilteredWeight.toLocaleString()} kg</strong>
                  </span>
                </div>

                {filteredOrders.length === 0 ? (
                  <div className="no-search-results">
                    <p>🔍 ไม่พบรายการสั่งซื้อที่ตรงกับคำค้นหา "{searchQuery}"</p>
                    <button className="btn-secondary" onClick={() => { setSearchQuery(''); setSelectedZoneFilter('ALL'); }}>
                      🔄 ล้างคำค้นหาทั้งหมด
                    </button>
                  </div>
                ) : (
                  <div className="orders-content">
                    <div className="orders-list">
                      {filteredOrders.map((order, idx) => (
                        <div key={idx} className="order-card">
                          <div className="order-icon">📦</div>
                          <div className="order-info">
                            <div className="order-card-header">
                              <h4>{order.customer}</h4>
                              {order.zone && <span className="order-zone-tag">{order.zone}</span>}
                            </div>
                            <p className="order-addr-text">📍 {order.address}</p>
                            {order.order_number && (
                              <p className="order-number">📋 SO: {order.order_number}</p>
                            )}
                            {order.products && order.products.length > 0 ? (
                              <div className="products-list" style={{ marginTop: '6px' }}>
                                {order.products.map((p, pIdx) => (
                                  <span key={pIdx} className="product-tag" style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', padding: '3px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                    🛍️ {p.name} ({p.quantity} {p.unit || 'ชิ้น'})
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <div className="products-list" style={{ marginTop: '6px' }}>
                                <span className="product-tag" style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', padding: '3px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                  🛍️ สินค้าตามใบสั่งซื้อ {order.order_number ? `(SO: ${order.order_number})` : `(${order.weight || 50} kg)`}
                                </span>
                              </div>
                            )}
                          </div>
                          <span className="weight-badge">{order.weight} kg</span>
                        </div>
                      ))}
                    </div>
                    <div className="orders-map">
                      <MapView orders={filteredOrders} routes={routes} onVerified={handleLocationVerified} />
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )
      case 'routes':
        return (
          <div className="page-container">
            <RouteResult routes={routes} deferredInfo={deferredInfo} onSendLine={handleSendLineNotification} onSendDriverLine={handleSendDriverNotification} />
            {routes.length > 0 && (
              <div className="routes-map-container">
                <h3>🗺️ แผนที่เส้นทางจัดส่งสินค้า</h3>
                <MapView orders={orders} routes={routes} onVerified={handleLocationVerified} />
              </div>
            )}
          </div>
        )
      case 'vehicles':
        return <VehicleManager />
      case 'database':
        return <DatabaseViewer onClearData={handleClearData} />
      case 'driver':
        return <DriverMobile />
      case 'load-balance':
        return <LoadBalancer />
      case 'booking':
        return <BookingDashboard />
      case 'admin':
        return <AdminDashboard />
      default:
        return (
          <Dashboard
            orders={orders}
            routes={routes}
            onNavigate={setCurrentPage}
            onClearData={handleClearData}
          />
        )
    }
  }

  const handleClearData = async () => {
    if (window.confirm('⚠️ คุณแน่ใจหรือไม่ว่าต้องการล้างข้อมูลออเดอร์ แผนจัดส่ง และ Fleet ทั้งหมดในระบบ?')) {
      try {
        const res = await fetch('/api/v1/clear-data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ confirm: 'CLEAR_ALL_DATA' })
        })
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.detail || `Server error: ${res.status}`)
        }
        setOrders([])
        setRoutes([])
        setDeferredInfo(null)
        setError(null)
        alert('🎉 ล้างข้อมูลทั้งหมดในระบบเรียบร้อยแล้ว!')
        setCurrentPage('upload')
      } catch (err) {
        alert(`⚠️ ไม่สามารถล้างข้อมูลได้: ${err.message}`)
      }
    }
  }

  const handleLoginSuccess = (data) => {
    setToken(data.access_token)
    setUser(data.user)
    setCurrentPage('dashboard')
  }

  if (!authChecked) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div className="spinner"></div>
          <p>กำลังโหลด...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <LoginScreen onLoginSuccess={handleLoginSuccess} />
  }

  return (
    <div className="app-layout">
      <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} onClearData={handleClearData} user={user} onLogout={logout} />
      <main className="main-content">{renderPage()}</main>
    </div>
  )
}

export default App
