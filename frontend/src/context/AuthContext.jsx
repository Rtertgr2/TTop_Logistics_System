import { createContext, useContext, useState, useEffect } from "react"
import { getToken, setToken, logout as doLogout } from "@/api"
import LoginScreen from "@/components/LoginScreen"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    const restoreSession = async () => {
      if (!getToken()) {
        setAuthChecked(true)
        return
      }
      try {
        const res = await fetch('/api/v1/auth/me')
        if (res.ok) {
          const data = await res.json()
          setUser(data.user)
        } else if (res.status === 401 || res.status === 403) {
          setToken(null)
        }
      } catch {
        // network error — keep token
      } finally {
        setAuthChecked(true)
      }
    }
    restoreSession()

    // ฟัง event เมื่อ token หมดอายุหรือถูก logout จาก component อื่น
    const onUnauthorized = () => {
      setToken(null)
      setUser(null)
    }
    window.addEventListener('auth:unauthorized', onUnauthorized)
    window.addEventListener('auth:logout', onUnauthorized)
    return () => {
      window.removeEventListener('auth:unauthorized', onUnauthorized)
      window.removeEventListener('auth:logout', onUnauthorized)
    }
  }, [])

  const login = (data) => {
    setToken(data.access_token)
    setUser(data.user)
  }

  const logout = () => {
    doLogout()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, authChecked, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function RequireAuth({ children }) {
  const { user, authChecked, login } = useAuth()

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!user) {
    return <LoginScreen onLoginSuccess={login} />
  }

  return children
}
