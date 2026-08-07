function Sidebar({ currentPage, onNavigate, onClearData, user, onLogout }) {
  const menuItems = [
    { id: 'dashboard', label: 'แดชบอร์ด', icon: '📊' },
    { id: 'upload', label: 'อัปโหลดไฟล์', icon: '📁' },
    { id: 'orders', label: 'รายการสั่งซื้อ', icon: '📋' },
    { id: 'booking', label: 'จัดการวันส่ง', icon: '📅' },
    { id: 'routes', label: 'ผลลัพธ์เส้นทาง', icon: '🗺️' },
    { id: 'vehicles', label: 'จัดการรถขนส่ง', icon: '🚛' },
    { id: 'driver', label: 'Driver Mobile', icon: '📱' },
    { id: 'load-balance', label: 'Load Balancing', icon: '⚖️' },
    { id: 'admin', label: 'Admin Dashboard', icon: '📊' },
    { id: 'database', label: 'จัดการฐานข้อมูล', icon: '🗄️' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <span className="logo-icon">🚚</span>
          <span className="logo-text">Route Planner</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer" style={{ flexDirection: 'column', gap: '10px', alignItems: 'stretch' }}>
        {user && (
          <div className="sidebar-user">
            <span className="user-avatar">👤</span>
            <div className="user-info">
              <span className="user-name">{user.name || user.username}</span>
              <span className="user-role">{user.role}</span>
            </div>
          </div>
        )}
        {onLogout && (
          <button className="sidebar-reset-btn" onClick={onLogout} title="ออกจากระบบ">
            <span>🚪</span>
            <span>ออกจากระบบ</span>
          </button>
        )}
        {onClearData && (
          <button
            className="sidebar-reset-btn"
            onClick={onClearData}
            title="ล้างข้อมูลออเดอร์ แผนจัดส่ง และ Fleet รถขนส่งทั้งหมด"
          >
            <span>🗑️</span>
            <span>รีเซ็ตข้อมูลระบบ</span>
          </button>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <span>Logistics System</span>
          <span>v2.1.0</span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
