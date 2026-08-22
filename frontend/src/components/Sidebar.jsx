import { useNavigate, useLocation } from "react-router-dom"
import { getMenuItemsForRole } from "@/permissions"
import { useAuth } from "@/context/AuthContext"
import { LogOut, Menu, LayoutDashboard, Upload, FileText, Calendar, Map, Truck, Smartphone, Scale, BarChart3, Users, Database } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"

const ICON_MAP = {
  dashboard: LayoutDashboard,
  upload: Upload,
  orders: FileText,
  booking: Calendar,
  routes: Map,
  vehicles: Truck,
  driver: Smartphone,
  'load-balance': Scale,
  admin: BarChart3,
  employees: Users,
  database: Database,
}

function SidebarContent({ user, onLogout, onClearData }) {
  const navigate = useNavigate()
  const location = useLocation()
  const role = user?.role || 'user'
  const menuItems = getMenuItemsForRole(role)
  const currentPath = location.pathname

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-3 border-b border-sidebar-border px-6 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary shadow-lg">
          <Truck className="h-6 w-6 text-primary-foreground" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight">Route Planner</h1>
          <p className="text-xs text-sidebar-foreground/60">Logistics System</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {menuItems.map((item) => {
          const Icon = ICON_MAP[item.id] || LayoutDashboard
          const isActive = currentPath === `/${item.id}` || (item.id === 'dashboard' && currentPath === '/')
          return (
            <button
              key={item.id}
              onClick={() => navigate(`/${item.id === 'dashboard' ? '' : item.id}`)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary text-primary-foreground shadow'
                  : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
              }`}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </button>
          )
        })}
      </nav>

      <div className="space-y-2 border-t border-sidebar-border px-3 py-4">
        {user && (
          <div className="flex items-center gap-3 rounded-lg px-3 py-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sidebar-accent text-sm font-semibold">
              {(user.name || user.username)?.charAt(0)?.toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user.name || user.username}</p>
              <p className="text-xs text-sidebar-foreground/60">{user.role}</p>
            </div>
          </div>
        )}
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          onClick={onLogout}
        >
          <LogOut className="h-5 w-5" />
          ออกจากระบบ
        </Button>
      </div>
    </div>
  )
}

function Sidebar({ user, onLogout, onClearData }) {
  return (
    <>
      {/* Desktop */}
      <aside className="hidden w-64 shrink-0 md:block">
        <div className="fixed h-screen w-64">
          <SidebarContent user={user} onLogout={onLogout} onClearData={onClearData} />
        </div>
      </aside>

      {/* Mobile */}
      <div className="fixed left-4 top-4 z-50 md:hidden">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" className="bg-background shadow">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>เมนูนำทาง</SheetTitle>
            </SheetHeader>
            <SidebarContent user={user} onLogout={onLogout} onClearData={onClearData} />
          </SheetContent>
        </Sheet>
      </div>
    </>
  )
}

export default Sidebar
