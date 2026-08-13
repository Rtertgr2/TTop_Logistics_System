import { useState, useEffect, useMemo, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { useData } from "@/context/DataContext"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import SearchInput from "@/components/SearchInput"
import DeferredOrdersCard from "@/components/DeferredOrdersCard"
import { Calendar, Package, MapPin, Truck, Loader2 } from "lucide-react"

export default function BookingDashboard() {
  const { user } = useAuth()
  const { deferredInfo } = useData()
  const navigate = useNavigate()
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState([])
  const [deliveryDate, setDeliveryDate] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [assigningNext, setAssigningNext] = useState(false)
  const [savingIds, setSavingIds] = useState(new Set())

  useEffect(() => {
    loadOrders()
  }, [])

  const loadOrders = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/v1/orders/today')
      if (res.ok) {
        const data = await res.json()
        setOrders(data.orders || [])
      }
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  // มอบหมายออเดอร์ที่เกินความจุรถ (deferred) ไปวันถัดไปในคลิกเดียว
  const assignNextDay = async () => {
    if (!deferredInfo?.orders?.length) return
    const t = new Date()
    t.setDate(t.getDate() + 1)
    const nextDate = t.toISOString().slice(0, 10)
    setAssigningNext(true)
    try {
      const res = await fetch('/api/v1/orders/assign-date', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_ids: deferredInfo.orders.map((o) => Number(o.id)),
          delivery_date: nextDate,
        }),
      })
      if (res.ok) {
        toast.success(`มอบหมายออเดอร์ ${deferredInfo.orders.length} รายการไปวันที่ ${nextDate} เรียบร้อยแล้ว`)
        loadOrders()
      } else {
        toast.error('ไม่สามารถมอบหมายวันถัดไปได้')
      }
    } catch {
      toast.error('เกิดข้อผิดพลาดในการมอบหมาย')
    } finally {
      setAssigningNext(false)
    }
  }

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase().trim()
    return orders.filter(o =>
      !q ||
      (o.customer || '').toLowerCase().includes(q) ||
      (o.order_number || '').toLowerCase().includes(q) ||
      (o.address || '').toLowerCase().includes(q)
    )
  }, [orders, searchQuery])

  const groupedByDate = useMemo(() => {
    const groups = {}
    filtered.forEach(o => {
      const d = o.delivery_date || 'ไม่ระบุ'
      if (!groups[d]) groups[d] = []
      groups[d].push(o)
    })
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0]))
  }, [filtered])

  const toggleSelect = (id) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const assignDate = async (date) => {
    if (selectedIds.length === 0) return
    try {
      const res = await fetch('/api/v1/orders/assign-date', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_ids: selectedIds.map(Number), delivery_date: date }),
      })
      if (res.ok) {
        const data = await res.json()
        toast.success(`มอบหมายวันส่ง ${data.updated || selectedIds.length} รายการเรียบร้อยแล้ว`)
        setSelectedIds([])
        loadOrders()
      } else {
        toast.error('ไม่สามารถมอบหมายวันส่งได้')
      }
    } catch {
      toast.error('เกิดข้อผิดพลาดในการมอบหมาย')
    }
  }

  const handleDateChange = useCallback(async (orderId, newDate) => {
    if (!newDate) return
    setSavingIds(prev => new Set(prev).add(orderId))
    try {
      const res = await fetch('/api/v1/orders/assign-date', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_ids: [Number(orderId)], delivery_date: newDate }),
      })
      if (res.ok) {
        setOrders(prev => prev.map(o => o.id === orderId ? { ...o, delivery_date: newDate } : o))
        toast.success(`บันทึกวันส่ง ${newDate} เรียบร้อยแล้ว`)
      } else {
        toast.error('ไม่สามารถบันทึกวันส่งได้')
      }
    } catch {
      toast.error('เกิดข้อผิดพลาดในการบันทึก')
    } finally {
      setSavingIds(prev => {
        const next = new Set(prev)
        next.delete(orderId)
        return next
      })
    }
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">จัดการวันส่ง</h1>
          <p className="text-sm text-muted-foreground">กำหนดวันจัดส่งสำหรับออเดอร์</p>
        </div>
      </div>

      <DeferredOrdersCard
        deferredInfo={deferredInfo}
        onAssignNextDay={assignNextDay}
        assigningNext={assigningNext}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <SearchInput
          wrapperClassName="relative flex-1 max-w-sm"
          placeholder="ค้นหาชื่อลูกค้า หรือเลขที่ SO..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <div className="flex items-center gap-2">
          <Input type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} className="w-auto" />
          <Button onClick={() => assignDate(deliveryDate)} disabled={!deliveryDate || selectedIds.length === 0}>
            <Calendar className="h-4 w-4" />
            มอบหมาย {selectedIds.length} รายการ
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <Tabs defaultValue="list">
          <TabsList>
            <TabsTrigger value="list">รายการ (ตาราง)</TabsTrigger>
            <TabsTrigger value="calendar">ปฏิทิน</TabsTrigger>
          </TabsList>
          <TabsContent value="list">
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10"></TableHead>
                      <TableHead>ลูกค้า</TableHead>
                      <TableHead>เลขที่ SO</TableHead>
                      <TableHead>ที่อยู่</TableHead>
                      <TableHead>วันส่ง</TableHead>
                      <TableHead>น้ำหนัก</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((o) => (
                      <TableRow key={o.id}>
                        <TableCell>
                          <Checkbox checked={selectedIds.includes(o.id)} onCheckedChange={() => toggleSelect(o.id)} />
                        </TableCell>
                        <TableCell className="font-medium">{o.customer}</TableCell>
                        <TableCell>{o.order_number}</TableCell>
                        <TableCell className="max-w-xs truncate text-muted-foreground">{o.address}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Input
                              type="date"
                              value={o.delivery_date || ''}
                              onChange={(e) => handleDateChange(o.id, e.target.value)}
                              disabled={savingIds.has(o.id)}
                              className="h-8 w-[140px] text-xs"
                            />
                            {savingIds.has(o.id) && (
                              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{o.weight} kg</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="calendar">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {groupedByDate.map(([date, items]) => (
                <Card key={date}>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Calendar className="h-4 w-4 text-primary" />
                      {date}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {items.map((o) => (
                      <div key={o.id} className="flex items-center gap-2 rounded-md border p-2 text-sm">
                        <Package className="h-4 w-4 text-muted-foreground" />
                        <span className="flex-1 truncate">{o.customer}</span>
                        <Badge variant="outline">{o.weight} kg</Badge>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
