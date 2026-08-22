import { useState, useEffect, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Truck, MapPin, Package, Scale, Navigation, Camera, CheckCircle2, XCircle,
  AlertTriangle, LogOut, ArrowLeft, Search, Loader2, ClipboardList, RefreshCw,
  Crosshair, Clock, Home,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { DELIVERY_STATUS_CONFIG } from "@/constants"

const FAILURE_REASONS = [
  'ไม่มีคนรับ',
  'ที่อยู่ผิด',
  'สินค้าเสียหาย',
  'ลูกค้าเลื่อนนัด',
  'ร้านปิด',
  'อื่นๆ',
]

const FILTERS = ['ALL', 'PENDING', 'IN_TRANSIT', 'ARRIVED', 'DELIVERED', 'FAILED']

// สถานะถัดไปที่ทำได้ในแต่ละขั้น (PENDING -> IN_TRANSIT -> ARRIVED -> DELIVERED/FAILED/PARTIAL)
const NEXT_ACTIONS = {
  PENDING: [
    { next: 'IN_TRANSIT', label: 'เริ่มขนส่ง', icon: Truck, variant: 'default' },
  ],
  IN_TRANSIT: [
    { next: 'ARRIVED', label: 'ถึงจุดส่งแล้ว', icon: MapPin, variant: 'warning' },
  ],
  ARRIVED: [
    { next: 'DELIVERED', label: 'ส่งสำเร็จ', icon: CheckCircle2, variant: 'success' },
    { next: 'PARTIAL', label: 'ส่งบางส่วน', icon: AlertTriangle, variant: 'warning', modal: 'partial' },
    { next: 'FAILED', label: 'ส่งไม่สำเร็จ', icon: XCircle, variant: 'destructive', modal: 'failure' },
  ],
  PARTIAL: [
    { next: 'DELIVERED', label: 'ส่งสำเร็จ (ครบแล้ว)', icon: CheckCircle2, variant: 'success' },
    { next: 'FAILED', label: 'ส่งไม่สำเร็จ', icon: XCircle, variant: 'destructive', modal: 'failure' },
  ],
}

function statusOf(stop) {
  return stop?.delivery_status || 'PENDING'
}

function cfgOf(status) {
  return DELIVERY_STATUS_CONFIG[status] || DELIVERY_STATUS_CONFIG.PENDING
}

export default function DriverMobile() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [driverName, setDriverName] = useState('')
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [route, setRoute] = useState(null)
  const [selectedStop, setSelectedStop] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showFailureModal, setShowFailureModal] = useState(false)
  const [failureReason, setFailureReason] = useState('')
  const [partialQty, setPartialQty] = useState(0)
  const [showPartialModal, setShowPartialModal] = useState(false)
  const [stopSearch, setStopSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  useEffect(() => {
    const saved = localStorage.getItem('driver_name')
    if (saved) {
      setDriverName(saved)
      loadRoute(saved)
    } else if (user?.name || user?.username) {
      setDriverName(user.name || user.username)
    }
  }, [])

  const loadRoute = async (name) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/delivery/driver/${encodeURIComponent(name)}`)
      if (res.ok) {
        const data = await res.json()
        setRoute(data)
        setIsLoggedIn(true)
        localStorage.setItem('driver_name', name)
      } else {
        setError('ไม่พบเส้นทางของคนขับวันนี้')
      }
    } catch {
      setError('เกิดข้อผิดพลาดในการโหลดข้อมูล')
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = () => {
    if (!driverName.trim()) return
    loadRoute(driverName.trim())
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    setRoute(null)
    setSelectedStop(null)
    localStorage.removeItem('driver_name')
  }

  const updateStatus = async (stopId, newStatus, note = '') => {
    if (!route) return
    setLoading(true)
    try {
      const res = await fetch('/api/v1/delivery/update-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          route_id: route.route_id,
          stop_id: stopId,
          status: newStatus,
          note,
        }),
      })
      if (res.ok) {
        await loadRoute(driverName)
        setSelectedStop(null)
        toast.success(`อัปเดตสถานะเป็น "${cfgOf(newStatus).label}" แล้ว`)
      } else {
        const data = await res.json().catch(() => ({}))
        const msg = data.detail || 'ไม่สามารถอัปเดตสถานะได้'
        setError(msg)
        toast.error(msg)
      }
    } catch {
      setError('เกิดข้อผิดพลาดในการอัปเดต')
      toast.error('เกิดข้อผิดพลาดในการอัปเดต')
    } finally {
      setLoading(false)
    }
  }

  const stopIdOf = (stop) => stop.id || stop.order_number

  // GPS auto-arrive: ตรวจระยะห่างคนขับจากพิกัด stop ถ้าใกล้พอ → เรียก auto-arrive
  const tryAutoArrive = (stop, onArrived) => {
    if (!navigator.geolocation) {
      toast.error('อุปกรณ์ไม่รองรับการระบุพิกัด — กรุณากดยืนยันมือ')
      return
    }
    if (!stop?.lat || !stop?.lng) {
      toast.error('จุดส่งนี้ยังไม่มีพิกัด — กรุณากดยืนยันมือ')
      return
    }
    setLoading(true)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude, accuracy } = pos.coords
        const R = 6371000
        const toRad = (d) => (d * Math.PI) / 180
        const dLat = toRad(stop.lat - latitude)
        const dLng = toRad(stop.lng - longitude)
        const a =
          Math.sin(dLat / 2) ** 2 +
          Math.cos(toRad(latitude)) * Math.cos(toRad(stop.lat)) * Math.sin(dLng / 2) ** 2
        const dist = 2 * R * Math.asin(Math.sqrt(a))
        if (accuracy > 100) {
          setLoading(false)
          toast.warning(`ความแม่นยำ GPS ${Math.round(accuracy)}m เกินเกณฑ์ — กรุณากดยืนยันมือ`)
          return
        }
        if (dist > 100) {
          setLoading(false)
          toast.warning(`คุณอยู่ห่างจุดส่ง ${Math.round(dist)}m — กรุณาเข้าใกล้จุดส่ง`)
          return
        }
        try {
          const res = await fetch('/api/v1/delivery/auto-arrive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              route_id: route.route_id,
              stop_id: stopIdOf(stop),
              lat: latitude,
              lng: longitude,
              accuracy_m: accuracy,
            }),
          })
          if (res.ok) {
            toast.success('ตรวจพบว่าถึงจุดส่งแล้ว (GPS)')
            onArrived && onArrived()
          } else {
            toast.error('ไม่สามารถบันทึกการถึงจุดส่งอัตโนมัติได้')
          }
        } catch {
          toast.error('เกิดข้อผิดพลาดในการบันทึก GPS')
        } finally {
          setLoading(false)
        }
      },
      (err) => {
        setLoading(false)
        toast.error('ไม่สามารถดึงพิกัด GPS ได้: ' + err.message)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    )
  }

  const handleAction = (action) => {
    if (!selectedStop) return
    if (action.modal === 'failure') return setShowFailureModal(true)
    if (action.modal === 'partial') return setShowPartialModal(true)
    if (action.next === 'ARRIVED') {
      // ลอง GPS auto-arrive ก่อน ถ้าไม่ผ่านจะแจ้งให้ยืนยันมือ
      tryAutoArrive(selectedStop, () => loadRoute(driverName))
      return
    }
    updateStatus(stopIdOf(selectedStop), action.next)
  }

  const handleFailed = () => {
    if (selectedStop) {
      updateStatus(stopIdOf(selectedStop), 'FAILED', failureReason)
      setShowFailureModal(false)
      setFailureReason('')
    }
  }

  const handlePartial = () => {
    if (selectedStop) {
      updateStatus(stopIdOf(selectedStop), 'PARTIAL', `ส่ง ${partialQty} รายการ`)
      setShowPartialModal(false)
      setPartialQty(0)
    }
  }

  const openGoogleMaps = (stop) => {
    if (stop.lat && stop.lng) {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lng}`, '_blank')
    } else if (stop.address) {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(stop.address)}`, '_blank')
    }
  }

  const handlePodUpload = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      toast.info('เลือกไฟล์แล้ว', {
        description: `${file.name} — ฟีเจอร์อัปโหลดหลักฐานการส่งมอบยังอยู่ระหว่างพัฒนา`,
      })
    }
  }

  const handleReportPin = () => {
    if (!navigator.geolocation) {
      toast.error('อุปกรณ์ไม่รองรับการระบุพิกัด')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords
        toast.success('รายงานพิกัดจริงแล้ว', {
          description: `${latitude}, ${longitude} (ระบบจะส่งพิกัดเมื่อเชื่อมต่อ API)`,
        })
      },
      () => toast.error('ไม่สามารถดึงพิกัดได้')
    )
  }

  const stops = route?.stops || []
  const summary = route?.summary || {}

  const filteredStops = useMemo(() => {
    const q = stopSearch.toLowerCase()
    return stops.filter((s) => {
      const matchesSearch =
        !q ||
        (s.customer || '').toLowerCase().includes(q) ||
        (s.address || '').toLowerCase().includes(q) ||
        (s.order_number || '').toLowerCase().includes(q)
      const matchesStatus = statusFilter === 'ALL' || statusOf(s) === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [stops, stopSearch, statusFilter])

  const nextStop = stops.find((s) => statusOf(s) === 'PENDING' || s.delivery_status === 'IN_TRANSIT')

  /* ---------------- Login screen ---------------- */
  if (!isLoggedIn) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-10">
        <Card className="shadow-lg">
          <CardHeader className="items-center space-y-2 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 text-white">
              <Truck className="h-8 w-8" />
            </div>
            <CardTitle className="text-2xl">Driver Mobile</CardTitle>
            <p className="text-sm text-muted-foreground">เข้าสู่ระบบด้วยชื่อคนขับ</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="driver-name">ชื่อคนขับ</Label>
              <Input
                id="driver-name"
                type="text"
                placeholder="ระบุชื่อคนขับ..."
                value={driverName}
                onChange={(e) => setDriverName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                className="h-12 text-base"
              />
            </div>
            <Button
              className="h-12 w-full text-base"
              onClick={handleLogin}
              disabled={loading || !driverName.trim()}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              {loading ? 'กำลังโหลด...' : 'ค้นหาเส้นทาง'}
            </Button>
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button variant="ghost" className="w-full" onClick={() => navigate('/')}>
              <Home className="h-4 w-4" />
              กลับหน้าแดชบอร์ด
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  /* ---------------- Loading skeleton ---------------- */
  if (loading && !route) {
    return (
      <div className="mx-auto w-full max-w-md space-y-3 px-4 py-6">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-24 w-full rounded-xl" />
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  /* ---------------- Route not found ---------------- */
  if (!route) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-10">
        <Card>
          <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
            <XCircle className="h-10 w-10 text-red-500" />
            <p className="font-medium text-red-600">ไม่พบเส้นทาง</p>
            <Button variant="destructive" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
              ออกจากระบบ
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  /* ---------------- Stop detail view ---------------- */
  if (selectedStop) {
    const status = statusOf(selectedStop)
    const cfg = cfgOf(status)
    const StatusIcon = cfg.icon
    const actions = NEXT_ACTIONS[status] || []

    return (
      <div className="mx-auto w-full max-w-md pb-8">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-gradient-to-r from-blue-700 to-blue-500 px-4 py-3 text-white">
          <Button
            variant="ghost"
            size="sm"
            className="text-white hover:bg-white/20 hover:text-white"
            onClick={() => setSelectedStop(null)}
          >
            <ArrowLeft className="h-4 w-4" />
            กลับ
          </Button>
          <span className="text-sm font-semibold">รายละเอียดจุดจอด</span>
          <Button
            variant="ghost"
            size="sm"
            className="text-white hover:bg-white/20 hover:text-white"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />
            ออก
          </Button>
        </div>

        <div className="space-y-4 p-4">
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Card>
            <CardContent className="space-y-3 p-5">
              <div className="flex items-center justify-between">
                <Badge variant={cfg.variant} className="gap-1.5">
                  <StatusIcon className="h-3.5 w-3.5" />
                  {cfg.label}
                </Badge>
                <span className="text-lg font-extrabold text-muted-foreground">
                  #{selectedStop.sequence || selectedStop.id || '-'}
                </span>
              </div>

              <div className="space-y-1">
                <h3 className="text-xl font-bold">{selectedStop.customer}</h3>
                <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
                  {selectedStop.address}
                </p>
                {selectedStop.order_number && (
                  <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <ClipboardList className="h-4 w-4 shrink-0" />
                    {selectedStop.order_number}
                  </p>
                )}
              </div>

              {selectedStop.products?.length > 0 && (
                <div className="rounded-lg bg-muted/50 p-3">
                  <h4 className="mb-2 flex items-center gap-1.5 text-sm font-bold">
                    <Package className="h-4 w-4" />
                    รายการสินค้า
                  </h4>
                  <div className="space-y-1">
                    {selectedStop.products.map((p, i) => (
                      <div key={i}>
                        {i > 0 && <Separator className="my-1" />}
                        <div className="flex justify-between py-1 text-sm">
                          <span>{p.name}</span>
                          <span className="font-bold text-blue-700">
                            {p.quantity} {p.unit || 'ชิ้น'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p className="flex items-center gap-1.5 text-sm font-semibold">
                <Scale className="h-4 w-4 text-muted-foreground" />
                น้ำหนัก: {selectedStop.weight || 0} kg
              </p>

              <Separator />

              <div className="flex flex-col gap-2.5">
                <Button
                  className="h-12 bg-sky-500 text-base text-white hover:bg-sky-500/90"
                  onClick={() => openGoogleMaps(selectedStop)}
                >
                  <Navigation className="h-4 w-4" />
                  นำทาง
                </Button>

                {actions.map((action) => {
                  const ActionIcon = action.icon
                  return (
                    <Button
                      key={action.next}
                      variant={action.variant}
                      className="h-12 text-base"
                      onClick={() => handleAction(action)}
                      disabled={loading}
                    >
                      <ActionIcon className="h-4 w-4" />
                      {action.label}
                    </Button>
                  )
                })}

                {(status === 'DELIVERED' || status === 'PARTIAL') && (
                  <div className="space-y-2">
                    <Label
                      htmlFor="pod-photo"
                      className="flex h-12 cursor-pointer items-center justify-center gap-2 rounded-md bg-purple-600 text-base font-medium text-white transition-colors hover:bg-purple-600/90"
                    >
                      <Camera className="h-4 w-4" />
                      อัปโหลดรูป POD
                    </Label>
                    <Input
                      id="pod-photo"
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="hidden"
                      onChange={handlePodUpload}
                    />
                  </div>
                )}

                <Button variant="warning" className="h-12 text-sm" onClick={handleReportPin}>
                  <Crosshair className="h-4 w-4" />
                  รายงานพิกัดผิด
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Failure reason dialog */}
        <Dialog open={showFailureModal} onOpenChange={setShowFailureModal}>
          <DialogContent className="max-w-sm">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <XCircle className="h-5 w-5 text-red-500" />
                เหตุผลที่ส่งไม่สำเร็จ
              </DialogTitle>
              <DialogDescription>เลือกเหตุผลเพื่อบันทึกสถานะการจัดส่ง</DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="failure-reason">เหตุผล</Label>
              <Select value={failureReason} onValueChange={setFailureReason}>
                <SelectTrigger id="failure-reason" className="h-11">
                  <SelectValue placeholder="เลือกเหตุผล..." />
                </SelectTrigger>
                <SelectContent>
                  {FAILURE_REASONS.map((reason) => (
                    <SelectItem key={reason} value={reason}>
                      {reason}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => setShowFailureModal(false)}
              >
                ยกเลิก
              </Button>
              <Button
                variant="destructive"
                className="flex-1"
                onClick={handleFailed}
                disabled={!failureReason || loading}
              >
                ยืนยัน
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Partial delivery dialog */}
        <Dialog open={showPartialModal} onOpenChange={setShowPartialModal}>
          <DialogContent className="max-w-sm">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                ส่งบางส่วน
              </DialogTitle>
              <DialogDescription>กรุณาระบุจำนวนที่ส่งจริง</DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="partial-qty">จำนวนที่ส่ง</Label>
              <Input
                id="partial-qty"
                type="number"
                min={0}
                placeholder="จำนวนที่ส่ง"
                value={partialQty}
                onChange={(e) => setPartialQty(Number(e.target.value))}
                className="h-11"
              />
            </div>
            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => setShowPartialModal(false)}
              >
                ยกเลิก
              </Button>
              <Button
                variant="warning"
                className="flex-1"
                onClick={handlePartial}
                disabled={partialQty <= 0 || loading}
              >
                ยืนยัน
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  /* ---------------- Route overview ---------------- */
  const summaryItems = [
    { key: 'delivered', label: 'สำเร็จ', value: summary.delivered || 0, className: 'text-emerald-600' },
    { key: 'in_transit', label: 'กำลังส่ง', value: summary.in_transit || 0, className: 'text-blue-600' },
    { key: 'pending', label: 'รอส่ง', value: summary.pending || 0, className: 'text-slate-500' },
    { key: 'failed', label: 'ไม่สำเร็จ', value: summary.failed || 0, className: 'text-red-600' },
  ]

  return (
    <div className="mx-auto w-full max-w-md pb-8">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-gradient-to-r from-blue-700 to-blue-500 px-4 py-3 text-white">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 truncate text-lg font-bold">
            <Truck className="h-5 w-5 shrink-0" />
            {route.driver}
          </h2>
          <p className="truncate text-xs opacity-90">
            ทะเบียน: {route.plate} · {route.total_weight} kg
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="text-white hover:bg-white/20 hover:text-white"
            onClick={() => loadRoute(driverName)}
            disabled={loading}
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-white hover:bg-white/20 hover:text-white"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />
            ออก
          </Button>
        </div>
      </div>

      <div className="space-y-3 p-3">
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Next stop */}
        {nextStop && (
          <Card className="border-blue-200 bg-blue-50">
            <CardContent className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="flex items-center gap-1 text-xs font-bold text-blue-600">
                  <MapPin className="h-3.5 w-3.5" />
                  จุดถัดไป
                </p>
                <p className="mt-1 truncate text-[15px] font-bold">{nextStop.customer}</p>
                <p className="truncate text-xs text-muted-foreground">{nextStop.address}</p>
              </div>
              <Button size="sm" className="shrink-0" onClick={() => openGoogleMaps(nextStop)}>
                <Navigation className="h-4 w-4" />
                นำทาง
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Summary */}
        <Card>
          <CardContent className="grid grid-cols-4 gap-2 p-4">
            {summaryItems.map((item) => (
              <div key={item.key} className="text-center">
                <span className={cn("block text-2xl font-extrabold", item.className)}>
                  {item.value}
                </span>
                <span className="text-[11px] font-semibold text-muted-foreground">
                  {item.label}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Progress */}
        <div className="space-y-1.5">
          <Progress value={summary.completion_pct || 0} indicatorClassName="bg-emerald-500" />
          <p className="text-xs font-semibold text-muted-foreground">
            {summary.completion_pct || 0}% เสร็จสิ้น
          </p>
        </div>

        {/* Search & filter */}
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="ค้นหาลูกค้า, ที่อยู่, เลข SO..."
              value={stopSearch}
              onChange={(e) => setStopSearch(e.target.value)}
              className="h-11 pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={statusFilter === s ? 'default' : 'secondary'}
                className="h-7 rounded-full px-3 text-[11px]"
                onClick={() => setStatusFilter(s)}
              >
                {s === 'ALL' ? 'ทั้งหมด' : cfgOf(s).label}
              </Button>
            ))}
          </div>
        </div>

        {/* Stop list */}
        <div className="space-y-2.5">
          {filteredStops.map((stop, idx) => {
            const status = statusOf(stop)
            const cfg = cfgOf(status)
            const StatusIcon = cfg.icon
            const origIdx = stops.indexOf(stop) + 1
            return (
              <Card
                key={idx}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedStop(stop)}
                onKeyDown={(e) => e.key === 'Enter' && setSelectedStop(stop)}
                className={cn(
                  "cursor-pointer border-l-4 transition-shadow hover:shadow-md",
                  cfg.border
                )}
              >
                <CardContent className="space-y-1.5 p-4">
                  <div className="flex items-center justify-between">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-[13px] font-bold text-muted-foreground">
                      {origIdx}
                    </span>
                    <Badge variant={cfg.variant} className="gap-1">
                      <StatusIcon className="h-3 w-3" />
                      {cfg.label}
                    </Badge>
                  </div>
                  <p className="text-[15px] font-bold">{stop.customer}</p>
                  <p className="flex items-start gap-1 text-[13px] text-muted-foreground">
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    {stop.address}
                  </p>
                  {stop.weight > 0 && (
                    <p className="text-xs font-semibold text-muted-foreground">{stop.weight} kg</p>
                  )}
                </CardContent>
              </Card>
            )
          })}

          {filteredStops.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
              <Search className="h-9 w-9 opacity-40" />
              <p className="text-sm">ไม่พบจุดจอดที่ค้นหา</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
