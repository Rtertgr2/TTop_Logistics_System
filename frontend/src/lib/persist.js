const STORAGE_KEY = "logistics_app_state_v1"

export function getTodayKey() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

export function loadPersistedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object" || parsed.date !== getTodayKey()) {
      // วันใหม่ หรือข้อมูลเสีย → ทิ้งทั้งหมด
      localStorage.removeItem(STORAGE_KEY)
      return null
    }
    return {
      orders: Array.isArray(parsed.orders) ? parsed.orders : [],
      routes: Array.isArray(parsed.routes) ? parsed.routes : [],
      deferredInfo: parsed.deferredInfo || null,
    }
  } catch {
    return null
  }
}

export function savePersistedState(orders, routes, deferredInfo) {
  try {
    const payload = {
      date: getTodayKey(),
      orders,
      routes,
      deferredInfo,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // ignore quota / private mode errors
  }
}

export function clearPersistedState() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
