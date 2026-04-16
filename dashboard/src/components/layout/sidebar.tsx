import { cn } from "@/lib/utils"
import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  TrendingUp,
  Target,
  BarChart3,
  Activity,
} from "lucide-react"
import { useEffect, useState } from "react"
import { getHealth } from "@/lib/api"

const navItems = [
  { label: "Visao Geral", href: "/", icon: LayoutDashboard },
  { label: "Forex", href: "/forex", icon: TrendingUp },
  { label: "Binarias", href: "/binary", icon: Target },
  { label: "Estatisticas", href: "/stats", icon: BarChart3 },
]

export function Sidebar() {
  const [healthy, setHealthy] = useState<boolean | null>(null)

  useEffect(() => {
    getHealth()
      .then((h) => setHealthy(h.status === "healthy"))
      .catch(() => setHealthy(false))

    const id = setInterval(() => {
      getHealth()
        .then((h) => setHealthy(h.status === "healthy"))
        .catch(() => setHealthy(false))
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <aside
      className="fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r border-border"
      style={{ background: "var(--gradient-sidebar)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
          <Activity className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-foreground">DailyAgent</h1>
          <span className="text-[10px] text-muted-foreground font-mono">v2.0</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            end={item.href === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Status */}
      <div className="border-t border-border px-5 py-4">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={cn(
              "status-dot",
              healthy === true && "status-dot-active",
              healthy === false && "status-dot-inactive",
              healthy === null && "bg-warn animate-pulse"
            )}
          />
          <span className="text-muted-foreground">
            {healthy === true && "API Online"}
            {healthy === false && "API Offline"}
            {healthy === null && "Conectando..."}
          </span>
        </div>
      </div>
    </aside>
  )
}
