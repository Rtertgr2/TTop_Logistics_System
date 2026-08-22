const TOKEN_KEY = 'logistics_access_token'

const originalFetch = window.fetch.bind(window)

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export function isAuthenticated() {
  return !!getToken()
}

export function logout() {
  setToken(null)
  window.dispatchEvent(new CustomEvent('auth:logout'))
}

export async function apiFetch(input, init = {}) {
  const headers = { ...(init.headers || {}) }
  const token = getToken()
  const url = typeof input === 'string' ? input : (input && input.url) || ''

  // แนบ token เฉพาะ same-origin request เท่านั้น (ป้องกัน token รั่วไป third-party)
  const isSameOrigin = url.startsWith('/') || url.startsWith(window.location.origin)
  if (token && isSameOrigin && !url.includes('/auth/login')) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await originalFetch(input, { ...init, headers })
  if (response.status === 401 && isSameOrigin && !url.includes('/auth/login')) {
    window.dispatchEvent(new CustomEvent('auth:unauthorized'))
  }
  return response
}

// Patch global fetch so all existing components send auth automatically
window.fetch = apiFetch

// Axios interceptor — so axios calls (Dashboard, FileUpload, RouteResult, VehicleManager, AdminDashboard)
// also receive the Authorization header and handle 401 correctly.
import('axios').then((axios) => {
  const client = axios.default || axios
  client.interceptors.request.use((config) => {
    const token = getToken()
    if (token && !(config.url || '').includes('/auth/login')) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response && error.response.status === 401 && !(error.config.url || '').includes('/auth/login')) {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
      return Promise.reject(error)
    }
  )
}).catch(() => {
  // axios not installed — skip interceptor
})
