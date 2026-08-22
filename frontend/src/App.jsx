import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider, RequireAuth } from "@/context/AuthContext"
import { DataProvider } from "@/context/DataContext"
import AppLayout from "@/components/AppLayout"
import LoginScreen from "@/components/LoginScreen"
import Dashboard from "@/components/Dashboard"
import FileUpload from "@/components/FileUpload"
import Orders from "@/components/Orders"
import RouteResult from "@/components/RouteResult"
import VehicleManager from "@/components/VehicleManager"
import DriverMobile from "@/components/DriverMobile"
import LoadBalancer from "@/components/LoadBalancer"
import BookingDashboard from "@/components/BookingDashboard"
import AdminDashboard from "@/components/AdminDashboard"
import EmployeeManager from "@/components/EmployeeManager"
import DatabaseViewer from "@/components/DatabaseViewer"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <DataProvider>
          <Routes>
            <Route path="/login" element={<LoginScreen />} />
            <Route
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="upload" element={<FileUpload />} />
              <Route path="orders" element={<Orders />} />
              <Route path="routes" element={<RouteResult />} />
              <Route path="vehicles" element={<VehicleManager />} />
              <Route path="driver" element={<DriverMobile />} />
              <Route path="load-balance" element={<LoadBalancer />} />
              <Route path="booking" element={<BookingDashboard />} />
              <Route path="admin" element={<AdminDashboard />} />
              <Route path="employees" element={<EmployeeManager />} />
              <Route path="database" element={<DatabaseViewer />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </DataProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
