import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useData } from "@/context/DataContext"
import { useAuth } from "@/context/AuthContext"
import PermissionGate from "@/components/PermissionGate"
import MapView from "@/components/MapView"
import ConfirmDialog from "@/components/ConfirmDialog"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Search, X, MapPin, Package, FileText, ShoppingBag, Scale, Trash2,
  Upload, Loader2, AlertTriangle, RotateCcw, Route as RouteIcon, Map as MapIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

const ALL_ZONES = "ALL"

function Orders() {
  const { orders, routes, planRoutes, clearAllData, setLocationVerified } = useData()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [searchQuery, setSearchQuery] = useState("")
  const [selectedZoneFilter, setSelectedZoneFilter] = useState(ALL_ZONES)
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState(null)
  const [confirmClearOpen, setConfirmClearOpen] = useState(false)

  const availableZones = useMemo(
    () => Array.from(new Set(orders.map((o) => o.zone || "ไม่ระบุ").filter(Boolean))),
    [orders]
  )

  const filteredOrders = useMemo(
    () =>
      orders.filter((order) => {
        const q = searchQuery.toLowerCase().trim()
        const matchesSearch =
          !q ||
          (order.customer || "").toLowerCase().includes(q) ||
          (order.address || "").toLowerCase().includes(q) ||
          (order.order_number || "").toLowerCase().includes(q) ||
          (order.zone || "").toLowerCase().includes(q) ||
          (order.products || []).some((p) => (p.name || "").toLowerCase().includes(q))

        const matchesZone = selectedZoneFilter === ALL_ZONES || order.zone === selectedZoneFilter

        return matchesSearch && matchesZone
      }),
    [orders, searchQuery, selectedZoneFilter]
  )

  const totalFilteredWeight = useMemo(
    () => filteredOrders.reduce((sum, o) => sum + (o.weight || 0), 0),
    [filteredOrders]
  )

  const handlePlanRoutes = async () => {
    setPlanning(true)
    setError(null)
    try {
      await planRoutes(orders)
    } catch (err) {
      setError(err.message || "เกิดข้อผิดพลาดในการคำนวณเส้นทาง")
    } finally {
      setPlanning(false)
    }
  }

  const handleClearData = () => {
    setConfirmClearOpen(true)
  }

  const resetFilters = () => {
    setSearchQuery("")
    setSelectedZoneFilter(ALL_ZONES)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            รายการสั่งซื้อ ({orders.length} รายการ)
          </h1>
          <p className="text-sm text-muted-foreground">
            ค้นหา กรองโซน และตรวจสอบรายละเอียดออเดอร์
          </p>
        </div>

        {orders.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <PermissionGate role={user?.role} permission="clear_data">
              <Button variant="outline" onClick={handleClearData} className="border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700">
                <Trash2 className="h-4 w-4" />
                ล้างข้อมูล
              </Button>
            </PermissionGate>
            <Button onClick={handlePlanRoutes} disabled={planning}>
              {planning ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  กำลังคำนวณ...
                </>
              ) : (
                <>
                  <RouteIcon className="h-4 w-4" />
                  คำนวณเส้นทาง
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>เกิดข้อผิดพลาด</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="ghost" size="icon" onClick={() => setError(null)}>
              <X className="h-4 w-4" />
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {orders.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50">
              <Package className="h-8 w-8 text-blue-600" />
            </div>
            <div>
              <p className="text-base font-semibold">ยังไม่มีข้อมูลรายการสั่งซื้อ</p>
              <p className="text-sm text-muted-foreground">กรุณาอัปโหลดไฟล์ PDF ใบสั่งขายเพื่อเริ่มต้นใช้งาน</p>
            </div>
            <Button onClick={() => navigate("/upload")}>
              <Upload className="h-4 w-4" />
              อัปโหลดไฟล์ PDF
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Search & Zone Filter */}
          <Card>
            <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-end">
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="order-search">ค้นหาออเดอร์</Label>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="order-search"
                    type="text"
                    placeholder="ค้นหาชื่อลูกค้า, ที่อยู่จัดส่ง, เลขที่ SO หรือสินค้า..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 pr-9"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      aria-label="ล้างคำค้นหา"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              <div className="w-full space-y-1.5 lg:w-72">
                <Label htmlFor="zone-filter" className="flex items-center gap-1.5">
                  <MapIcon className="h-4 w-4 text-muted-foreground" />
                  โซนพื้นที่
                </Label>
                <Select value={selectedZoneFilter} onValueChange={setSelectedZoneFilter}>
                  <SelectTrigger id="zone-filter">
                    <SelectValue placeholder="เลือกโซนพื้นที่" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_ZONES}>แสดงทุกโซน ({orders.length})</SelectItem>
                    {availableZones.map((zone, zIdx) => {
                      const count = orders.filter((o) => o.zone === zone).length
                      return (
                        <SelectItem key={zIdx} value={zone}>
                          {zone} ({count} รายการ)
                        </SelectItem>
                      )
                    })}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Filter Summary */}
          <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-muted-foreground">
                พบ <strong className="text-foreground">{filteredOrders.length}</strong> จาก {orders.length} ออเดอร์
              </span>
              {selectedZoneFilter !== ALL_ZONES && (
                <Badge variant="info">โซน: {selectedZoneFilter}</Badge>
              )}
              {searchQuery && <Badge variant="secondary">คำค้น: "{searchQuery}"</Badge>}
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Scale className="h-4 w-4" />
              น้ำหนักรวมกลุ่มที่เลือก:
              <strong className="text-foreground">{totalFilteredWeight.toLocaleString()} kg</strong>
            </div>
          </div>

          {filteredOrders.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
                <Search className="h-10 w-10 text-muted-foreground opacity-40" />
                <p className="text-sm text-muted-foreground">
                  ไม่พบรายการสั่งซื้อที่ตรงกับคำค้นหา "{searchQuery}"
                </p>
                <Button variant="secondary" onClick={resetFilters}>
                  <RotateCcw className="h-4 w-4" />
                  ล้างคำค้นหาทั้งหมด
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_1fr]">
              {/* Orders List */}
              <div className="flex max-h-[750px] flex-col gap-3 overflow-y-auto pr-1.5">
                {filteredOrders.map((order, idx) => (
                  <Card key={order.id ?? idx} className="transition-shadow hover:shadow-md">
                    <CardContent className="flex gap-3 p-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50">
                        <Package className="h-5 w-5 text-blue-600" />
                      </div>

                      <div className="min-w-0 flex-1 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="text-sm font-semibold leading-tight">{order.customer}</h4>
                          {order.zone && <Badge variant="secondary">{order.zone}</Badge>}
                        </div>

                        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
                          <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          <span className="break-words">{order.address}</span>
                        </p>

                        {order.order_number && (
                          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <FileText className="h-3.5 w-3.5 shrink-0" />
                            SO: {order.order_number}
                          </p>
                        )}

                        <div className="flex flex-wrap gap-1.5 pt-0.5">
                          {order.products && order.products.length > 0 ? (
                            order.products.map((p, pIdx) => (
                              <Badge key={pIdx} variant="info" className="gap-1 font-medium">
                                <ShoppingBag className="h-3 w-3" />
                                {p.name} ({p.quantity} {p.unit || "ชิ้น"})
                              </Badge>
                            ))
                          ) : (
                            <Badge variant="info" className="gap-1 font-medium">
                              <ShoppingBag className="h-3 w-3" />
                              สินค้าตามใบสั่งซื้อ{" "}
                              {order.order_number
                                ? `(SO: ${order.order_number})`
                                : `(${order.weight || 50} kg)`}
                            </Badge>
                          )}
                        </div>
                      </div>

                      <Badge
                        variant="outline"
                        className={cn("h-fit shrink-0 border-blue-200 bg-blue-50 text-blue-700")}
                      >
                        {order.weight} kg
                      </Badge>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Map */}
              <Card className="overflow-hidden">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <MapPin className="h-5 w-5 text-blue-600" />
                    แผนที่ตำแหน่งลูกค้า
                  </CardTitle>
                  <CardDescription>
                    ตรวจสอบและยืนยันพิกัดจัดส่งของแต่ละออเดอร์ ({filteredOrders.length} จุด)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <MapView
                    orders={filteredOrders}
                    routes={routes}
                    onVerified={setLocationVerified}
                  />
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmClearOpen}
        onOpenChange={setConfirmClearOpen}
        title="รีเซ็ตข้อมูลระบบ"
        description="คุณแน่ใจหรือไม่ว่าต้องการล้างข้อมูลออเดอร์ แผนจัดส่ง และ fleet ทั้งหมด?"
        confirmLabel="ล้างข้อมูลทั้งหมด"
        onConfirm={() => {
          setConfirmClearOpen(false)
          clearAllData()
        }}
      />
    </div>
  )
}

export default Orders
