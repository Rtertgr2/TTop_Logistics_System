import { hasButtonPermission } from '../permissions'

/**
 * PermissionGate — ซ่อน/แสดง children ตามสิทธิ์ของ user
 *
 * ใช้งาน:
 *   <PermissionGate role={user.role} permission="clear_data">
 *     <button>ล้างข้อมูล</button>
 *   </PermissionGate>
 *
 *   หรือใช้ fallback เมื่อไม่มีสิทธิ์:
 *   <PermissionGate role={user.role} permission="manage_employees" fallback={<span>ไม่มีสิทธิ์</span>}>
 *     <button>จัดการ</button>
 *   </PermissionGate>
 */
export default function PermissionGate({ role, permission, children, fallback = null }) {
  if (hasButtonPermission(role, permission)) {
    return children
  }
  return fallback
}
