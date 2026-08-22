import { useState, useEffect } from "react"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import {
  Bell,
  BellOff,
  CheckCheck,
  Loader2,
  XCircle,
  Clock,
  Truck,
  AlertTriangle,
  MapPin,
  Scale,
  CheckCircle2,
  RefreshCw,
  Info,
} from "lucide-react"

const TYPE_CONFIG = {
  DELIVERY_FAILED: { icon: XCircle, color: "text-red-600", bg: "bg-red-50" },
  DELIVERY_DELAYED: { icon: Clock, color: "text-amber-600", bg: "bg-amber-50" },
  VEHICLE_IDLE: { icon: Truck, color: "text-blue-600", bg: "bg-blue-50" },
  VEHICLE_OVERFLOW: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50" },
  ROUTE_DEVIATION: { icon: MapPin, color: "text-amber-600", bg: "bg-amber-50" },
  TRANSFER_SUGGESTED: { icon: Scale, color: "text-purple-600", bg: "bg-purple-50" },
  TRANSFER_EXECUTED: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
  STOP_RESCHEDULED: { icon: RefreshCw, color: "text-sky-600", bg: "bg-sky-50" },
  SYSTEM_ALERT: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50" },
}

const PRIORITY_BADGE = {
  high: { variant: "danger", label: "ด่วน" },
  medium: { variant: "warning", label: "ปานกลาง" },
  low: { variant: "secondary", label: "ทั่วไป" },
}

const DEFAULT_TYPE = { icon: Info, color: "text-slate-600", bg: "bg-slate-100" }

function formatTime(iso) {
  if (!iso) return ""
  const d = new Date(iso)
  const diffMin = Math.floor((Date.now() - d.getTime()) / 60000)
  if (diffMin < 1) return "เมื่อสักครู่"
  if (diffMin < 60) return `${diffMin} นาทีที่แล้ว`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} ชม. ที่แล้ว`
  return d.toLocaleDateString("th-TH")
}

export default function NotificationPanel({ className, align = "end" }) {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchUnreadCount = async () => {
    try {
      const res = await fetch("/api/v1/notifications/unread-count")
      if (res.ok) {
        const data = await res.json()
        setUnreadCount(data.unread_count || 0)
      }
    } catch { /* ignore */ }
  }

  const fetchNotifications = async () => {
    setLoading(true)
    try {
      const res = await fetch("/api/v1/notifications?limit=30")
      if (res.ok) {
        const data = await res.json()
        setNotifications(data.notifications || [])
      }
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  const handleOpenChange = (next) => {
    setOpen(next)
    if (next) fetchNotifications()
  }

  const markRead = async (id) => {
    const prev = notifications
    const prevCount = unreadCount
    setNotifications((p) => p.map((n) => (n.id === id ? { ...n, read: true } : n)))
    setUnreadCount((p) => Math.max(0, p - 1))
    try {
      const res = await fetch(`/api/v1/notifications/${id}/read`, { method: "PUT" })
      if (!res.ok) throw new Error("Failed")
    } catch {
      setNotifications(prev) // rollback
      setUnreadCount(prevCount) // rollback
    }
  }

  const markAllRead = async () => {
    const prev = notifications
    const prevCount = unreadCount
    setNotifications((p) => p.map((n) => ({ ...n, read: true })))
    setUnreadCount(0)
    try {
      const res = await fetch("/api/v1/notifications/mark-all-read", { method: "PUT" })
      if (!res.ok) throw new Error("Failed")
    } catch {
      setNotifications(prev) // rollback
      setUnreadCount(prevCount) // rollback
    }
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="การแจ้งเตือน"
          className={cn("relative shrink-0", className)}
        >
          <Bell className={cn("h-5 w-5", unreadCount > 0 && "text-blue-600")} />
          {unreadCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-bold leading-none text-white ring-2 ring-background">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent align={align} sideOffset={8} className="w-[380px] max-w-[calc(100vw-2rem)] p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-blue-600" />
            <h3 className="text-sm font-bold">การแจ้งเตือน</h3>
            {unreadCount > 0 && (
              <Badge variant="info" className="px-1.5 py-0 text-[10px]">
                {unreadCount > 99 ? "99+" : unreadCount} ใหม่
              </Badge>
            )}
          </div>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={markAllRead}
              className="h-7 gap-1 px-2 text-xs font-semibold text-blue-600 hover:bg-blue-50 hover:text-blue-700"
            >
              <CheckCheck className="h-3.5 w-3.5" />
              อ่านทั้งหมด
            </Button>
          )}
        </div>

        <Separator />

        <ScrollArea className="max-h-[400px]">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              กำลังโหลด...
            </div>
          )}

          {!loading && notifications.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
              <BellOff className="h-10 w-10 opacity-40" />
              <p className="text-sm">ไม่มีการแจ้งเตือน</p>
            </div>
          )}

          {!loading &&
            notifications.map((n) => {
              const cfg = TYPE_CONFIG[n.type] || DEFAULT_TYPE
              const Icon = cfg.icon
              const priority = PRIORITY_BADGE[n.priority]
              return (
                <button
                  key={n.id}
                  type="button"
                  disabled={n.read}
                  onClick={() => !n.read && markRead(n.id)}
                  className={cn(
                    "flex w-full items-start gap-3 border-b px-4 py-3 text-left transition-colors last:border-b-0",
                    n.read ? "bg-background" : "bg-blue-50/60 hover:bg-blue-50"
                  )}
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                      cfg.bg
                    )}
                  >
                    <Icon className={cn("h-4 w-4", cfg.color)} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={cn(
                          "truncate text-[13px] text-slate-900",
                          n.read ? "font-medium" : "font-bold"
                        )}
                      >
                        {n.title}
                      </span>
                      {!n.read && (
                        <span className="h-2 w-2 shrink-0 rounded-full bg-blue-600" />
                      )}
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {n.message}
                    </p>
                    <div className="mt-1.5 flex items-center gap-2">
                      <span className="text-[11px] text-muted-foreground">
                        {formatTime(n.created_at)}
                      </span>
                      {priority && n.priority !== "low" && (
                        <Badge variant={priority.variant} className="px-1.5 py-0 text-[10px]">
                          {priority.label}
                        </Badge>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )
}
