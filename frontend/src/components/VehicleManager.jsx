import { useEffect, useMemo, useState } from "react"
import axios from "axios"
import { useAuth } from "@/context/AuthContext"
import PermissionGate from "@/components/PermissionGate"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog"
import {
  Truck, Settings, Plus, Trash2, User, Copy, Save, Loader2, Power,
  AlertTriangle, Scale, Package, MapPin, MessageSquare, Ruler,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

const EMPTY_FORM = {
  name: "",
  plate: "",
  driver: "",
  line_user_id: "",
  capacity: 3500,
  max_volume_cbm: "",
  max_boxes: "",
  max_stops: "",
}

const isBlank = (value) => value === "" || value === null || value === undefined

const orEmpty = (value) => (value === null || value === undefined ? "" : value)

const toNumber = (value, parser = parseFloat) => (isBlank(value) ? "" : parser(value))

function VehicleManager() {
  const { user } = useAuth()
  const [vehicles, setVehicles] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState(EMPTY_FORM)
  const [editIndex, setEditIndex] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY_FORM)

  useEffect(() => {
    fetchVehicles()
  }, [])

  const fetchVehicles = async () => {
    setLoading(true)
    try {
      const res = await axios.get("/api/v1/vehicles")
      setVehicles(res.data.vehicles || [])
      setLoadError(null)
    } catch (err) {
      console.error("Failed to load vehicles:", err)
      setLoadError("ไม่สามารถดึงข้อมูลรถขนส่งได้")
      toast.error("ไม่สามารถดึงข้อมูลรถขนส่งได้")
    } finally {
      setLoading(false)
    }
  }

  // Auto-save any fleet mutation straight to the backend
  const persist = async (list, successText) => {
    const previous = vehicles
    setVehicles(list)
    try {
      const res = await axios.put("/api/v1/vehicles", list)
      if (res.data && res.data.vehicles) {
        setVehicles(res.data.vehicles)
      }
      if (successText) toast.success(successText)
      return true
    } catch (err) {
      console.error("Auto-save failed:", err)
      setVehicles(previous) // rollback on failure
      toast.error(`เกิดข้อผิดพลาดในการบันทึกข้อมูลรถ: ${err.message}`)
      return false
    }
  }

  const nextVehicleId = () =>
    (vehicles.length > 0 ? Math.max(...vehicles.map((v) => v.id || 0)) : 0) + 1

  const openAddDialog = () => {
    const newId = nextVehicleId()
    setAddForm({
      ...EMPTY_FORM,
      name: `รถคันที่ ${newId} (รถบรรทุก 3.5 ตัน)`,
      plate: `กข ${1000 + newId}`,
      driver: `พนักงานขับรถ ${newId}`,
      capacity: 3500,
    })
    setAddOpen(true)
  }

  const handleAddVehicle = async (e) => {
    if (e) e.preventDefault()
    const newId = nextVehicleId()
    const newVehicle = {
      ...addForm,
      id: newId,
      name: addForm.name || `รถคันที่ ${newId} (รถบรรทุก 3.5 ตัน)`,
      plate: addForm.plate || `กข ${1000 + newId}`,
      driver: addForm.driver || `พนักงานขับรถ ${newId}`,
      capacity: addForm.capacity === "" ? 0 : addForm.capacity,
      active: true,
    }
    setAddOpen(false)
    await persist([...vehicles, newVehicle], `เพิ่ม "${newVehicle.name}" ลงฐานข้อมูลเรียบร้อยแล้ว`)
  }

  const openEditDialog = (index) => {
    const v = vehicles[index]
    setEditIndex(index)
    setEditForm({
      name: v.name || "",
      plate: v.plate || "",
      driver: v.driver || "",
      line_user_id: v.line_user_id || "",
      capacity: orEmpty(v.capacity),
      max_volume_cbm: orEmpty(v.max_volume_cbm),
      max_boxes: orEmpty(v.max_boxes),
      max_stops: orEmpty(v.max_stops),
    })
  }

  const handleEditSubmit = async (e) => {
    if (e) e.preventDefault()
    if (editIndex === null) return
    const updated = vehicles.map((v, idx) => (idx === editIndex ? { ...v, ...editForm } : v))
    const targetName = editForm.name || `คันที่ ${editIndex + 1}`
    setEditIndex(null)
    await persist(updated, `บันทึกข้อมูล "${targetName}" ลงฐานข้อมูลเรียบร้อยแล้ว`)
  }

  const handleDuplicateVehicle = async (index) => {
    const target = vehicles[index]
    const duplicated = {
      ...target,
      id: nextVehicleId(),
      name: `${target.name || "รถขนส่ง"} (สำเนา)`,
      plate: `${target.plate || "กข 0000"}`,
      active: true,
    }
    const copyList = [...vehicles]
    copyList.splice(index + 1, 0, duplicated)
    await persist(copyList, "สำเนารถและบันทึกลงฐานข้อมูลเรียบร้อยแล้ว")
  }

  const handleToggleActive = async (index) => {
    const updated = vehicles.map((v, idx) => (idx === index ? { ...v, active: !v.active } : v))
    const target = updated[index]
    await persist(
      updated,
      `อัปเดตสถานะ "${target.name}" เป็น ${target.active ? "เปิดใช้งาน" : "ปิดใช้งาน"} ในฐานข้อมูลเรียบร้อยแล้ว`
    )
  }

  const handleDeleteVehicle = async (index) => {
    if (vehicles.length <= 1) {
      toast.error("ระบบต้องมีรถขนส่งอย่างน้อย 1 คัน")
      return
    }
    const targetName = vehicles[index].name || `คันที่ ${index + 1}`
    const filtered = vehicles.filter((_, idx) => idx !== index)
    await persist(filtered, `ลบ "${targetName}" ออกจากฐานข้อมูลเรียบร้อยแล้ว`)
  }

  const handleSave = async (e) => {
    if (e) e.preventDefault()
    setSaving(true)
    try {
      await axios.put("/api/v1/vehicles", vehicles)
      toast.success("บันทึก Fleet รถขนส่งเรียบร้อยแล้ว")
    } catch (err) {
      console.error("Failed to save vehicles:", err)
      toast.error("เกิดข้อผิดพลาดในการบันทึกข้อมูลรถ")
    } finally {
      setSaving(false)
    }
  }

  const maxCapacity = useMemo(
    () => Math.max(1, ...vehicles.map((v) => Number(v.capacity) || 0)),
    [vehicles]
  )

  const totalCapacityTons = useMemo(
    () => (vehicles.reduce((sum, v) => sum + (Number(v.capacity) || 0), 0) / 1000).toFixed(2),
    [vehicles]
  )

  const activeCount = vehicles.filter((v) => v.active !== false).length

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-72" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-64 w-full rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Truck className="h-6 w-6 text-blue-600" />
            จัดการข้อมูล Fleet รถขนส่ง ({vehicles.length} คัน)
          </h1>
          <p className="text-sm text-muted-foreground">
            เพิ่ม/ลบรถ ตั้งค่าชื่อคนขับ ทะเบียนรถ น้ำหนักบรรทุกสูงสุด โดยลำดับคันจะเรียงเป็น 1, 2, 3, 4... อัตโนมัติ
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">เปิดใช้งาน {activeCount} คัน</Badge>
          <Badge variant="secondary">รวม {totalCapacityTons} ตัน</Badge>
          <PermissionGate role={user?.role} permission="manage_vehicles">
            <Button variant="secondary" onClick={openAddDialog}>
              <Plus className="h-4 w-4" />
              เพิ่มรถคันใหม่
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  กำลังบันทึก...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  บันทึกการเปลี่ยนแปลง
                </>
              )}
            </Button>
          </PermissionGate>
        </div>
      </div>

      {loadError && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>เกิดข้อผิดพลาด</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
      )}

      {vehicles.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50">
              <Truck className="h-8 w-8 text-blue-600" />
            </div>
            <div>
              <p className="text-base font-semibold">ยังไม่มีข้อมูลรถขนส่ง</p>
              <p className="text-sm text-muted-foreground">
                กดปุ่ม "เพิ่มรถคันใหม่" เพื่อเพิ่มรถบรรทุกเข้าสู่ Fleet จัดส่ง
              </p>
            </div>
            <PermissionGate role={user?.role} permission="manage_vehicles">
              <Button onClick={openAddDialog}>
                <Plus className="h-4 w-4" />
                เพิ่มรถคันใหม่
              </Button>
            </PermissionGate>
          </CardContent>
        </Card>
      )}

      {/* Vehicle Cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {vehicles.map((v, idx) => {
          const isActive = v.active !== false
          const capacityKg = Number(v.capacity) || 0
          const capacityPct = Math.min(100, Math.round((capacityKg / maxCapacity) * 100))
          const barColor =
            capacityPct >= 80 ? "bg-blue-600" : capacityPct >= 50 ? "bg-blue-500" : "bg-blue-400"

          return (
            <Card
              key={v.id || idx}
              className={cn("flex flex-col transition-shadow hover:shadow-md", !isActive && "opacity-60")}
            >
              <CardHeader className="gap-2 pb-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="default">คันที่ {idx + 1}</Badge>
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        isActive ? "bg-emerald-500" : "bg-slate-300"
                      )}
                      aria-hidden="true"
                    />
                    <Badge variant={isActive ? "success" : "secondary"}>
                      {isActive ? "เปิดใช้งานอยู่" : "ปิดใช้งานอยู่"}
                    </Badge>
                  </div>
                  <PermissionGate role={user?.role} permission="manage_vehicles">
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleToggleActive(idx)}
                        title="คลิกเพื่อเปิดหรือปิดใช้งานรถคันนี้"
                      >
                        <Power className={cn("h-4 w-4", isActive ? "text-emerald-600" : "text-muted-foreground")} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDuplicateVehicle(idx)}
                        title="คัดลอกรถคันนี้"
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(idx)}
                        title="แก้ไขข้อมูลรถคันนี้"
                      >
                        <Settings className="h-4 w-4" />
                      </Button>
                      <PermissionGate role={user?.role} permission="delete_vehicle">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteVehicle(idx)}
                          title="ลบรถคันนี้ออกจากระบบ"
                          className="text-red-600 hover:bg-red-50 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </PermissionGate>
                    </div>
                  </PermissionGate>
                </div>

                <CardTitle className="text-base leading-snug">{v.name || "รถขนส่ง"}</CardTitle>
                <CardDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="inline-flex items-center gap-1.5">
                    <Truck className="h-3.5 w-3.5" />
                    {v.plate || "ยังไม่ระบุทะเบียน"}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <User className="h-3.5 w-3.5" />
                    {v.driver || "ยังไม่ระบุคนขับ"}
                  </span>
                </CardDescription>
              </CardHeader>

              <CardContent className="flex flex-1 flex-col gap-4">
                {/* Capacity */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="inline-flex items-center gap-1.5 font-medium">
                      <Scale className="h-4 w-4 text-muted-foreground" />
                      น้ำหนักบรรทุกสูงสุด
                    </span>
                    <span className="text-muted-foreground">
                      {capacityKg.toLocaleString()} kg ({(capacityKg / 1000).toFixed(2)} ตัน)
                    </span>
                  </div>
                  <Progress value={capacityPct} indicatorClassName={barColor} />
                </div>

                {/* Limits */}
                <div className="grid grid-cols-3 gap-2 border-t pt-3 text-center">
                  <div>
                    <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
                      <Ruler className="h-3.5 w-3.5" />
                      ปริมาตร
                    </p>
                    <p className="text-sm font-semibold">
                      {v.max_volume_cbm ? `${v.max_volume_cbm} CBM` : "ไม่จำกัด"}
                    </p>
                  </div>
                  <div>
                    <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
                      <Package className="h-3.5 w-3.5" />
                      กล่อง
                    </p>
                    <p className="text-sm font-semibold">{v.max_boxes ? v.max_boxes : "ไม่จำกัด"}</p>
                  </div>
                  <div>
                    <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5" />
                      จุดส่ง
                    </p>
                    <p className="text-sm font-semibold">{v.max_stops ? v.max_stops : "ไม่จำกัด"}</p>
                  </div>
                </div>

                <div className="mt-auto flex items-center gap-1.5 border-t pt-3 text-xs text-muted-foreground">
                  <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">
                    LINE: {v.line_user_id ? v.line_user_id : "ยังไม่ได้ตั้งค่า LINE User ID"}
                  </span>
                </div>

                <PermissionGate role={user?.role} permission="manage_vehicles">
                  <Button variant="outline" className="w-full" onClick={() => openEditDialog(idx)}>
                    <Settings className="h-4 w-4" />
                    แก้ไขข้อมูลรถ
                  </Button>
                </PermissionGate>
              </CardContent>
            </Card>
          )
        })}

        {/* Add Vehicle Card */}
        <PermissionGate role={user?.role} permission="manage_vehicles">
          <button
            type="button"
            onClick={openAddDialog}
            className="flex min-h-52 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-blue-200 bg-blue-50/40 p-6 text-center transition-colors hover:border-blue-400 hover:bg-blue-50"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100">
              <Plus className="h-6 w-6 text-blue-600" />
            </div>
            <span className="text-sm font-semibold text-blue-700">เพิ่มรถขนส่งคันใหม่</span>
            <span className="text-xs text-muted-foreground">
              คลิกเพื่อเพิ่มรถบรรทุกใหม่เข้าสู่ Fleet จัดส่ง
            </span>
          </button>
        </PermissionGate>
      </div>

      {/* Add Vehicle Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-blue-600" />
              เพิ่มรถขนส่งคันใหม่
            </DialogTitle>
            <DialogDescription>
              กรอกข้อมูลรถบรรทุกที่ต้องการเพิ่มเข้าสู่ Fleet ระบบจะบันทึกลงฐานข้อมูลอัตโนมัติ
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddVehicle}>
            <VehicleFormFields form={addForm} setForm={setAddForm} idPrefix="add" />
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>
                ยกเลิก
              </Button>
              <Button type="submit">
                <Plus className="h-4 w-4" />
                เพิ่มรถและบันทึก
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Vehicle Dialog */}
      <Dialog open={editIndex !== null} onOpenChange={(open) => !open && setEditIndex(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-blue-600" />
              แก้ไขข้อมูลรถ {editIndex !== null ? `คันที่ ${editIndex + 1}` : ""}
            </DialogTitle>
            <DialogDescription>
              ปรับปรุงชื่อเรียก ทะเบียนรถ คนขับ และข้อจำกัดการบรรทุก ระบบจะบันทึกลงฐานข้อมูลอัตโนมัติ
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEditSubmit}>
            <VehicleFormFields form={editForm} setForm={setEditForm} idPrefix="edit" />
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" onClick={() => setEditIndex(null)}>
                ยกเลิก
              </Button>
              <Button type="submit">
                <Save className="h-4 w-4" />
                บันทึกข้อมูลรถ
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function VehicleFormFields({ form, setForm, idPrefix }) {
  const update = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-name`}>ชื่อเรียก / ชนิดรถ</Label>
        <Input
          id={`${idPrefix}-name`}
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
          placeholder="เช่น รถใหญ่ 3.75 ตัน"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-plate`}>ทะเบียนรถ</Label>
          <Input
            id={`${idPrefix}-plate`}
            value={form.plate}
            onChange={(e) => update("plate", e.target.value)}
            placeholder="เช่น กข 1234"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-driver`} className="flex items-center gap-1.5">
            <User className="h-4 w-4 text-muted-foreground" />
            พนักงานขับรถ
          </Label>
          <Input
            id={`${idPrefix}-driver`}
            value={form.driver}
            onChange={(e) => update("driver", e.target.value)}
            placeholder="เช่น สมชาย"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-line`}>LINE User ID (สำหรับส่งลิงค์แมพเข้า LINE)</Label>
        <Input
          id={`${idPrefix}-line`}
          value={form.line_user_id}
          onChange={(e) => update("line_user_id", e.target.value)}
          placeholder="เช่น U4a5b6c7d8... (คัดลอกจาก LINE Developers)"
        />
        <p className="text-xs text-muted-foreground">
          คนขับต้อง add LINE OA นี้เป็นเพื่อนก่อน จึงจะรับข้อความได้
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-capacity`}>น้ำหนักบรรทุกสูงสุด (กิโลกรัม / kg)</Label>
        <Input
          id={`${idPrefix}-capacity`}
          type="number"
          min="0"
          value={form.capacity}
          onChange={(e) => update("capacity", toNumber(e.target.value))}
          placeholder="3750"
        />
        <p className="text-xs text-muted-foreground">
          = {(((form.capacity === "" ? 0 : form.capacity) || 0) / 1000).toFixed(2)} ตัน
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-volume`}>ปริมาตรสูงสุด (ลบ.ม. / CBM)</Label>
          <Input
            id={`${idPrefix}-volume`}
            type="number"
            step="0.1"
            min="0"
            value={form.max_volume_cbm}
            onChange={(e) => update("max_volume_cbm", toNumber(e.target.value))}
            placeholder="0"
          />
          <p className="text-xs text-muted-foreground">0 = ไม่จำกัด</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-boxes`}>จำนวนกล่องสูงสุด</Label>
          <Input
            id={`${idPrefix}-boxes`}
            type="number"
            min="0"
            value={form.max_boxes}
            onChange={(e) => update("max_boxes", toNumber(e.target.value, parseInt))}
            placeholder="0"
          />
          <p className="text-xs text-muted-foreground">0 = ไม่จำกัด</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-stops`}>จำนวนจุดส่งสูงสุด</Label>
          <Input
            id={`${idPrefix}-stops`}
            type="number"
            min="0"
            value={form.max_stops}
            onChange={(e) => update("max_stops", toNumber(e.target.value, parseInt))}
            placeholder="0"
          />
          <p className="text-xs text-muted-foreground">0 = ไม่จำกัด</p>
        </div>
      </div>
    </div>
  )
}

export default VehicleManager
