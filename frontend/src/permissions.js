// ─── RBAC Permission Definitions ────────────────────────────────
// กำหนดว่าแต่ละ role สามารถเข้าถึงเมนูใด และกดปุ่มใดได้บ้าง

export const ROLE_PERMISSIONS = {
  admin: {
    menus: [
      'dashboard', 'upload', 'orders', 'booking', 'routes',
      'vehicles', 'driver', 'load-balance', 'admin', 'employees', 'database'
    ],
    buttons: [
      'clear_data', 'manage_vehicles', 'manage_employees',
      'delete_vehicle', 'plan_routes', 'verify_location', 'send_line'
    ]
  },
  dispatcher: {
    menus: [
      'dashboard', 'upload', 'orders', 'booking', 'routes',
      'vehicles', 'load-balance'
    ],
    buttons: [
      'clear_data', 'manage_vehicles', 'plan_routes', 'verify_location', 'send_line'
    ]
  },
  driver: {
    menus: ['dashboard', 'driver'],
    buttons: []
  },
  user: {
    menus: ['dashboard', 'orders'],
    buttons: []
  }
}

export function hasMenuPermission(role, menuId) {
  if (!role) return false
  const perms = ROLE_PERMISSIONS[role]
  if (!perms) return false
  return perms.menus.includes(menuId)
}

export function hasButtonPermission(role, buttonId) {
  if (!role) return false
  const perms = ROLE_PERMISSIONS[role]
  if (!perms) return false
  return perms.buttons.includes(buttonId)
}

export function getMenuItemsForRole(role) {
  const allMenus = [
    { id: 'dashboard', label: 'แดชบอร์ด', icon: 'dashboard' },
    { id: 'upload', label: 'อัปโหลดไฟล์', icon: 'upload' },
    { id: 'orders', label: 'รายการสั่งซื้อ', icon: 'orders' },
    { id: 'booking', label: 'จัดการวันส่ง', icon: 'booking' },
    { id: 'routes', label: 'ผลลัพธ์เส้นทาง', icon: 'routes' },
    { id: 'vehicles', label: 'จัดการรถขนส่ง', icon: 'vehicles' },
    { id: 'driver', label: 'Driver Mobile', icon: 'driver' },
    { id: 'load-balance', label: 'Load Balancing', icon: 'load-balance' },
    { id: 'admin', label: 'Admin Dashboard', icon: 'admin' },
    { id: 'employees', label: 'จัดการพนักงาน', icon: 'employees' },
    { id: 'database', label: 'จัดการฐานข้อมูล', icon: 'database' },
  ]
  return allMenus.filter(item => hasMenuPermission(role, item.id))
}
