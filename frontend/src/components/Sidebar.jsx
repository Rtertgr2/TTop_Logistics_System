function Sidebar({ currentPage, onNavigate, onClearData }) {
  const menuItems = [
    { id: 'dashboard', label: 'แดชบอร์ด', icon: '📊' },
    { id: 'upload', label: 'อัปโหลดไฟล์', icon: '📁' },
    { id: 'orders', label: 'รายการสั่งซื้อ', icon: '📋' },
    { id: 'routes', label: 'ผลลัพธ์เส้นทาง', icon: '🗺️' },
    { id: 'vehicles', label: 'จัดการรถขนส่ง', icon: '🚛' },
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
      <div className="sidebar-footer">
        <p>v1.2.0</p>
      </div>
    </aside>
  )
}

export default Sidebar
