import { useState, useEffect, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { useData } from "@/context/DataContext"
import { useAuth } from "@/context/AuthContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import PermissionGate from "@/components/PermissionGate"
import NotificationPanel from "@/components/NotificationPanel"
import ConfirmDialog from "@/components/ConfirmDialog"
import {
  Package, Truck, MapPin, Scale, Upload, FileText, Settings,
  Smartphone, Scale as ScaleIcon, Trash2, AlertCircle
} from "lucide-react"
import { toast } from "sonner"
import { DELIVERY_STATUS_CONFIG } from "@/constants"

const QUICK_ACTIONS = [
  { id: 'upload', label: 'อัปโหลดไฟล์ PDF ใบสั่งขาย', desc: 'รองรับ Express PDF หลายไฟล์พร้อมกัน', icon: Upload, color: 'bg-blue-500' },
  { id: 'orders', label: 'ตรวจสอบรายการสั่งซื้อ', desc: 'ดูรายการสินค้า น้ำหนัก และตำแหน่งลูกค้า', icon: FileText, color: 'bg-emerald-500' },
  { id: 'vehicles', label: 'จัดการ fleet รถขนส่ง', desc: 'ปรับเปลี่ยนทะเบียนคนขับ ความจุสูงสุด', icon: Settings, color: 'bg-amber-500' },
  { id: 'driver', label: 'Driver Mobile', desc: 'อัปเดตสถานะจัดส่งแบบ real-time', icon: Smartphone, color: 'bg-sky-500' },
  { id: 'load-balance', label: 'Load Balancing', desc: 'วิเคราะห์และกระจายภาระระหว่างรถ', icon: ScaleIcon, color: 'bg-purple-500' },
]

function Dashboard() {
  const { orders, routes, clearAllData, fetchTodayData } = useData()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [sysStatus, setSysStatus] = useState(null)
  const [deliveryDashboard, setDeliveryDashboard] = useState(null)
  const [confirmClearOpen, setConfirmClearOpen] = useState(false)

  useEffect(() => {
    fetchSystemStatus()
    fetchDeliveryDashboard()
    fetchTodayData()
    const interval = setInterval(fetchDeliveryDashboard, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch('/api/v1/system-status')
      if (res.ok) setSysStatus(await res.json())
    } catch { /* ignore */ }
  }

  const fetchDeliveryDashboard = async () => {
    try {
      const res = await fetch('/api/v1/delivery/dashboard')
      if (res.ok) setDeliveryDashboard(await res.json())
    } catch { /* ignore */ }
  }

  const totalWeightKg = orders.reduce((sum, o) => sum + (parseFloat(o.weight) || 0), 0)
  const totalWeightTons = (totalWeightKg / 1000).toFixed(2)
  const totalStops = routes.reduce((sum, r) => sum + (r.stops?.length || 0), 0)

  const zoneCounts = useMemo(() => {
    const counts = {}
    orders.forEach((o) => {
      const zone = o.zone || 'ไม่ระบุ'
      counts[zone] = (counts[zone] || 0) + 1
    })
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5)
  }, [orders])

  const stats = [
    { label: 'ออเดอร์ทั้งหมด', value: orders.length, unit: 'รายการ', icon: Package, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'รถที่จัดคิวแล้ว', value: routes.length, unit: 'คัน', icon: Truck, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'จุดจัดส่ง', value: totalStops || orders.length, unit: 'จุด', icon: MapPin, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'น้ำหนักรวม', value: totalWeightTons, unit: 'ตัน', icon: Scale, color: 'text-purple-600', bg: 'bg-purple-50' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">แดชบอร์ด</h1>
          <p className="text-sm text-muted-foreground">
            ระบบบริหารจัดการขนส่งและวางแผนเส้นทาง
          </p>
        </div>
        <div className="flex items-center gap-3">
          <NotificationPanel />
          <Badge variant={sysStatus?.google_maps_api === 'active' ? 'success' : 'warning'}>
            {sysStatus?.google_maps_api === 'active' ? 'Google Maps API: Active' : 'Smart Geocoding: Active'}
          </Badge>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => {
          const Icon = s.icon
          return (
            <Card
              key={s.label}
              className="cursor-pointer transition-shadow hover:shadow-md"
              onClick={() => navigate(s.label.includes('ออเดอร์') ? '/orders' : s.label.includes('รถ') ? '/routes' : '/orders')}
            >
              <CardContent className="flex items-center gap-4 p-6">
                <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${s.bg}`}>
                  <Icon className={`h-6 w-6 ${s.color}`} />
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

      {/* Zone + Fleet */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">การกระจายจุดส่งตามโซน</CardTitle>
            <Badge variant="secondary">{Object.keys(zoneCounts).length} โซน</Badge>
          </CardHeader>
          <CardContent>
            {zoneCounts.length > 0 ? (
              <div className="space-y-4">
                {zoneCounts.map(([zone, count], idx) => {
                  const percent = Math.round((count / orders.length) * 100)
                  const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-purple-500', 'bg-sky-500']
                  return (
                    <div key={idx} className="space-y-1.5">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium">{zone}</span>
                        <span className="text-muted-foreground">{count} ออเดอร์ ({percent}%)</span>
                      </div>
                      <Progress value={percent} indicatorClassName={colors[idx % colors.length]} />
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
                <MapPin className="h-10 w-10 opacity-40" />
                <p className="text-sm">ยังไม่มีข้อมูลโซน — อัปโหลดไฟล์ PDF เพื่อเริ่มวิเคราะห์</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">สถานะการจัดคิวรถ</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate('/vehicles')}>
              <Settings className="h-4 w-4" />
              จัดการรถ
            </Button>
          </CardHeader>
          <CardContent>
            {routes.length > 0 ? (
              <div className="space-y-4">
                {routes.map((route, idx) => {
                  const maxCap = route.capacity || 3750
                  const loadPct = Math.round((route.total_weight / maxCap) * 100)
                  const barColor = loadPct > 90 ? 'bg-red-500' : loadPct > 70 ? 'bg-amber-500' : 'bg-emerald-500'
                  return (
                    <div key={idx} className="space-y-1.5">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium">{route.name || `คันที่ ${route.vehicle_id}`}</span>
                        <span className="text-muted-foreground">
                          {route.total_weight} / {maxCap} kg ({loadPct}%)
                        </span>
                      </div>
                      <Progress value={loadPct} indicatorClassName={barColor} />
                      <p className="text-xs text-muted-foreground">
                        คนขับ: {route.driver || 'ไม่ระบุ'} · {route.stops?.length || 0} จุดส่ง
                      </p>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
                <Truck className="h-10 w-10 opacity-40" />
                <p className="text-sm">ยังไม่ได้จัดเส้นทาง — คลิก "คำนวณเส้นทาง" เพื่อจัดสรรคิวรถ</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">ทางลัดการใช้งาน</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon
              return (
                <button
                  key={action.id}
                  onClick={() => navigate(`/${action.id}`)}
                  className="flex items-start gap-3 rounded-lg border p-4 text-left transition-colors hover:bg-accent"
                >
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${action.color} text-white`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">{action.label}</p>
                    <p className="text-xs text-muted-foreground">{action.desc}</p>
                  </div>
                </button>
              )
            })}
            <PermissionGate role={user?.role} permission="clear_data">
              <button
                onClick={() => setConfirmClearOpen(true)}
                className="flex items-start gap-3 rounded-lg border border-red-200 p-4 text-left transition-colors hover:bg-red-50"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-red-500 text-white">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-red-600">รีเซ็ตข้อมูลระบบ</p>
                  <p className="text-xs text-muted-foreground">ล้างข้อมูลออเดอร์ แผนจัดส่ง และ fleet</p>
                </div>
              </button>
            </PermissionGate>
          </div>
        </CardContent>
      </Card>

      {/* Delivery Status */}
      {deliveryDashboard?.has_plan && deliveryDashboard.summary && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">สถานะการจัดส่งวันนี้</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate('/driver')}>
              <Smartphone className="h-4 w-4" />
              Driver Mobile
            </Button>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {Object.entries({
                delivered: 'delivered',
                in_transit: 'in_transit',
                arrived: 'arrived',
                pending: 'pending',
                failed: 'failed',
                partial: 'partial',
              }).map(([key, statusKey]) => {
                const cfg = DELIVERY_STATUS_CONFIG[statusKey.toUpperCase()] || DELIVERY_STATUS_CONFIG.PENDING
                const count = deliveryDashboard.summary[key] || 0
                return (
                  <div
                    key={key}
                    className="rounded-lg border p-3 text-center"
                    style={{ backgroundColor: `${cfg.color}12`, borderColor: `${cfg.color}30` }}
                  >
                    <p className="text-2xl font-bold" style={{ color: cfg.color }}>{count}</p>
                    <p className="text-xs font-medium" style={{ color: cfg.color }}>{cfg.label}</p>
                  </div>
                )
              })}
            </div>
            <div className="mt-4 space-y-1.5">
              <Progress value={deliveryDashboard.summary.completion_pct || 0} indicatorClassName="bg-emerald-500" />
              <p className="text-center text-sm font-medium text-muted-foreground">
                {deliveryDashboard.summary.completion_pct || 0}% เสร็จสิ้น
              </p>
            </div>
          </CardContent>
        </Card>
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

export default Dashboard
