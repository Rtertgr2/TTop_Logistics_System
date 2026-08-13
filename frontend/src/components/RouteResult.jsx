import { useState, useEffect, useMemo, useCallback } from "react"
import axios from "axios"
import {
  DndContext, DragOverlay, PointerSensor, KeyboardSensor,
  useSensor, useSensors, useDraggable, useDroppable, closestCenter,
} from "@dnd-kit/core"
import { useData } from "@/context/DataContext"
import { useAuth } from "@/context/AuthContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  MapPin, Copy, Download, Truck, Warehouse,
  Scale, GripVertical, CheckCircle, XCircle, RefreshCw, ArrowRight,
  History, Lightbulb, Loader2,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import RouteMiniMap from "@/components/RouteMiniMap"
import DeferredOrdersCard from "@/components/DeferredOrdersCard"
import {
  DEPOT_COORDS,
  CAPACITY_LIMIT_PCT,
  capacityCfgOf,
  pctOf,
  VEHICLE_COLOR_CLASSES,
} from "@/constants"

const DEFAULT_DEPOT = { ...DEPOT_COORDS, address: "คลังสินค้าหลัก (Depot)" }

// คีย์เส้นทาง: ใช้ DB route_id ถ้ามี มิฉะนั้นใช้ vehicle_id
function routeKey(r) {
  return r.route_id ?? r.id ?? r.vehicle_id
}

/* ─── Stop item (draggable in LB mode, normal otherwise) ─────────── */
function StopItem({ stop, sIndex, canDrag, rKey, sourceVehicleId, disabled }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `stop-${rKey}-${stop.id ?? stop.order_number ?? sIndex}`,
    disabled: !canDrag || disabled,
    data: { stop, sourceRouteId: rKey, sourceVehicleId },
  })

  return (
    <li
      ref={canDrag ? setNodeRef : undefined}
      className={cn(
        "flex gap-3 rounded-md border p-3",
        isDragging && "opacity-40",
        canDrag ? "bg-background hover:border-blue-300" : "bg-muted/30"
      )}
    >
      {canDrag && (
        <GripVertical
          className="mt-0.5 h-4 w-4 shrink-0 cursor-grab text-muted-foreground active:cursor-grabbing"
          {...listeners}
          {...attributes}
        />
      )}
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
        {sIndex + 1}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="text-sm font-medium">
          {stop.customer}
          {stop.order_number && (
            <span className="font-normal text-muted-foreground"> ({stop.order_number})</span>
          )}
        </div>
        <div className="text-xs text-muted-foreground">{stop.address}</div>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {stop.zone && <Badge variant="outline">{stop.zone}</Badge>}
          <Badge variant={stop.is_verified ? "success" : "warning"}>
            {stop.is_verified ? "100%" : `${Math.round(stop.confidence_score || 50)}%`}
          </Badge>
          <span className="text-xs text-muted-foreground">{stop.weight} kg</span>
        </div>
      </div>
    </li>
  )
}

/* ─── Route card (also a drop zone in LB mode) ──────────────────── */
function RouteCard({
  route, index, depot, vehicleColors, activeDrag, canTransfer, lbMode,
  onOpenMaps, onCopyMapsUrl, onSendDriverLine, lineUserIdMap, sendingDriverLine,
}) {
  const rKey = routeKey(route)
  const capText = route.capacity
    ? `${(route.capacity / 1000).toFixed(2)} ตัน (${route.capacity} kg)`
    : { 1: "3.75 ตัน (3,750 kg)", 2: "1.8 - 1.9 ตัน (1,900 kg)", 3: "1.95 - 2.24 ตัน (2,240 kg)", 4: "3.75 ตัน (3,750 kg)" }[route.vehicle_id] || "ไม่ระบุความจุ"

  const maxCapKg = route.capacity || (route.vehicle_id === 2 ? 1900 : route.vehicle_id === 3 ? 2240 : 3750)
  const totalWeight = route.total_weight ?? route.current_weight ?? 0
  const weightPercent = maxCapKg > 0 ? Math.min(100, Math.round((totalWeight / maxCapKg) * 100)) : 0
  const barColor = weightPercent > 90 ? "bg-red-500" : "bg-blue-500"
  const cfg = capacityCfgOf(route.status)

  const { setNodeRef, isOver } = useDroppable({
    id: `vehicle-${rKey}`,
    data: { route: { ...route, route_id: rKey } },
    disabled: !lbMode,
  })

  const projection = useMemo(() => {
    if (!activeDrag || !lbMode) return null
    const isSource = activeDrag.sourceRouteId === rKey
    const newWeight = totalWeight + (activeDrag.stop.weight || 0)
    const newPct = pctOf(newWeight, maxCapKg)
    return { isSource, newWeight, newPct, valid: !isSource && newPct <= CAPACITY_LIMIT_PCT }
  }, [activeDrag, rKey, totalWeight, maxCapKg, lbMode])

  const valid = projection?.valid
  const isTarget = Boolean(activeDrag) && !projection?.isSource && lbMode

  return (
    <Card
      ref={lbMode ? setNodeRef : undefined}
      className={cn(
        "flex flex-col transition-colors",
        lbMode && isTarget && !isOver && (valid ? "border-dashed border-emerald-400" : "border-dashed border-red-300"),
        lbMode && isOver && valid && "border-emerald-500 bg-emerald-50",
        lbMode && isOver && !valid && "border-red-500 bg-red-50",
        lbMode && projection?.isSource && "opacity-90"
      )}
    >
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg text-white", vehicleColors[index % 4])}>
              <Truck className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base">{route.name || `รถคันที่ ${route.vehicle_id}`}</CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">
                คนขับ: {route.driver || "ไม่ระบุ"} · ทะเบียน: {route.plate || "ไม่ระบุ"}
              </p>
              <p className="text-xs text-muted-foreground">น้ำหนักสูงสุด: {capText}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge variant="secondary">{route.stops?.length || 0} จุดส่ง</Badge>
            <Badge variant="outline">{totalWeight} kg</Badge>
            {lbMode && <Badge variant={cfg.variant}>{cfg.label}</Badge>}
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">น้ำหนักบรรทุก: {totalWeight} / {maxCapKg} kg</span>
            <span className={cn(weightPercent > 90 && "font-semibold text-red-600")}>{weightPercent}%</span>
          </div>
          <Progress value={weightPercent} indicatorClassName={barColor} />
        </div>

        {lbMode && isTarget && (
          <div className={cn(
            "flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] font-semibold",
            valid ? "border-emerald-300 bg-emerald-100 text-emerald-700" : "border-red-300 bg-red-100 text-red-700"
          )}>
            {valid ? <CheckCircle className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {valid
              ? `วางได้ — ${projection.newWeight.toFixed(1)} kg (${projection.newPct}%)`
              : `เกิน ${CAPACITY_LIMIT_PCT}% — ${projection.newPct}%`}
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {/* แผนที่แสดงเสมอ — ทั้งโหมดปกติและโหมด Load Balancing */}
        <RouteMiniMap route={route} depotLat={depot.lat} depotLng={depot.lng} colorIndex={index} className="h-64" />

        <div>
          <p className="mb-2 text-sm font-medium">
            ลำดับการจัดส่ง ({route.stops?.length || 0} จุด)
            {lbMode && canTransfer && (
              <span className="ml-2 text-[11px] font-normal text-blue-600">— ลากจุดส่ง (จับที่เด handle ด้านซ้าย) ไปวางที่รถคันอื่น</span>
            )}
          </p>
          <div className={cn("max-h-80 overflow-y-auto rounded-md border", lbMode && "bg-accent/30")}>
            <ol className="space-y-2 p-3">
              <li className="flex gap-3 rounded-md border border-red-200 bg-red-50 p-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-600 text-xs font-semibold text-white">
                  <Warehouse className="h-3.5 w-3.5" />
                </span>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="text-sm font-medium text-red-700">คลังสินค้าหลัก (จุดเริ่มต้น)</div>
                  <div className="text-xs text-muted-foreground">{depot.address}</div>
                </div>
              </li>

              {(route.stops || []).map((stop, sIndex) => (
                <StopItem
                  key={stop.id ?? stop.order_number ?? sIndex}
                  stop={stop}
                  sIndex={sIndex}
                  canDrag={lbMode}
                  rKey={rKey}
                  sourceVehicleId={route.vehicle_id}
                  disabled={!canTransfer}
                />
              ))}

              <li className="flex gap-3 rounded-md border border-red-200 bg-red-50 p-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-600 text-xs font-semibold text-white">
                  <Warehouse className="h-3.5 w-3.5" />
                </span>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="text-sm font-medium text-red-700">คลังสินค้าหลัก (จุดสิ้นสุด)</div>
                <div className="text-xs text-muted-foreground">{depot.address}</div>
              </div>
            </li>
            </ol>
          </div>
        </div>

        {!lbMode && (
          <div className="flex flex-wrap gap-2">
            <Button className="flex-1" onClick={() => onOpenMaps(route)}>
              <MapPin className="h-4 w-4" />
              ดูใน Google Maps
            </Button>
            <Button variant="outline" onClick={() => onCopyMapsUrl(route)}>
              <Copy className="h-4 w-4" />
              คัดลอกลิงก์แมพ
            </Button>
            <Button
              className="bg-cyan-500 text-white hover:bg-cyan-600"
              onClick={() => onSendDriverLine(route)}
              disabled={sendingDriverLine}
              title={lineUserIdMap[route.vehicle_id] ? "ส่งลิงก์แมพเข้า LINE ให้คนขับคันนี้" : "กรอก LINE User ID ที่หน้า จัดการรถ ก่อน"}
            >
              {sendingDriverLine ? "กำลังส่ง..." : "ส่ง LINE ให้คนขับ"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function RouteResult({ onSendLine, onSendDriverLine }) {
  const { routes, deferredInfo, fetchTodayData } = useData()
  const { user } = useAuth()
  const vehicleColors = VEHICLE_COLOR_CLASSES
  const [downloadingExcel, setDownloadingExcel] = useState(false)
  const [sendingLine, setSendingLine] = useState(false)
  const [sendingDriverLine, setSendingDriverLine] = useState(false)
  const [lineUserIdMap, setLineUserIdMap] = useState({})

  // LB state
  const [lbMode, setLbMode] = useState(false)
  const [lbVehicles, setLbVehicles] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [transferHistory, setTransferHistory] = useState([])
  const [lbLoading, setLbLoading] = useState(false)
  const [activeDrag, setActiveDrag] = useState(null)
  const [pendingTransfer, setPendingTransfer] = useState(null)
  const [executing, setExecuting] = useState(null)

  const canTransfer = ["admin", "dispatcher"].includes(user?.role)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor)
  )

  useEffect(() => {
    const fetchVehicles = async () => {
      try {
        const res = await fetch("/api/v1/vehicles")
        if (res.ok) {
          const data = await res.json()
          const map = {}
          ;(data.vehicles || []).forEach((v) => {
            if (v.id !== null && v.line_user_id) map[v.id] = v.line_user_id
          })
          setLineUserIdMap(map)
        }
      } catch (e) {
        console.warn("โหลดข้อมูลรถเพื่อส่ง LINE ไม่สำเร็จ", e)
      }
    }
    fetchVehicles()
  }, [])

  const handleSendDriverLine = async (route) => {
    const driverLineUserId = lineUserIdMap[route.vehicle_id]
    if (!driverLineUserId) {
      toast.error("ยังไม่ได้กรอก LINE User ID ของคนขับคันนี้\nไปที่เมนู จัดการรถ แล้วกรอก LINE User ID ให้รถคันนี้ก่อน")
      return
    }
    if (!onSendDriverLine) return
    setSendingDriverLine(true)
    try {
      await onSendDriverLine(route, driverLineUserId)
      toast.success(`ส่งลิงก์แมพเข้า LINE ให้คนขับคัน "${route.name || route.vehicle_id}" เรียบร้อยแล้ว`)
    } catch (err) {
      toast.error(err.message || "ส่ง LINE ให้คนขับไม่สำเร็จ")
    } finally {
      setSendingDriverLine(false)
    }
  }

  const getMapsUrl = (route) => {
    if (route.google_maps_link) return route.google_maps_link
    const addresses = (route.stops || []).map((s) => encodeURIComponent(s.address)).join("/")
    return `https://www.google.com/maps/dir/${addresses}`
  }

  const handleOpenMaps = (route) => window.open(getMapsUrl(route), "_blank")

  const handleCopyMapsUrl = (route) => {
    const url = getMapsUrl(route)
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(() => {
        toast.success(`คัดลอกลิงก์ Google Maps ของ ${route.name || "รถคันนี้"} เรียบร้อยแล้ว!`)
      }).catch(() => fallbackCopyTextToClipboard(url, route.name))
    } else {
      fallbackCopyTextToClipboard(url, route.name)
    }
  }

  const fallbackCopyTextToClipboard = (text, routeName) => {
    const textArea = document.createElement("textarea")
    textArea.value = text
    document.body.appendChild(textArea)
    textArea.select()
    try {
      document.execCommand("copy")
      toast.success(`คัดลอกลิงก์ Google Maps ของ ${routeName || "รถคันนี้"} เรียบร้อยแล้ว!`)
    } catch (err) {
      console.error("Fallback copy failed", err)
      toast.error("ไม่สามารถคัดลอกลิงก์อัตโนมัติได้")
    }
    document.body.removeChild(textArea)
  }

  const handleDownloadExcel = async () => {
    setDownloadingExcel(true)
    try {
      const response = await axios.post("/api/v1/export-manifest-excel", { routes }, { responseType: "blob" })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement("a")
      link.href = url
      link.setAttribute("download", `driver_manifest_all_${new Date().toISOString().slice(0, 10)}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error("Download excel failed:", err)
      toast.error("ไม่สามารถดาวน์โหลดไฟล์ Excel ได้")
    } finally {
      setDownloadingExcel(false)
    }
  }

  /* ── Load Balancing data ───────────────────────────────────────── */
  const loadLbData = useCallback(async () => {
    setLbLoading(true)
    try {
      const [analyzeRes, suggestRes, historyRes] = await Promise.all([
        fetch("/api/v1/load-balance/analyze"),
        fetch("/api/v1/load-balance/suggestions"),
        fetch("/api/v1/load-balance/transfer-history"),
      ])
      if (analyzeRes.ok) {
        const data = await analyzeRes.json()
        setLbVehicles(data.vehicles || [])
      }
      if (suggestRes.ok) {
        const data = await suggestRes.json()
        setSuggestions(data.suggestions || [])
      }
      if (historyRes.ok) {
        const data = await historyRes.json()
        setTransferHistory(data.transfers || [])
      }
      await fetchTodayData()
    } catch {
      toast.error("เกิดข้อผิดพลาดในการโหลดข้อมูล Load Balancing")
    } finally {
      setLbLoading(false)
    }
  }, [fetchTodayData])

  // board: รวมข้อมูล capacity จาก analyze (มี DB route_id) เข้ากับแสดงผลจาก context routes
  const board = useMemo(() => {
    const routeByVehicle = new Map(routes.map((r) => [r.vehicle_id, r]))
    if (!lbVehicles.length) {
      return routes.map((r) => ({ ...r, route_id: r.route_id ?? r.id ?? r.vehicle_id }))
    }
    return lbVehicles.map((v) => {
      const ctx = routeByVehicle.get(v.vehicle_id) || {}
      const capacity = v.capacity ?? ctx.capacity ?? (v.vehicle_id === 2 ? 1900 : v.vehicle_id === 3 ? 2240 : 3750)
      return {
        ...ctx,
        ...v,
        route_id: v.route_id ?? ctx.route_id ?? ctx.id ?? v.vehicle_id,
        vehicle_id: v.vehicle_id ?? ctx.vehicle_id,
        stops: ctx.stops || [],
        depot: ctx.depot,
        driver: ctx.driver ?? v.driver,
        plate: ctx.plate ?? v.plate,
        name: ctx.name ?? v.name,
        google_maps_link: ctx.google_maps_link,
        total_weight: ctx.total_weight ?? v.current_weight ?? 0,
        capacity,
      }
    })
  }, [lbVehicles, routes])

  const displayRoutes = lbMode ? board : routes

  const executeTransfer = async (transfer) => {
    setExecuting(transfer.stopId)
    try {
      const res = await fetch("/api/v1/load-balance/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_route_id: transfer.sourceRouteId,
          target_route_id: transfer.targetRouteId,
          stop_id: transfer.stopId,
        }),
      })
      if (res.ok) {
        toast.success("ย้ายจุดจอดสำเร็จ", { description: `${transfer.stopLabel} → ${transfer.targetLabel}` })
        await loadLbData()
      } else {
        const data = await res.json().catch(() => ({}))
        toast.error("ไม่สามารถย้ายได้", { description: data.detail || "เกิดข้อผิดพลาด" })
      }
    } catch {
      toast.error("เกิดข้อผิดพลาดในการย้าย")
    } finally {
      setExecuting(null)
      setPendingTransfer(null)
    }
  }

  const handleDragStart = (event) => setActiveDrag(event.active.data.current)
  const handleDragCancel = () => setActiveDrag(null)

  const handleDragEnd = (event) => {
    const { active, over } = event
    setActiveDrag(null)
    if (!over) return
    const src = active.data.current
    const target = over.data.current?.route
    if (!src || !target) return
    if (src.sourceRouteId === target.route_id) return

    const maxCapKg = target.capacity || 3750
    const newWeight = (target.total_weight || target.current_weight || 0) + (src.stop.weight || 0)
    const newPct = pctOf(newWeight, maxCapKg)

    if (newPct > CAPACITY_LIMIT_PCT) {
      toast.error(`เกินความจุที่กำหนด (${CAPACITY_LIMIT_PCT}%)`, {
        description: `คันที่ ${target.vehicle_id} จะมีน้ำหนัก ${newWeight.toFixed(1)} kg (${newPct}%) — ยกเลิกการย้าย`,
      })
      return
    }

    setPendingTransfer({
      stopId: src.stop.id,
      stopLabel: src.stop.customer,
      sourceRouteId: src.sourceRouteId,
      sourceLabel: `คันที่ ${src.sourceVehicleId}`,
      targetRouteId: target.route_id,
      targetLabel: `คันที่ ${target.vehicle_id}`,
      detail: `น้ำหนักใหม่: คันที่ ${target.vehicle_id} ${newWeight.toFixed(1)} kg (${newPct}%) จากความจุ ${maxCapKg} kg`,
    })
  }

  const handleSuggestionConfirm = (s) => {
    setPendingTransfer({
      stopId: s.stop.id,
      stopLabel: s.stop.customer,
      sourceRouteId: s.source_route_id,
      sourceLabel: `คันที่ ${s.source_vehicle_id} (${s.source_driver})`,
      targetRouteId: s.target.target_route_id,
      targetLabel: `คันที่ ${s.target.target_vehicle_id} (${s.target.target_driver})`,
      detail: `น้ำหนักใหม่: ${s.source_driver} ${s.source_weight_after} kg → ${s.target.target_driver} ${s.target.new_target_weight} kg`,
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>ผลลัพธ์การจัดเส้นทางตามโซนและน้ำหนักบรรทุก</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              จัดสรรออเดอร์ลงรถตามทิศทางภูมิศาสตร์และขีดจำกัดน้ำหนัก
              {lbMode && " · โหมด Load Balancing กำลังเปิดอยู่ (ลากจุดส่งระหว่างรถได้)"}
            </p>
          </div>
          {routes.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <Button
                variant={lbMode ? "default" : "outline"}
                onClick={() => {
                  if (!lbMode) {
                    setLbMode(true)
                    loadLbData()
                  } else {
                    setLbMode(false)
                  }
                }}
                disabled={lbLoading}
              >
                <Scale className={cn("h-4 w-4", lbMode && "text-white")} />
                {lbMode ? "ปิด Load Balancing" : "Load Balancing"}
              </Button>
              {!lbMode && (
                <Button variant="outline" onClick={handleDownloadExcel} disabled={downloadingExcel}>
                  {downloadingExcel ? "กำลังสร้าง Excel..." : (<><Download className="h-4 w-4" />ดาวน์โหลดใบส่งงานคนขับรถ (Excel)</>)}
                </Button>
              )}
              {!lbMode && onSendLine && (
                <Button
                  className="bg-cyan-500 text-white hover:bg-cyan-600"
                  onClick={async () => { setSendingLine(true); try { await onSendLine(routes) } finally { setSendingLine(false) } }}
                  disabled={sendingLine}
                >
                  {sendingLine ? "กำลังส่ง..." : "ส่ง LINE Notification"}
                </Button>
              )}
            </div>
          )}
        </CardHeader>
      </Card>

      <DeferredOrdersCard deferredInfo={deferredInfo} />

      {!lbMode && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {displayRoutes.map((route, index) => {
            const depot = route.depot || DEFAULT_DEPOT
            return (
              <RouteCard
                key={routeKey(route)}
                route={route}
                index={index}
                depot={depot}
                vehicleColors={vehicleColors}
                activeDrag={null}
                canTransfer={canTransfer}
                lbMode={false}
                onOpenMaps={handleOpenMaps}
                onCopyMapsUrl={handleCopyMapsUrl}
                onSendDriverLine={handleSendDriverLine}
                lineUserIdMap={lineUserIdMap}
                sendingDriverLine={sendingDriverLine}
              />
            )
          })}
        </div>
      )}

      {lbMode && (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {displayRoutes.map((route, index) => {
              const depot = route.depot || DEFAULT_DEPOT
              return (
                <RouteCard
                  key={routeKey(route)}
                  route={route}
                  index={index}
                  depot={depot}
                  vehicleColors={vehicleColors}
                  activeDrag={activeDrag}
                  canTransfer={canTransfer}
                  lbMode={true}
                  onOpenMaps={handleOpenMaps}
                  onCopyMapsUrl={handleCopyMapsUrl}
                  onSendDriverLine={handleSendDriverLine}
                  lineUserIdMap={lineUserIdMap}
                  sendingDriverLine={sendingDriverLine}
                />
              )
            })}
          </div>

          <DragOverlay dropAnimation={null}>
            {activeDrag ? (
              <div className="flex items-center gap-2 rounded-lg border-2 border-blue-500 bg-background p-2.5 shadow-lg">
                <GripVertical className="h-4 w-4 text-blue-600" />
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold">{activeDrag.stop.customer}</p>
                  <p className="text-[11px] text-muted-foreground">{activeDrag.stop.weight || 0} kg</p>
                </div>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      {lbMode && suggestions.length > 0 && (
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-base font-bold">
            <Lightbulb className="h-4 w-4" />
            คำแนะนำการย้าย
            <Badge variant="secondary">{suggestions.length} รายการ</Badge>
            <Button variant="ghost" size="sm" onClick={loadLbData} disabled={lbLoading}>
              <RefreshCw className={cn("h-3.5 w-3.5", lbLoading && "animate-spin")} />
              รีเฟรช
            </Button>
          </h2>
          <div className="space-y-3">
            {suggestions.map((s, idx) => (
              <Card key={idx}>
                <CardContent className="space-y-3 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">Score: {s.transfer_score}</Badge>
                    <span className="text-[13px] font-bold">ย้าย: {s.stop.customer}</span>
                  </div>
                  <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted-foreground">
                    <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{s.stop.address}</span>
                    <span className="flex items-center gap-1"><Scale className="h-3.5 w-3.5" />{s.stop.weight} kg</span>
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="min-w-[200px] flex-1 rounded-lg bg-red-50 p-3">
                      <p className="mb-1 flex items-center gap-1 text-xs font-bold text-red-600"><Truck className="h-3.5 w-3.5" />ต้นทาง</p>
                      <p className="text-[13px] font-semibold">คันที่ {s.source_vehicle_id} ({s.source_driver})</p>
                      <p className="text-xs text-muted-foreground">{s.source_weight_before}kg → <strong>{s.source_weight_after}kg</strong> ({s.source_pct_before}% → {s.source_pct_after}%)</p>
                    </div>
                    <ArrowRight className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <div className="min-w-[200px] flex-1 rounded-lg bg-emerald-50 p-3">
                      <p className="mb-1 flex items-center gap-1 text-xs font-bold text-emerald-600"><Truck className="h-3.5 w-3.5" />ปลายทาง</p>
                      <p className="text-[13px] font-semibold">คันที่ {s.target.target_vehicle_id} ({s.target.target_driver})</p>
                      <p className="text-xs text-muted-foreground">{s.target.target_weight}kg → <strong>{s.target.new_target_weight}kg</strong> ({s.target.target_weight_pct}% → {s.target.new_target_pct}%)</p>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button variant="success" onClick={() => handleSuggestionConfirm(s)} disabled={executing === s.stop.id || !canTransfer}>
                      {executing === s.stop.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
                      {executing === s.stop.id ? "กำลังย้าย..." : "ยืนยันย้าย"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {lbMode && suggestions.length === 0 && !lbLoading && (
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <CheckCircle className="h-9 w-9 text-emerald-600" />
            <p className="text-base font-semibold text-emerald-700">สมดุลดีแล้ว!</p>
            <p className="text-sm text-muted-foreground">ไม่มีรถที่ต้องย้ายภาระในขณะนี้</p>
          </CardContent>
        </Card>
      )}

      {lbMode && transferHistory.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <History className="h-4 w-4" />
              ประวัติการย้าย
            </CardTitle>
            <Badge variant="secondary">{transferHistory.length} รายการ</Badge>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Stop</TableHead>
                  <TableHead>จากรถ</TableHead>
                  <TableHead>ไปรถ</TableHead>
                  <TableHead>เหตุผล</TableHead>
                  <TableHead>อนุมัติโดย</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transferHistory.map((t, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">#{t.stop_id}</TableCell>
                    <TableCell>คันที่ {t.from_vehicle_id}</TableCell>
                    <TableCell>
                      <span className="flex items-center gap-1"><ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />คันที่ {t.to_vehicle_id}</span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{t.reason || "-"}</TableCell>
                    <TableCell>{t.approved_by}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <AlertDialog open={Boolean(pendingTransfer)} onOpenChange={(open) => !open && setPendingTransfer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2"><Scale className="h-5 w-5 text-blue-600" />ยืนยันการย้ายจุดจอด</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm">
                <p>ย้ายจุดจอด <strong>{pendingTransfer?.stopLabel}</strong></p>
                <span className="flex flex-wrap items-center gap-2">
                  <Badge variant="danger">{pendingTransfer?.sourceLabel}</Badge>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  <Badge variant="success">{pendingTransfer?.targetLabel}</Badge>
                </span>
                <p className="text-muted-foreground">{pendingTransfer?.detail}</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={Boolean(executing)}>
              <XCircle className="h-4 w-4" />ยกเลิก
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); if (pendingTransfer) executeTransfer(pendingTransfer) }}
              disabled={Boolean(executing)}
            >
              {executing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
              {executing ? "กำลังย้าย..." : "ยืนยันย้าย"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default RouteResult
