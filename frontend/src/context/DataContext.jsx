import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { loadPersistedState, savePersistedState, clearPersistedState, getTodayKey } from "@/lib/persist"

const DataContext = createContext(null)

export function DataProvider({ children }) {
  // คืนค่าจาก localStorage ถ้าวันนี้เหมือนกัน (รีเฟรชไม่หาย, ขึ้นวันใหม่หาย)
  const [initial] = useState(() => loadPersistedState())

  const [orders, setOrders] = useState(initial?.orders || [])
  const [routes, setRoutes] = useState(initial?.routes || [])
  const [deferredInfo, setDeferredInfo] = useState(initial?.deferredInfo || null)
  const navigate = useNavigate()

  const fetchTodayData = useCallback(async () => {
    try {
      const [resOrders, resRoutes] = await Promise.all([
        fetch('/api/v1/orders/today'),
        fetch('/api/v1/routes/today'),
      ])
      if (resOrders.ok) {
        const dataOrders = await resOrders.json()
        if (dataOrders.orders && dataOrders.orders.length > 0) {
          setOrders(dataOrders.orders)
        }
      }
      if (resRoutes.ok) {
        const dataRoutes = await resRoutes.json()
        if (dataRoutes.routes && dataRoutes.routes.length > 0) {
          setRoutes(dataRoutes.routes)
        }
      }
    } catch {
      // silent
    }
  }, [])

  const planRoutes = useCallback(async (ordersToPlan) => {
    try {
      const response = await fetch('/api/v1/plan-routes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orders: ordersToPlan }),
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Server error: ${response.status}`)
      }
      const data = await response.json()
      setRoutes(data.routes)
      setDeferredInfo(
        data.deferred_count > 0
          ? { orders: data.deferred_orders || [], weight: data.deferred_weight || 0, count: data.deferred_count || 0 }
          : null
      )
      navigate('/routes')
      return data
    } catch (err) {
      toast.error(err.message || 'เกิดข้อผิดพลาดในการคำนวณเส้นทาง')
      throw err
    }
  }, [navigate])

  const clearAllData = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/clear-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: 'CLEAR_ALL_DATA' }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Server error: ${res.status}`)
      }
      setOrders([])
      setRoutes([])
      setDeferredInfo(null)
      clearPersistedState()
      toast.success('ล้างข้อมูลทั้งหมดในระบบเรียบร้อยแล้ว')
      navigate('/upload')
    } catch (err) {
      toast.error(`ไม่สามารถล้างข้อมูลได้: ${err.message}`)
    }
  }, [navigate])

  const setLocationVerified = useCallback((orderId, lat, lng) => {
    setOrders((prev) => prev.map((o) =>
      o.id === orderId ? { ...o, lat, lng, verified_lat: lat, verified_lng: lng, is_verified: true } : o
    ))
    setRoutes((prev) => prev.map((r) => ({
      ...r,
      stops: (r.stops || []).map((s) =>
        (s.id === orderId || s.order_id === orderId) ? { ...s, lat, lng, verified_lat: lat, verified_lng: lng, is_verified: true } : s
      ),
    })))
  }, [])

  // บันทึกสถานะลง localStorage ทุกครั้งที่มีการเปลี่ยน (พร้อมวันที่)
  useEffect(() => {
    savePersistedState(orders, routes, deferredInfo)
  }, [orders, routes, deferredInfo])

  // ตรวจสอบว่าขึ้นวันใหม่หรือยัง → ถ้าใช่ ล้างข้อมูลทั้งหมด
  useEffect(() => {
    const checkNewDay = () => {
      const persisted = loadPersistedState()
      if (!persisted) {
        // วันใหม่ หรือไม่มีข้อมูล → ล้าง state
        setOrders([])
        setRoutes([])
        setDeferredInfo(null)
      }
    }
    // เช็คทุก 1 นาที
    const interval = setInterval(checkNewDay, 60 * 1000)
    // เช็คเมื่อกลับมาที่แท็บ (tab visibility)
    const onVisible = () => {
      if (document.visibilityState === "visible") checkNewDay()
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => {
      clearInterval(interval)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [])

  return (
    <DataContext.Provider
      value={{
        orders, setOrders, routes, setRoutes, deferredInfo, setDeferredInfo,
        fetchTodayData, planRoutes, clearAllData, setLocationVerified,
      }}
    >
      {children}
    </DataContext.Provider>
  )
}

export function useData() {
  return useContext(DataContext)
}
