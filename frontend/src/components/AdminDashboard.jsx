import { useState, useEffect, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import {
  BarChart3, MapPin, AlertTriangle, CheckCircle, Package,
  ShieldCheck, ShieldAlert, ShieldX, Map as MapIcon, Loader2
} from "lucide-react"

export default function AdminDashboard() {
  const [orders, setOrders] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [ordersRes, statusRes] = await Promise.all([
        fetch('/api/v1/orders-history?limit=500'),
        fetch('/api/v1/system-status'),
      ])
      if (ordersRes.ok) {
        const data = await ordersRes.json()
        setOrders(data.orders || [])
      }
      if (statusRes.ok) {
        setStats(await statusRes.json())
      }
    } catch (err) {
      console.error('Admin data load failed:', err)
    } finally {
      setLoading(false)
    }
  }

  const { zoneStats, qualityStats, lowConfidenceOrders } = useMemo(() => {
    const zoneMap = {}
    orders.forEach((o) => {
      const zone = o.zone || 'ไม่ระบุ'
      if (!zoneMap[zone]) {
        zoneMap[zone] = { count: 0, totalWeight: 0, confidenceSum: 0, avgConfidence: 0 }
      }
      const z = zoneMap[zone]
      z.count++
      z.totalWeight += Number(o.weight) || 0
      z.confidenceSum += Number(o.confidence_score) || 0
    })

    const zones = Object.entries(zoneMap)
      .map(([zone, z]) => {
        z.avgConfidence = z.count > 0 ? Math.round(z.confidenceSum / z.count) : 0
        return [zone, z]
      })
      .sort((a, b) => b[1].count - a[1].count)

    const quality = {
      total: orders.length,
      highConfidence: orders.filter((o) => (Number(o.confidence_score) || 0) >= 90).length,
      mediumConfidence: orders.filter((o) => {
        const c = Number(o.confidence_score) || 0
        return c >= 70 && c < 90
      }).length,
      lowConfidence: orders.filter((o) => (Number(o.confidence_score) || 0) < 70).length,
      verified: orders.filter((o) => o.is_verified).length,
      unverified: orders.filter((o) => !o.is_verified).length,
    }

    const low = orders
      .filter((o) => (Number(o.confidence_score) || 0) < 70)
      .slice(0, 20)

    return { zoneStats: zones, qualityStats: quality, lowConfidenceOrders: low }
  }, [orders])

  const filteredLow = useMemo(() => {
    if (!search) return lowConfidenceOrders
    const q = search.toLowerCase()
    return lowConfidenceOrders.filter(
      (o) => (o.customer || '').toLowerCase().includes(q) || (o.address || '').toLowerCase().includes(q)
    )
  }, [lowConfidenceOrders, search])

  const qualityCards = [
    {
      label: 'ออเดอร์ทั้งหมด',
      value: qualityStats.total,
      Icon: Package,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Confidence ≥ 90%',
      value: qualityStats.highConfidence,
      Icon: CheckCircle,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
    },
    {
      label: 'Confidence 70-90%',
      value: qualityStats.mediumConfidence,
      Icon: ShieldAlert,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
    },
    {
      label: 'Confidence < 70%',
      value: qualityStats.lowConfidence,
      Icon: ShieldX,
      color: 'text-red-600',
      bg: 'bg-red-50',
    },
    {
      label: 'ยืนยันพิกัดแล้ว',
      value: qualityStats.verified,
      Icon: ShieldCheck,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
  ]

  const qualityBadge = (avg) => {
    if (avg >= 90) return { label: 'ดี', variant: 'success' }
    if (avg >= 70) return { label: 'ปานกลาง', variant: 'warning' }
    return { label: 'ต่ำ', variant: 'danger' }
  }

  const qualityBar = (avg) => {
    if (avg >= 90) return 'bg-emerald-500'
    if (avg >= 70) return 'bg-amber-500'
    return 'bg-red-500'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        <p>กำลังโหลดข้อมูล Admin Dashboard...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <BarChart3 className="h-6 w-6 text-blue-600" />
          Admin Dashboard
        </h2>
        <p className="text-sm text-muted-foreground">
          รายงานคุณภาพการจับพิกัด และสถิติการจัดส่งแยกตามโซน
        </p>
      </div>

      {/* Quality Overview */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {qualityCards.map((s) => {
          const Icon = s.Icon
          return (
            <Card key={s.label}>
              <CardContent className="flex items-center gap-4 p-5">
                <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl", s.bg)}>
                  <Icon className={cn("h-5 w-5", s.color)} />
                </div>
                <div>
                  <p className="text-2xl font-bold">{s.value}</p>
                  <p className="text-xs font-medium text-muted-foreground">{s.label}</p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Zone Heatmap Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <MapIcon className="h-5 w-5 text-blue-600" />
            Location Quality Report — แยกตามโซน
          </CardTitle>
          <Badge variant="secondary">{zoneStats.length} โซน</Badge>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>โซน</TableHead>
                <TableHead>จำนวน</TableHead>
                <TableHead>น้ำหนักรวม</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>คุณภาพ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {zoneStats.map(([zone, data], idx) => {
                const badge = qualityBadge(data.avgConfidence)
                return (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-1.5">
                        <MapPin className="h-4 w-4 text-blue-500" />
                        {zone}
                      </span>
                    </TableCell>
                    <TableCell>{data.count} ออเดอร์</TableCell>
                    <TableCell>{data.totalWeight.toLocaleString()} kg</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={data.avgConfidence}
                          className="max-w-[80px]"
                          indicatorClassName={qualityBar(data.avgConfidence)}
                        />
                        <span className="text-xs font-bold">{data.avgConfidence}%</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={badge.variant}>{badge.label}</Badge>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Low Confidence Orders */}
      {qualityStats.lowConfidence > 0 && (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              ออเดอร์ที่ต้องตรวจสอบ (Confidence &lt; 70%)
            </CardTitle>
            <div className="w-full sm:w-64">
              <Label htmlFor="low-search" className="sr-only">ค้นหา</Label>
              <Input
                id="low-search"
                placeholder="ค้นหาชื่อลูกค้า หรือที่อยู่..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </CardHeader>
          <CardContent>
            <div className="max-h-[300px] overflow-y-auto">
              {filteredLow.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  ไม่พบออเดอร์ที่ตรงกับคำค้นหา
                </p>
              ) : (
                filteredLow.map((o, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between border-b border-border py-3 last:border-0"
                  >
                    <div>
                      <p className="text-sm font-semibold">{o.customer}</p>
                      <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                        <MapPin className="h-3.5 w-3.5" />
                        {o.address}
                      </p>
                    </div>
                    <Badge variant="danger">{Number(o.confidence_score) || 0}%</Badge>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
