import { useState, useEffect, useCallback } from "react"
import axios from "axios"
import { useAuth } from "@/context/AuthContext"
import PermissionGate from "@/components/PermissionGate"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import SearchInput from "@/components/SearchInput"
import ConfirmDialog from "@/components/ConfirmDialog"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  Users,
  Plus,
  Pencil,
  Trash2,
  KeyRound,
  FileClock,
  ChevronLeft,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react"

const ROLE_OPTIONS = [
  { value: "user", label: "User" },
  { value: "driver", label: "Driver" },
  { value: "dispatcher", label: "Dispatcher" },
  { value: "admin", label: "Admin" },
]

const ROLE_BADGE = {
  admin: "purple",
  dispatcher: "info",
  driver: "warning",
  user: "secondary",
}

const EMPTY_FORM = {
  username: "",
  password: "",
  role: "user",
  name: "",
  email: "",
  phone: "",
  department: "",
  position: "",
}

export default function EmployeeManager() {
  const { user: currentUser } = useAuth()

  const [employees, setEmployees] = useState([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState("all")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  const [showCreate, setShowCreate] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showAudit, setShowAudit] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [toggleTarget, setToggleTarget] = useState(null)

  const [form, setForm] = useState(EMPTY_FORM)
  const [editForm, setEditForm] = useState({})
  const [newPassword, setNewPassword] = useState("")

  const loadEmployees = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "20",
        search,
        role: roleFilter === "all" ? "" : roleFilter,
      })
      const res = await axios.get(`/api/v1/auth/employees?${params}`)
      setEmployees(res.data.employees || [])
      setTotal(res.data.total || 0)
      setPages(res.data.pages || 1)
    } catch (err) {
      setMessage({ type: "error", text: "ไม่สามารถโหลดรายชื่อพนักงานได้" })
    } finally {
      setLoading(false)
    }
  }, [page, search, roleFilter])

  useEffect(() => {
    loadEmployees()
  }, [loadEmployees])

  const handleCreate = async (e) => {
    e.preventDefault()
    setMessage(null)
    try {
      await axios.post("/api/v1/auth/employees", form)
      setMessage({
        type: "success",
        text: `สร้างพนักงาน ${form.username} เรียบร้อยแล้ว`,
      })
      setShowCreate(false)
      setForm(EMPTY_FORM)
      setPage(1)
      loadEmployees()
    } catch (err) {
      const detail = err.response?.data?.detail || "เกิดข้อผิดพลาด"
      setMessage({ type: "error", text: detail })
    }
  }

  const handleEdit = async (e) => {
    e.preventDefault()
    setMessage(null)
    try {
      const payload = { ...editForm }
      delete payload.username
      delete payload.id
      delete payload.created_at
      await axios.put(`/api/v1/auth/employees/${selectedUser.id}`, payload)
      setMessage({
        type: "success",
        text: `อัปเดต ${selectedUser.username} เรียบร้อยแล้ว`,
      })
      setShowEdit(false)
      setSelectedUser(null)
      loadEmployees()
    } catch (err) {
      const detail = err.response?.data?.detail || "เกิดข้อผิดพลาด"
      setMessage({ type: "error", text: detail })
    }
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setMessage(null)
    try {
      await axios.put(`/api/v1/auth/employees/${selectedUser.id}/password`, {
        new_password: newPassword,
      })
      setMessage({
        type: "success",
        text: `เปลี่ยนรหัสผ่าน ${selectedUser.username} เรียบร้อยแล้ว`,
      })
      setShowPassword(false)
      setNewPassword("")
      setSelectedUser(null)
    } catch (err) {
      const detail = err.response?.data?.detail || "เกิดข้อผิดพลาด"
      setMessage({ type: "error", text: detail })
    }
  }

  const handleToggleActive = (emp) => {
    setToggleTarget(emp)
  }

  const confirmToggleActive = async () => {
    const emp = toggleTarget
    if (!emp) return
    const action = emp.is_active ? "ปิดการใช้งาน" : "เปิดการใช้งาน"
    setToggleTarget(null)
    setMessage(null)
    try {
      const res = await axios.put(
        `/api/v1/auth/employees/${emp.id}/toggle-active`
      )
      setMessage({ type: "success", text: res.data.message })
      loadEmployees()
    } catch (err) {
      const detail = err.response?.data?.detail || "เกิดข้อผิดพลาด"
      setMessage({ type: "error", text: detail })
    }
  }

  const openEdit = (emp) => {
    setSelectedUser(emp)
    setEditForm({
      name: emp.name || "",
      email: emp.email || "",
      phone: emp.phone || "",
      department: emp.department || "",
      position: emp.position || "",
      role: emp.role || "user",
    })
    setShowEdit(true)
  }

  const openPassword = (emp) => {
    setSelectedUser(emp)
    setNewPassword("")
    setShowPassword(true)
  }

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-5">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-xl">จัดการพนักงาน (RBAC)</CardTitle>
              <CardDescription>
                เพิ่ม แก้ไข และจัดการสิทธิ์ผู้ใช้งานในระบบ
              </CardDescription>
            </div>
          </div>
          <PermissionGate role={currentUser?.role} permission="manage_employees">
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              เพิ่มพนักงาน
            </Button>
          </PermissionGate>
        </CardHeader>
        <CardContent className="space-y-4">
          {message && (
            <div
              className={cn(
                "flex items-start justify-between gap-3 rounded-md border px-4 py-3 text-sm",
                message.type === "success"
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-red-200 bg-red-50 text-red-700"
              )}
            >
              <span>{message.text}</span>
              <button
                onClick={() => setMessage(null)}
                className="shrink-0 rounded-sm opacity-70 transition-opacity hover:opacity-100"
                aria-label="ปิด"
              >
                <XCircle className="h-4 w-4" />
              </button>
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <SearchInput
              wrapperClassName="relative flex-1"
              placeholder="ค้นหา username, ชื่อ, email, แผนก..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
            <Select
              value={roleFilter}
              onValueChange={(v) => {
                setRoleFilter(v)
                setPage(1)
              }}
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="ทุก Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">ทุก Role</SelectItem>
                {ROLE_OPTIONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              onClick={() => setShowAudit(true)}
              className="shrink-0"
            >
              <FileClock className="h-4 w-4" />
              ประวัติการแก้ไข
            </Button>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>ชื่อ</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>แผนก / ตำแหน่ง</TableHead>
                  <TableHead>Email / โทร</TableHead>
                  <TableHead>สถานะ</TableHead>
                  <TableHead className="text-right">จัดการ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center">
                      <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : employees.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="h-24 text-center text-muted-foreground"
                    >
                      ไม่พบรายชื่อพนักงาน
                    </TableCell>
                  </TableRow>
                ) : (
                  employees.map((emp) => (
                    <TableRow key={emp.id}>
                      <TableCell className="font-medium">{emp.username}</TableCell>
                      <TableCell>{emp.name || "-"}</TableCell>
                      <TableCell>
                        <Badge variant={ROLE_BADGE[emp.role] || "secondary"}>
                          {ROLE_OPTIONS.find((r) => r.value === emp.role)?.label ||
                            emp.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div>{emp.department || "-"}</div>
                        <div className="text-xs text-muted-foreground">
                          {emp.position || ""}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>{emp.email || "-"}</div>
                        <div className="text-xs text-muted-foreground">
                          {emp.phone || ""}
                        </div>
                      </TableCell>
                      <TableCell>
                        {emp.is_active ? (
                          <Badge variant="success" className="gap-1">
                            <CheckCircle2 className="h-3 w-3" />
                            ใช้งาน
                          </Badge>
                        ) : (
                          <Badge variant="danger" className="gap-1">
                            <XCircle className="h-3 w-3" />
                            ปิดใช้
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <PermissionGate
                            role={currentUser?.role}
                            permission="manage_employees"
                          >
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => openEdit(emp)}
                              title="แก้ไข"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => openPassword(emp)}
                              title="เปลี่ยนรหัสผ่าน"
                            >
                              <KeyRound className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => handleToggleActive(emp)}
                              disabled={currentUser?.id === emp.id}
                              title={
                                emp.is_active ? "ปิดการใช้งาน" : "เปิดการใช้งาน"
                              }
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </PermissionGate>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
                ก่อนหน้า
              </Button>
              <span className="text-sm font-medium text-muted-foreground">
                หน้า {page} / {pages} (ทั้งหมด {total} คน)
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                disabled={page >= pages}
              >
                ถัดไป
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>เพิ่มพนักงานใหม่</DialogTitle>
            <DialogDescription>
              กรอกข้อมูลเพื่อสร้างบัญชีผู้ใช้งานใหม่
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <FormField label="Username *">
              <Input
                required
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                placeholder="เช่น somchai"
              />
            </FormField>
            <FormField label="รหัสผ่าน * (8+ ตัวอักษร, มีพิมพ์ใหญ่/เล็ก/ตัวเลข)">
              <Input
                required
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
              />
            </FormField>
            <FormField label="Role *">
              <Select
                value={form.role}
                onValueChange={(v) => setForm({ ...form, role: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="ชื่อ-สกุล">
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="เช่น สมชาย ใจดี"
              />
            </FormField>
            <FormField label="Email">
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="user@company.com"
              />
            </FormField>
            <FormField label="โทรศัพท์">
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="08x-xxx-xxxx"
              />
            </FormField>
            <FormField label="แผนก">
              <Input
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
                placeholder="เช่น ขนส่ง"
              />
            </FormField>
            <FormField label="ตำแหน่ง">
              <Input
                value={form.position}
                onChange={(e) => setForm({ ...form, position: e.target.value })}
                placeholder="เช่น หัวหน้าทีม"
              />
            </FormField>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreate(false)}
              >
                ยกเลิก
              </Button>
              <Button type="submit">สร้าง</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEdit} onOpenChange={setShowEdit}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>แก้ไข {selectedUser?.username}</DialogTitle>
            <DialogDescription>ปรับปรุงข้อมูลผู้ใช้งาน</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4">
            <FormField label="ชื่อ-สกุล">
              <Input
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </FormField>
            <FormField label="Role">
              <Select
                value={editForm.role}
                onValueChange={(v) => setEditForm({ ...editForm, role: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((r) => (
                    <SelectItem
                      key={r.value}
                      value={r.value}
                      disabled={r.value === "admin"}
                    >
                      {r.label}
                      {r.value === "admin" ? " (ไม่สามารถเปลี่ยนเป็นได้)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Email">
              <Input
                type="email"
                value={editForm.email}
                onChange={(e) =>
                  setEditForm({ ...editForm, email: e.target.value })
                }
              />
            </FormField>
            <FormField label="โทรศัพท์">
              <Input
                value={editForm.phone}
                onChange={(e) =>
                  setEditForm({ ...editForm, phone: e.target.value })
                }
              />
            </FormField>
            <FormField label="แผนก">
              <Input
                value={editForm.department}
                onChange={(e) =>
                  setEditForm({ ...editForm, department: e.target.value })
                }
              />
            </FormField>
            <FormField label="ตำแหน่ง">
              <Input
                value={editForm.position}
                onChange={(e) =>
                  setEditForm({ ...editForm, position: e.target.value })
                }
              />
            </FormField>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowEdit(false)}
              >
                ยกเลิก
              </Button>
              <Button type="submit">บันทึก</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Password Dialog */}
      <Dialog open={showPassword} onOpenChange={setShowPassword}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>เปลี่ยนรหัสผ่าน {selectedUser?.username}</DialogTitle>
            <DialogDescription>กำหนดรหัสผ่านใหม่สำหรับบัญชีนี้</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <FormField label="รหัสผ่านใหม่ * (8+ ตัวอักษร, มีพิมพ์ใหญ่/เล็ก/ตัวเลข)">
              <Input
                required
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
              />
            </FormField>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowPassword(false)}
              >
                ยกเลิก
              </Button>
              <Button type="submit">
                <KeyRound className="h-4 w-4" />
                เปลี่ยนรหัสผ่าน
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Audit Log Dialog */}
      {showAudit && (
        <AuditLogDialog
          open={showAudit}
          onOpenChange={setShowAudit}
        />
      )}

      <ConfirmDialog
        open={!!toggleTarget}
        onOpenChange={(open) => { if (!open) setToggleTarget(null) }}
        title={toggleTarget ? `ยืนยัน${toggleTarget.is_active ? "ปิดการใช้งาน" : "เปิดการใช้งาน"}` : "ยืนยัน"}
        description={toggleTarget ? `คุณแน่ใจหรือไม่ที่จะ${toggleTarget.is_active ? "ปิดการใช้งาน" : "เปิดการใช้งาน"} "${toggleTarget.username}"?` : ""}
        confirmLabel="ยืนยัน"
        onConfirm={confirmToggleActive}
      />
    </div>
  )
}

function FormField({ label, children }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-slate-700">{label}</Label>
      {children}
    </div>
  )
}

function AuditLogDialog({ open, onOpenChange }) {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: "50",
        username: search,
      })
      const res = await axios.get(`/api/v1/auth/audit-logs?${params}`)
      setLogs(res.data.logs || [])
      setTotal(res.data.total || 0)
    } catch (err) {
      // silent
    } finally {
      setLoading(false)
    }
  }, [page, search])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>ประวัติการแก้ไขพนักงาน</DialogTitle>
          <DialogDescription>
            บันทึกการเปลี่ยนแปลงบัญชีผู้ใช้งานทั้งหมด
          </DialogDescription>
        </DialogHeader>
        <SearchInput
          wrapperClassName="relative"
          placeholder="ค้นหาตาม username..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Separator />
        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-10 text-center text-sm text-muted-foreground">
            ไม่มีประวัติการแก้ไข
          </div>
        ) : (
          <ScrollArea className="max-h-[50vh] pr-3">
            <div className="space-y-2">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className="rounded-md border bg-slate-50 p-3 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-700">
                      {log.username}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {log.timestamp
                        ? new Date(log.timestamp).toLocaleString("th-TH")
                        : ""}
                    </span>
                  </div>
                  <div className="mt-1.5">
                    <Badge variant="info" className="mr-1.5">
                      {log.action}
                    </Badge>
                    {log.target_user && (
                      <span className="text-muted-foreground">
                        → {log.target_user}
                      </span>
                    )}
                  </div>
                  {log.details && (
                    <div className="mt-1 text-xs italic text-muted-foreground">
                      {log.details}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
        <div className="text-center text-xs text-muted-foreground">
          ทั้งหมด {total} รายการ
        </div>
      </DialogContent>
    </Dialog>
  )
}
