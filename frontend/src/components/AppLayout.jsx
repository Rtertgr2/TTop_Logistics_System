import { Outlet } from "react-router-dom"
import Sidebar from "@/components/Sidebar"
import { useAuth } from "@/context/AuthContext"
import { Toaster } from "@/components/ui/sonner"

function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar user={user} onLogout={logout} />
      <main className="flex-1 overflow-x-hidden pt-16 md:pt-0">
        <div className="mx-auto max-w-7xl px-4 py-6 md:px-8">
          <Outlet />
        </div>
      </main>
      <Toaster />
    </div>
  )
}

export default AppLayout
