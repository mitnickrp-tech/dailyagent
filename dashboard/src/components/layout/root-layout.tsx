import { Sidebar } from "@/components/layout/sidebar"
import { Outlet } from "react-router-dom"

export function RootLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="pl-56">
        <div className="p-6 max-w-[1400px] mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
