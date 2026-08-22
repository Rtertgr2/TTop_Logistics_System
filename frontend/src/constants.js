// Shared constants and helpers for the Logistics frontend.
// Centralises values previously duplicated across multiple components.

/** Main depot coordinates (คลังสินค้าหลัก) */
export const DEPOT_COORDS = { lat: 13.781882, lng: 100.425041 }

/** Default vehicle capacity in kg (previously hardcoded as 3750 in 15+ places) */
export const DEFAULT_VEHICLE_CAPACITY = 3750

/** Palette used to colour routes/vehicles on the maps */
export const VEHICLE_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
  "#06b6d4",
]

/** Tailwind background classes mirroring VEHICLE_COLORS (for non-map UI) */
export const VEHICLE_COLOR_CLASSES = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-purple-500",
]

/** Capacity threshold (%) above which a drop is rejected */
export const CAPACITY_LIMIT_PCT = 95

/**
 * Delivery-status presentation config.
 * Merged from Dashboard.jsx and DriverMobile.jsx (they used the same keys
 * with slightly different shapes). Includes both `color` (used by Dashboard)
 * and `icon`/`border`/`text` (used by DriverMobile).
 */
import {
  Clock,
  Truck,
  MapPin,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
} from "lucide-react"

export const DELIVERY_STATUS_CONFIG = {
  PENDING: { label: "รอจัดส่ง", color: "#64748b", variant: "secondary", icon: Clock, border: "border-l-slate-400", text: "text-slate-600" },
  IN_TRANSIT: { label: "กำลังขนส่ง", color: "#3b82f6", variant: "info", icon: Truck, border: "border-l-blue-500", text: "text-blue-600" },
  ARRIVED: { label: "ถึงจุดส่งแล้ว", color: "#f59e0b", variant: "warning", icon: MapPin, border: "border-l-amber-500", text: "text-amber-600" },
  DELIVERED: { label: "ส่งสำเร็จ", color: "#16a34a", variant: "success", icon: CheckCircle2, border: "border-l-emerald-500", text: "text-emerald-600" },
  FAILED: { label: "ไม่สำเร็จ", color: "#dc2626", variant: "danger", icon: XCircle, border: "border-l-red-500", text: "text-red-600" },
  PARTIAL: { label: "ส่งบางส่วน", color: "#9333ea", variant: "purple", icon: AlertTriangle, border: "border-l-purple-500", text: "text-purple-600" },
  RESCHEDULED: { label: "เลื่อนจัดส่ง", color: "#0891b2", variant: "info", icon: RefreshCw, border: "border-l-cyan-500", text: "text-cyan-600" },
}

/**
 * Capacity-status presentation config (previously duplicated in
 * RouteResult.jsx and LoadBalancer.jsx).
 */
export const CAPACITY_STATUS_CONFIG = {
  overflow: { label: "รถเต็ม", variant: "danger", bar: "bg-red-500", ring: "border-red-200" },
  high: { label: "ใกล้เต็ม", variant: "warning", bar: "bg-amber-500", ring: "border-amber-200" },
  normal: { label: "ปกติ", variant: "success", bar: "bg-emerald-500", ring: "border-emerald-200" },
  underflow: { label: "รถว่าง", variant: "info", bar: "bg-blue-500", ring: "border-blue-200" },
}

export function capacityCfgOf(status) {
  return CAPACITY_STATUS_CONFIG[status] || CAPACITY_STATUS_CONFIG.normal
}

/** Weight as a percentage of capacity, rounded to 1 decimal place */
export function pctOf(weight, capacity) {
  if (!capacity || capacity <= 0) return 0
  return Math.round((weight / capacity) * 1000) / 10
}
