import { useState, useEffect, useMemo, useCallback } from "react"
import { useAuth } from "@/context/AuthContext"
import { useData } from "@/context/DataContext"
import { hasButtonPermission } from "@/permissions"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import SearchInput from "@/components/SearchInput"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Database, Trash2, RefreshCw, Package, Brain, History, Truck,
  MapPin, ExternalLink, Loader2, Power, PowerOff, FileText,
} from "lucide-react"
import { toast } from "sonner"

const TABS = [
  { id: "orders", label: "รายการออเดอร์", icon: Package },
  { id: "memories", label: "พิกัดจดจำลูกค้า", icon: Brain },
  { id: "history", label: "ประวัติการจัดคิวรถ", icon: History },
  { id: "vehicles", label: "ข้อมูลรถขนส่ง", icon: Truck },
]

const SCORE_FILTERS = [
  { id: "ALL", label: "ทั้งหมด" },
  { id: "HIGH", label: "แม่นยำสูง (>=90%)" },
  { id: "MID", label: "ปานกลาง (70-89%)" },
  { id: "LOW", label: "คลาดเคลื่อน (<70%)" },
]

const SEARCH_PLACEHOLDER = {
  orders: "ค้นหาชื่อลูกค้า, ที่อยู่, เลขที่ SO หรือโซน...",
  memories: "ค้นหาชื่อลูกค้าหรือที่อยู่ในความจำถาวร...",
  history: "ค้นหาเลขที่แผน, วันที่ หรือคลังสินค้า...",
  vehicles: "ค้นหาชื่อคันรถ, ทะเบียน หรือพนักงานขับรถ...",
}

const ENDPOINTS = {
  orders: "/api/v1/orders-history?limit=200",
  memories: "/api/v1/customer-locations?limit=200",
  history: "/api/v1/history?limit=100",
  vehicles: "/api/v1/vehicles",
}

function scoreVariant(score, isVerified) {
  if (isVerified || score >= 90) return "success"
  if (score >= 70) return "warning"
  return "danger"
}

function EmptyRow({ colSpan, icon: Icon, message }) {
  return (
    <TableRow className="hover:bg-transparent">
      <TableCell colSpan={colSpan} className="h-32 text-center">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Icon className="h-9 w-9 opacity-40" />
          <p className="text-sm">{message}</p>
        </div>
      </TableCell>
    </TableRow>
  )
}

function DatabaseViewer({ onClearData }) {
  const { user } = useAuth()
  const { clearAllData } = useData() || {}
  const role = user?.role

  const canDeleteMemory = hasButtonPermission(role, "clear_data")
  const canDeleteVehicle = hasButtonPermission(role, "delete_vehicle")
  const canManageVehicles = hasButtonPermission(role, "manage_vehicles")
  const canClearData = hasButtonPermission(role, "clear_data")

  const [activeTab, setActiveTab] = useState("orders")
  const [orders, setOrders] = useState([])
  const [memories, setMemories] = useState([])
  const [history, setHistory] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [scoreFilter, setScoreFilter] = useState("ALL")
  const [confirm, setConfirm] = useState(null)

  const fetchData = useCallback(async (tab) => {
    setLoading(true)
    try {
      const res = await fetch(ENDPOINTS[tab])
      if (!res.ok) throw new Error("fetch failed")
      const data = await res.json()
      if (tab === "orders") setOrders(data.orders || [])
      else if (tab === "memories") setMemories(data.locations || [])
      else if (tab === "history") setHistory(data.history || [])
      else if (tab === "vehicles") setVehicles(data.vehicles || [])
    } catch (err) {
      console.error("Fetch database data error:", err)
      toast.error("ไม่สามารถดึงข้อมูลจากฐานข้อมูลได้")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData(activeTab)
  }, [activeTab, fetchData])

  const handleTabChange = (value) => {
    setActiveTab(value)
    setSearchQuery("")
    setScoreFilter("ALL")
  }

  const deleteMemory = async (item) => {
    try {
      const res = await fetch(`/api/v1/customer-locations/${item.id}`, { method: "DELETE" })
      if (!res.ok) throw new Error("delete failed")
      setMemories((prev) => prev.filter((m) => m.id !== item.id))
      toast.success("ลบพิกัดความจำเรียบร้อยแล้ว")
    } catch (err) {
      console.error("Delete memory error:", err)
      toast.error("เกิดข้อผิดพลาดในการลบพิกัดความจำ")
    }
  }

  const deleteVehicle = async (item) => {
    try {
      const res = await fetch(`/api/v1/vehicles/${item.id}`, { method: "DELETE" })
      if (!res.ok) throw new Error("delete failed")
      const data = await res.json()
      setVehicles(data.vehicles || [])
      toast.success("ลบรถออกจากฐานข้อมูลเรียบร้อยแล้ว")
    } catch (err) {
      console.error("Failed to delete vehicle:", err)
      toast.error("ไม่สามารถลบรถได้ กรุณาลองใหม่")
    }
  }

  const handleClearAll = async () => {
    try {
      if (onClearData) await onClearData()
      else if (clearAllData) await clearAllData()
      await fetchData(activeTab)
      toast.success("ล้างข้อมูลทั้งหมดเรียบร้อยแล้ว")
    } catch (err) {
      console.error("Clear data error:", err)
      toast.error("ไม่สามารถล้างข้อมูลได้")
    }
  }

  const handleToggleVehicleActive = async (vehicle) => {
    const previous = vehicles
    const updated = vehicles.map((v) => (v.id === vehicle.id ? { ...v, active: !v.active } : v))
    setVehicles(updated)
    try {
      const res = await fetch("/api/v1/vehicles", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      })
      if (!res.ok) throw new Error("update failed")
      toast.success(vehicle.active ? "ปิดใช้งานรถเรียบร้อยแล้ว" : "เปิดใช้งานรถเรียบร้อยแล้ว")
    } catch (err) {
      console.error("Failed to toggle vehicle status:", err)
      setVehicles(previous)
      toast.error("ไม่สามารถเปลี่ยนสถานะรถได้")
    }
  }

  const confirmDelete = () => {
    if (!confirm) return
    const { kind, item } = confirm
    if (kind === "memory") deleteMemory(item)
    else if (kind === "vehicle") deleteVehicle(item)
    else if (kind === "clear") handleClearAll()
    setConfirm(null)
  }

  const query = searchQuery.toLowerCase().trim()

  const filteredOrders = useMemo(() => orders.filter((o) => {
    const matchesSearch = !query || [o.customer, o.address, o.order_number, o.zone]
      .some((f) => (f || "").toLowerCase().includes(query))
    const score = o.confidence_score !== undefined ? o.confidence_score : 50.0
    let matchesScore = true
    if (scoreFilter === "HIGH") matchesScore = score >= 90 || o.is_verified
    else if (scoreFilter === "MID") matchesScore = score >= 70 && score < 90 && !o.is_verified
    else if (scoreFilter === "LOW") matchesScore = score < 70 && !o.is_verified
    return matchesSearch && matchesScore
  }), [orders, query, scoreFilter])

  const filteredMemories = useMemo(() => memories.filter((m) => !query
    || [m.customer_key, m.formatted_address].some((f) => (f || "").toLowerCase().includes(query))
  ), [memories, query])

  const filteredHistory = useMemo(() => history.filter((h) => !query
    || [String(h.id ?? ""), h.plan_date, h.depot_address].some((f) => (f || "").toLowerCase().includes(query))
  ), [history, query])

  const filteredVehicles = useMemo(() => vehicles.filter((v) => !query
    || [v.name, v.plate, v.driver].some((f) => (f || "").toLowerCase().includes(query))
  ), [vehicles, query])

  const stats = [
    { label: "ออเดอร์ในฐานข้อมูล", value: orders.length, unit: "รายการ", icon: Package, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "พิกัดจดจำถาวร (100%)", value: memories.length, unit: "พิกัด", icon: Brain, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "แผนจัดคิวรถย้อนหลัง", value: history.length, unit: "รอบ", icon: History, color: "text-indigo-600", bg: "bg-indigo-50" },
    { label: "รถขนส่งในระบบ", value: vehicles.length, unit: "คัน", icon: Truck, color: "text-sky-600", bg: "bg-sky-50" },
  ]

  const confirmCopy = {
    memory: {
      title: "ยืนยันการลบพิกัดความจำ",
      description: `คุณต้องการลบพิกัดความจำของ "${confirm?.item?.customer_key || ""}" ใช่หรือไม่? ระบบจะต้องค้นหาพิกัดใหม่ในครั้งถัดไป`,
    },
    vehicle: {
      title: "ยืนยันการลบรถขนส่ง",
      description: `คุณต้องการลบ "${confirm?.item?.name || confirm?.item?.plate || ""}" ออกจากฐานข้อมูลใช่หรือไม่? การกระทำนี้ไม่สามารถย้อนกลับได้`,
    },
    clear: {
      title: "ยืนยันการล้างข้อมูลทั้งหมด",
      description: "ระบบจะล้างข้อมูลออเดอร์ แผนจัดส่ง และ fleet ทั้งหมดในฐานข้อมูล การกระทำนี้ไม่สามารถย้อนกลับได้",
    },
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
            <Database className="h-6 w-6 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">คลังจัดการข้อมูล (Database Viewer)</h1>
            <p className="text-sm text-muted-foreground">
              เรียกดู ค้นหา ตรวจสอบ และบริหารจัดการข้อมูลออเดอร์ พิกัดจดจำถาวร และประวัติการจัดคิวรถ
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => fetchData(activeTab)} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            รีเฟรชข้อมูล
          </Button>
          {canClearData && (
            <Button variant="destructive" onClick={() => setConfirm({ kind: "clear" })}>
              <Trash2 className="h-4 w-4" />
              ล้างข้อมูลทั้งหมด
            </Button>
          )}
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => {
          const Icon = s.icon
          return (
            <Card key={s.label}>
              <CardContent className="flex items-center gap-4 p-6">
                <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl", s.bg)}>
                  <Icon className={cn("h-6 w-6", s.color)} />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {s.value} <span className="text-sm font-normal text-muted-foreground">{s.unit}</span>
                  </p>
                  <p className="text-sm text-muted-foreground">{s.label}</p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4">
          {TABS.map((t) => {
            const Icon = t.icon
            return (
              <TabsTrigger
                key={t.id}
                value={t.id}
                className="gap-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{t.label}</span>
              </TabsTrigger>
            )
          })}
        </TabsList>

        {/* Search + Filter */}
        <Card>
          <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
            <SearchInput
              id="db-search"
              wrapperClassName="relative flex-1"
              placeholder={SEARCH_PLACEHOLDER[activeTab]}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {activeTab === "orders" && (
              <div className="flex flex-wrap gap-2">
                {SCORE_FILTERS.map((f) => (
                  <Button
                    key={f.id}
                    size="sm"
                    variant={scoreFilter === f.id ? "default" : "outline"}
                    onClick={() => setScoreFilter(f.id)}
                    className={cn(scoreFilter === f.id && "bg-blue-600 hover:bg-blue-700")}
                  >
                    {f.label}
                  </Button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {loading ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm">กำลังดึงข้อมูลจาก Database...</p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Orders */}
            <TabsContent value="orders" className="mt-0">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">รายการออเดอร์ (Orders Table)</CardTitle>
                  <Badge variant="info">{filteredOrders.length} รายการ</Badge>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="w-full">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-16">#ID</TableHead>
                          <TableHead>เลขที่ SO</TableHead>
                          <TableHead>ชื่อลูกค้า/บริษัท</TableHead>
                          <TableHead>ที่อยู่จัดส่ง</TableHead>
                          <TableHead>โซน</TableHead>
                          <TableHead className="text-right">น้ำหนัก (kg)</TableHead>
                          <TableHead>พิกัด (Lat, Lng)</TableHead>
                          <TableHead>ความแม่นยำ</TableHead>
                          <TableHead className="text-right">จัดการ</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredOrders.length === 0 ? (
                          <EmptyRow colSpan={9} icon={FileText} message="ไม่พบข้อมูลรายการสั่งซื้อตามเงื่อนไข" />
                        ) : (
                          filteredOrders.map((o, idx) => {
                            const score = o.confidence_score !== undefined ? o.confidence_score : 50.0
                            return (
                              <TableRow key={o.id ?? idx}>
                                <TableCell className="font-semibold text-muted-foreground">#{o.id || idx + 1}</TableCell>
                                <TableCell className="font-semibold text-blue-600">{o.order_number || "-"}</TableCell>
                                <TableCell className="font-semibold">{o.customer}</TableCell>
                                <TableCell className="max-w-[280px] truncate text-muted-foreground">{o.address}</TableCell>
                                <TableCell>
                                  <Badge variant="secondary">{o.zone || "ไม่ระบุ"}</Badge>
                                </TableCell>
                                <TableCell className="text-right font-semibold">{o.weight}</TableCell>
                                <TableCell className="font-mono text-xs">
                                  {o.lat && o.lng ? `${o.lat.toFixed(5)}, ${o.lng.toFixed(5)}` : "ไม่มีพิกัด"}
                                </TableCell>
                                <TableCell>
                                  <Badge variant={scoreVariant(score, o.is_verified)}>
                                    {o.is_verified ? "100%" : `${Math.round(score)}%`}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-right">
                                  {o.lat && o.lng && (
                                    <Button variant="ghost" size="sm" asChild>
                                      <a
                                        href={`https://www.google.com/maps/search/?api=1&query=${o.lat},${o.lng}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="text-blue-600"
                                      >
                                        <MapPin className="h-4 w-4" />
                                        ดูบนแผนที่
                                        <ExternalLink className="h-3 w-3" />
                                      </a>
                                    </Button>
                                  )}
                                </TableCell>
                              </TableRow>
                            )
                          })
                        )}
                      </TableBody>
                    </Table>
                    <ScrollBar orientation="horizontal" />
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Customer Locations */}
            <TabsContent value="memories" className="mt-0">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">คลังความจำพิกัดถาวร (Customer Locations)</CardTitle>
                  <Badge variant="success">{filteredMemories.length} พิกัด</Badge>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="w-full">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-16">#ID</TableHead>
                          <TableHead>Customer Key (ชื่อ + ที่อยู่)</TableHead>
                          <TableHead>สถานที่ยืนยัน (Formatted Address)</TableHead>
                          <TableHead>พิกัดยืนยันจริง (Lat, Lng)</TableHead>
                          <TableHead>ความแม่นยำ</TableHead>
                          <TableHead>อัปเดตล่าสุด</TableHead>
                          <TableHead className="text-right">จัดการ</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredMemories.length === 0 ? (
                          <EmptyRow
                            colSpan={7}
                            icon={MapPin}
                            message="ยังไม่มีข้อมูลพิกัดความจำถาวร (เมื่อมีการยืนยันพิกัดหรือลากหมุด ข้อมูลจะมาปรากฏที่นี่อัตโนมัติ)"
                          />
                        ) : (
                          filteredMemories.map((m, idx) => (
                            <TableRow key={m.id ?? idx}>
                              <TableCell className="font-semibold text-muted-foreground">#{m.id}</TableCell>
                              <TableCell className="font-semibold">{m.customer_key}</TableCell>
                              <TableCell className="max-w-[280px] truncate text-muted-foreground">
                                {m.formatted_address || "-"}
                              </TableCell>
                              <TableCell className="font-mono text-xs font-semibold text-emerald-600">
                                {m.lat?.toFixed(6) ?? "-"}, {m.lng?.toFixed(6) ?? "-"}
                              </TableCell>
                              <TableCell>
                                <Badge variant="success">100%</Badge>
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground">{m.updated_at || "-"}</TableCell>
                              <TableCell className="text-right">
                                {canDeleteMemory && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-red-600 hover:bg-red-50 hover:text-red-700"
                                    onClick={() => setConfirm({ kind: "memory", item: m })}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                    ลบความจำ
                                  </Button>
                                )}
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                    <ScrollBar orientation="horizontal" />
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Route History */}
            <TabsContent value="history" className="mt-0">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">ประวัติการจัดคิวรถ (Route History)</CardTitle>
                  <Badge variant="purple">{filteredHistory.length} รอบ</Badge>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="w-full">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>#Plan ID</TableHead>
                          <TableHead>วันที่ประมวลผล</TableHead>
                          <TableHead className="text-right">จำนวนออเดอร์</TableHead>
                          <TableHead className="text-right">จำนวนรถที่ใช้</TableHead>
                          <TableHead>คลังสินค้า (Depot)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredHistory.length === 0 ? (
                          <EmptyRow colSpan={5} icon={History} message="ยังไม่มีประวัติการคำนวณจัดคิวรถ" />
                        ) : (
                          filteredHistory.map((h, idx) => (
                            <TableRow key={h.id ?? idx}>
                              <TableCell className="font-semibold text-indigo-600">#PLAN-{h.id}</TableCell>
                              <TableCell className="font-medium">{h.plan_date || "-"}</TableCell>
                              <TableCell className="text-right font-semibold">{h.total_orders} รายการ</TableCell>
                              <TableCell className="text-right font-semibold text-emerald-600">{h.total_vehicles} คัน</TableCell>
                              <TableCell className="text-muted-foreground">
                                {h.depot_address || "คลังบรมราชชนนี (ตลิ่งชัน)"}
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                    <ScrollBar orientation="horizontal" />
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Vehicles */}
            <TabsContent value="vehicles" className="mt-0">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">ข้อมูลรถขนส่ง (Vehicles Fleet DB)</CardTitle>
                  <Badge variant="info">{filteredVehicles.length} คัน</Badge>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="w-full">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-16">#ID</TableHead>
                          <TableHead>ชื่อคันรถ</TableHead>
                          <TableHead>ทะเบียนรถ</TableHead>
                          <TableHead>พนักงานขับรถ</TableHead>
                          <TableHead className="text-right">ความจุบรรทุกสูงสุด</TableHead>
                          <TableHead>สถานะ</TableHead>
                          <TableHead className="text-right">จัดการข้อมูล</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredVehicles.length === 0 ? (
                          <EmptyRow colSpan={7} icon={Truck} message="ไม่พบข้อมูลรถขนส่งในฐานข้อมูล" />
                        ) : (
                          filteredVehicles.map((v, idx) => (
                            <TableRow key={v.id ?? idx}>
                              <TableCell className="font-semibold text-muted-foreground">#{v.id}</TableCell>
                              <TableCell className="font-semibold">{v.name || `รถคันที่ ${v.id}`}</TableCell>
                              <TableCell className="font-semibold text-blue-600">{v.plate}</TableCell>
                              <TableCell className="text-muted-foreground">{v.driver || "-"}</TableCell>
                              <TableCell className="text-right font-semibold">
                                {v.capacity} kg
                                <span className="ml-1 text-xs font-normal text-muted-foreground">
                                  ({(v.capacity / 1000).toFixed(2)} ตัน)
                                </span>
                              </TableCell>
                              <TableCell>
                                <Badge variant={v.active ? "success" : "danger"}>
                                  {v.active ? "เปิดใช้งาน" : "ปิดใช้งาน"}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center justify-end gap-2">
                                  {canManageVehicles && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleToggleVehicleActive(v)}
                                      title={v.active ? "คลิกเพื่อปิดใช้งาน" : "คลิกเพื่อเปิดใช้งาน"}
                                    >
                                      {v.active ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                                      {v.active ? "ปิดใช้งาน" : "เปิดใช้งาน"}
                                    </Button>
                                  )}
                                  {canDeleteVehicle && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="text-red-600 hover:bg-red-50 hover:text-red-700"
                                      onClick={() => setConfirm({ kind: "vehicle", item: v })}
                                      title="ลบรถคันนี้ออกจากฐานข้อมูล"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                      ลบรถ
                                    </Button>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                    <ScrollBar orientation="horizontal" />
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
          </>
        )}
      </Tabs>

      <AlertDialog open={!!confirm} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirm ? confirmCopy[confirm.kind].title : ""}</AlertDialogTitle>
            <AlertDialogDescription>
              {confirm ? confirmCopy[confirm.kind].description : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>ยกเลิก</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={confirmDelete}
            >
              ยืนยันการลบ
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default DatabaseViewer
