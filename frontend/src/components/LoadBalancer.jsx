import { useState, useEffect, useMemo, useCallback } from "react"
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  closestCenter,
} from "@dnd-kit/core"
import { useData } from "@/context/DataContext"
import { useAuth } from "@/context/AuthContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Truck, Scale, ArrowRight, CheckCircle, XCircle, RefreshCw, AlertTriangle,
  GripVertical, MapPin, User, History, Lightbulb, Loader2, Package,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { CAPACITY_LIMIT_PCT, capacityCfgOf, pctOf } from "@/constants"

/* ─── Draggable stop card ───────────────────────────────────────── */
function DraggableStop({ stop, vehicle, disabled }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `stop-${vehicle.route_id}-${stop.id}`,
    disabled,
    data: { stop, sourceRouteId: vehicle.route_id, sourceVehicleId: vehicle.vehicle_id },
  })

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn(
        "flex items-start gap-2 rounded-lg border bg-background p-2.5 text-left",
        disabled ? "cursor-not-allowed opacity-70" : "cursor-grab active:cursor-grabbing hover:border-blue-300 hover:bg-accent",
        isDragging && "opacity-40"
      )}
    >
      <GripVertical className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-semibold">{stop.customer}</p>
        <p className="truncate text-[11px] text-muted-foreground">{stop.address}</p>
      </div>
      <span className="shrink-0 text-[11px] font-bold text-blue-700">{stop.weight || 0} kg</span>
    </div>
  )
}

/* ─── Droppable vehicle zone ────────────────────────────────────── */
function VehicleZone({ vehicle, activeDrag, canTransfer }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `vehicle-${vehicle.route_id}`,
    data: { vehicle },
  })

  const cfg = capacityCfgOf(vehicle.status)

  const projection = useMemo(() => {
    if (!activeDrag) return null
    const isSource = activeDrag.sourceRouteId === vehicle.route_id
    const newWeight = (vehicle.current_weight || 0) + (activeDrag.stop.weight || 0)
    const newPct = pctOf(newWeight, vehicle.capacity)
    return { isSource, newWeight, newPct, valid: !isSource && newPct <= CAPACITY_LIMIT_PCT }
  }, [activeDrag, vehicle])

  const valid = projection?.valid
  const isTarget = Boolean(activeDrag) && !projection?.isSource

  return (
    <Card
      ref={setNodeRef}
      className={cn(
        "flex flex-col border-2 transition-colors",
        cfg.ring,
        isTarget && !isOver && (valid ? "border-dashed border-emerald-400" : "border-dashed border-red-300"),
        isOver && valid && "border-emerald-500 bg-emerald-50",
        isOver && !valid && "border-red-500 bg-red-50",
        projection?.isSource && "opacity-90"
      )}
    >
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-sm font-bold">
            <Truck className="h-4 w-4 text-blue-600" />
            คันที่ {vehicle.vehicle_id}
          </span>
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
        </div>

        <div className="space-y-0.5">
          <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <User className="h-3.5 w-3.5" />
            {vehicle.driver || 'ไม่ระบุ'}
          </p>
          <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <Package className="h-3.5 w-3.5" />
            {vehicle.plate}
          </p>
        </div>

        <Progress value={Math.min(100, vehicle.weight_pct)} indicatorClassName={cfg.bar} />
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">
            {vehicle.current_weight} / {vehicle.capacity} kg
          </span>
          <span className={cn("font-bold", cfg.variant === 'danger' ? 'text-red-600' : cfg.variant === 'warning' ? 'text-amber-600' : cfg.variant === 'info' ? 'text-blue-600' : 'text-emerald-600')}>
            {vehicle.weight_pct}%
          </span>
        </div>

        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <MapPin className="h-3.5 w-3.5" />
          {vehicle.num_stops} จุดส่ง
        </p>

        {/* Drop projection feedback */}
        {isTarget && (
          <div
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] font-semibold",
              valid
                ? "border-emerald-300 bg-emerald-100 text-emerald-700"
                : "border-red-300 bg-red-100 text-red-700"
            )}
          >
            {valid ? <CheckCircle className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {valid
              ? `วางได้ — ${projection.newWeight.toFixed(1)} kg (${projection.newPct}%)`
              : `เกิน ${CAPACITY_LIMIT_PCT}% — ${projection.newPct}%`}
          </div>
        )}

        {vehicle.stops.length > 0 && (
          <>
            <Separator />
            <ScrollArea className="h-40 pr-3">
              <div className="space-y-1.5">
                {vehicle.stops.map((stop, idx) => (
                  <DraggableStop
                    key={stop.id ?? idx}
                    stop={stop}
                    vehicle={vehicle}
                    disabled={!canTransfer}
                  />
                ))}
              </div>
            </ScrollArea>
          </>
        )}
      </CardContent>
    </Card>
  )
}

/* ─── Main component ────────────────────────────────────────────── */
export default function LoadBalancer() {
  const { routes, fetchTodayData } = useData()
  const { user } = useAuth()

  const [vehicles, setVehicles] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [transferHistory, setTransferHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [executing, setExecuting] = useState(null)
  const [activeDrag, setActiveDrag] = useState(null)
  const [pendingTransfer, setPendingTransfer] = useState(null)

  const canTransfer = ['admin', 'dispatcher'].includes(user?.role)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor)
  )

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [analyzeRes, suggestRes, historyRes] = await Promise.all([
        fetch('/api/v1/load-balance/analyze'),
        fetch('/api/v1/load-balance/suggestions'),
        fetch('/api/v1/load-balance/transfer-history'),
      ])

      if (analyzeRes.ok) {
        const data = await analyzeRes.json()
        setVehicles(data.vehicles || [])
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
      setError('เกิดข้อผิดพลาดในการโหลดข้อมูล')
    } finally {
      setLoading(false)
    }
  }, [fetchTodayData])

  useEffect(() => {
    loadData()
  }, [])

  // ผูก stops ของแต่ละ route เข้ากับผลวิเคราะห์ เพื่อใช้ลากย้ายได้
  const board = useMemo(() => {
    const routeMap = new Map(routes.map((r) => [r.id, r]))
    return vehicles.map((v) => ({
      ...v,
      stops: routeMap.get(v.route_id)?.stops || [],
    }))
  }, [vehicles, routes])

  const executeTransfer = async (transfer) => {
    setExecuting(transfer.stopId)
    try {
      const res = await fetch('/api/v1/load-balance/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_route_id: transfer.sourceRouteId,
          target_route_id: transfer.targetRouteId,
          stop_id: transfer.stopId,
        }),
      })

      if (res.ok) {
        toast.success('ย้ายจุดจอดสำเร็จ', {
          description: `${transfer.stopLabel} → ${transfer.targetLabel}`,
        })
        await loadData()
      } else {
        const data = await res.json().catch(() => ({}))
        toast.error('ไม่สามารถย้ายได้', { description: data.detail || 'เกิดข้อผิดพลาด' })
      }
    } catch {
      toast.error('เกิดข้อผิดพลาดในการย้าย')
    } finally {
      setExecuting(null)
      setPendingTransfer(null)
    }
  }

  const handleDragStart = (event) => {
    setActiveDrag(event.active.data.current)
  }

  const handleDragCancel = () => setActiveDrag(null)

  const handleDragEnd = (event) => {
    const { active, over } = event
    setActiveDrag(null)
    if (!over) return

    const src = active.data.current
    const target = over.data.current?.vehicle
    if (!src || !target) return

    if (src.sourceRouteId === target.route_id) return

    const newWeight = (target.current_weight || 0) + (src.stop.weight || 0)
    const newPct = pctOf(newWeight, target.capacity)

    if (newPct > CAPACITY_LIMIT_PCT) {
      toast.error(`เกินความจุที่กำหนด (${CAPACITY_LIMIT_PCT}%)`, {
        description: `คันที่ ${target.vehicle_id} จะมีน้ำหนัก ${newWeight.toFixed(1)} kg (${newPct}%) — ยกเลิกการย้าย`,
      })
      return
    }

    const source = board.find((v) => v.route_id === src.sourceRouteId)
    setPendingTransfer({
      stopId: src.stop.id,
      stopLabel: src.stop.customer,
      sourceRouteId: src.sourceRouteId,
      sourceLabel: `คันที่ ${src.sourceVehicleId} (${source?.driver || '-'})`,
      targetRouteId: target.route_id,
      targetLabel: `คันที่ ${target.vehicle_id} (${target.driver || '-'})`,
      detail: `น้ำหนักใหม่: ${target.driver || `คันที่ ${target.vehicle_id}`} ${newWeight.toFixed(1)} kg (${newPct}%) จากความจุ ${target.capacity} kg`,
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

  const hasRoutes = board.length > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Scale className="h-6 w-6 text-blue-600" />
            Load Balancing
          </h1>
          <p className="text-sm text-muted-foreground">
            วิเคราะห์และกระจายภาระระหว่างรถขนส่ง — ลากจุดส่งไปวางที่รถคันอื่นเพื่อย้าย
          </p>
        </div>
        <Button onClick={loadData} disabled={loading}>
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          {loading ? 'กำลังวิเคราะห์...' : 'วิเคราะห์ใหม่'}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!canTransfer && hasRoutes && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            บัญชีของคุณดูข้อมูลได้อย่างเดียว — เฉพาะ Admin และ Dispatcher เท่านั้นที่ย้ายจุดส่งได้
          </AlertDescription>
        </Alert>
      )}

      {loading && !hasRoutes && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-72 w-full rounded-xl" />
          ))}
        </div>
      )}

      {!hasRoutes && !loading && (
        <div className="flex flex-col items-center gap-2 py-16 text-center text-muted-foreground">
          <Truck className="h-12 w-12 opacity-40" />
          <p className="text-base font-semibold">ยังไม่มีเส้นทางวันนี้</p>
          <p className="text-sm">กรุณาคำนวณเส้นทางก่อนใช้ Load Balancing</p>
        </div>
      )}

      {hasRoutes && (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          {/* Vehicle utilization grid */}
          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-base font-bold">
              <Truck className="h-4 w-4" />
              สถานะรถแต่ละคัน
              <Badge variant="secondary">{board.length} คัน</Badge>
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {board.map((v) => (
                <VehicleZone
                  key={v.route_id ?? v.vehicle_id}
                  vehicle={v}
                  activeDrag={activeDrag}
                  canTransfer={canTransfer}
                />
              ))}
            </div>
          </section>

          <DragOverlay dropAnimation={null}>
            {activeDrag ? (
              <div className="flex items-center gap-2 rounded-lg border-2 border-blue-500 bg-background p-2.5 shadow-lg">
                <GripVertical className="h-4 w-4 text-blue-600" />
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold">{activeDrag.stop.customer}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {activeDrag.stop.weight || 0} kg
                  </p>
                </div>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      {/* Transfer suggestions */}
      {hasRoutes && suggestions.length > 0 && (
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-base font-bold">
            <Lightbulb className="h-4 w-4" />
            คำแนะนำการย้าย
            <Badge variant="secondary">{suggestions.length} รายการ</Badge>
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
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {s.stop.address}
                    </span>
                    <span className="flex items-center gap-1">
                      <Scale className="h-3.5 w-3.5" />
                      {s.stop.weight} kg
                    </span>
                  </p>

                  <div className="flex flex-wrap items-center gap-3">
                    <div className="min-w-[200px] flex-1 rounded-lg bg-red-50 p-3">
                      <p className="mb-1 flex items-center gap-1 text-xs font-bold text-red-600">
                        <Truck className="h-3.5 w-3.5" />
                        ต้นทาง
                      </p>
                      <p className="text-[13px] font-semibold">
                        คันที่ {s.source_vehicle_id} ({s.source_driver})
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {s.source_weight_before}kg → <strong>{s.source_weight_after}kg</strong>{' '}
                        ({s.source_pct_before}% → {s.source_pct_after}%)
                      </p>
                    </div>

                    <ArrowRight className="h-5 w-5 shrink-0 text-muted-foreground" />

                    <div className="min-w-[200px] flex-1 rounded-lg bg-emerald-50 p-3">
                      <p className="mb-1 flex items-center gap-1 text-xs font-bold text-emerald-600">
                        <Truck className="h-3.5 w-3.5" />
                        ปลายทาง
                      </p>
                      <p className="text-[13px] font-semibold">
                        คันที่ {s.target.target_vehicle_id} ({s.target.target_driver})
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {s.target.target_weight}kg → <strong>{s.target.new_target_weight}kg</strong>{' '}
                        ({s.target.target_weight_pct}% → {s.target.new_target_pct}%)
                      </p>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button
                      variant="success"
                      onClick={() => handleSuggestionConfirm(s)}
                      disabled={executing === s.stop.id || !canTransfer}
                    >
                      {executing === s.stop.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <CheckCircle className="h-4 w-4" />
                      )}
                      {executing === s.stop.id ? 'กำลังย้าย...' : 'ยืนยันย้าย'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {hasRoutes && suggestions.length === 0 && (
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <CheckCircle className="h-9 w-9 text-emerald-600" />
            <p className="text-base font-semibold text-emerald-700">สมดุลดีแล้ว!</p>
            <p className="text-sm text-muted-foreground">ไม่มีรถที่ต้องย้ายภาระในขณะนี้</p>
          </CardContent>
        </Card>
      )}

      {/* Transfer history */}
      {transferHistory.length > 0 && (
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
                      <span className="flex items-center gap-1">
                        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                        คันที่ {t.to_vehicle_id}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{t.reason || '-'}</TableCell>
                    <TableCell>{t.approved_by}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Confirm transfer */}
      <AlertDialog
        open={Boolean(pendingTransfer)}
        onOpenChange={(open) => !open && setPendingTransfer(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-blue-600" />
              ยืนยันการย้ายจุดจอด
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm">
                <p>
                  ย้ายจุดจอด <strong>{pendingTransfer?.stopLabel}</strong>
                </p>
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
              <XCircle className="h-4 w-4" />
              ยกเลิก
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                if (pendingTransfer) executeTransfer(pendingTransfer)
              }}
              disabled={Boolean(executing)}
            >
              {executing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
              {executing ? 'กำลังย้าย...' : 'ยืนยันย้าย'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
