import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { AlertTriangle } from "lucide-react"

/**
 * Amber alert card listing orders that exceeded vehicle capacity and were
 * deferred to the next day. Previously duplicated in BookingDashboard and
 * RouteResult. Pass `onAssignNextDay` to render the assign-next-day action.
 */
export default function DeferredOrdersCard({ deferredInfo, onAssignNextDay, assigningNext = false }) {
  if (!deferredInfo || deferredInfo.count <= 0) return null

  return (
    <Card className="border-amber-300 bg-amber-50">
      <CardHeader className="flex flex-row items-start gap-3 space-y-0">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100">
          <AlertTriangle className="h-5 w-5 text-amber-700" />
        </div>
        <div className="flex-1 space-y-1">
          <CardTitle className="text-base text-amber-800">ออเดอร์เกินความจุรถ — เลื่อนส่งวันถัดไป</CardTitle>
          <p className="text-sm text-amber-900">
            ออเดอร์ <strong>{deferredInfo.count} รายการ</strong> น้ำหนักรวม{" "}
            <strong>{(deferredInfo.weight || 0).toLocaleString()} kg</strong> จะถูกส่งในวันถัดไป
            เนื่องจากน้ำหนักรวมเกินความจุรถที่มี
          </p>
          {onAssignNextDay && (
            <Button
              size="sm"
              className="mt-2 bg-amber-600 text-white hover:bg-amber-700"
              onClick={onAssignNextDay}
              disabled={assigningNext}
            >
              {assigningNext ? "กำลังมอบหมาย..." : "มอบหมายวันถัดไปให้ออเดอร์เหล่านี้"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-amber-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow className="bg-amber-100 hover:bg-amber-100">
                <TableHead className="w-16">ลำดับ</TableHead>
                <TableHead>เลขที่ SO</TableHead>
                <TableHead>ลูกค้า</TableHead>
                <TableHead className="text-right">น้ำหนัก (kg)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(deferredInfo.orders || []).map((o, i) => (
                <TableRow key={o.id ?? i}>
                  <TableCell>{i + 1}</TableCell>
                  <TableCell>{o.order_number || "-"}</TableCell>
                  <TableCell>{o.customer || "-"}</TableCell>
                  <TableCell className="text-right">{o.weight || 0}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
