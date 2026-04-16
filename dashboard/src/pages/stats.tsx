import { useEffect, useState, useCallback } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getBinaryStats } from "@/lib/api"
import type { BinaryStatsResponse } from "@/lib/types"
import { RefreshCw } from "lucide-react"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts"

const SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
const COLORS = {
  itm: "hsl(152, 69%, 45%)",
  otm: "hsl(0, 72%, 51%)",
  tie: "hsl(38, 92%, 50%)",
  open: "hsl(217, 91%, 60%)",
}

export function StatsPage() {
  const [days, setDays] = useState(30)
  const [allStats, setAllStats] = useState<BinaryStatsResponse | null>(null)
  const [symbolStats, setSymbolStats] = useState<(BinaryStatsResponse & { name: string })[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(() => {
    setLoading(true)
    const requests = [
      getBinaryStats(days),
      ...SYMBOLS.map((s) => getBinaryStats(days, s).then((r) => ({ ...r, name: s }))),
    ]
    Promise.allSettled(requests).then(([all, ...perSymbol]) => {
      if (all.status === "fulfilled") setAllStats(all.value as BinaryStatsResponse)
      const resolved = perSymbol
        .filter((r) => r.status === "fulfilled")
        .map((r) => (r as PromiseFulfilledResult<BinaryStatsResponse & { name: string }>).value)
      setSymbolStats(resolved)
      setLoading(false)
    })
  }, [days])

  useEffect(() => { fetchData() }, [fetchData])

  const pieData = allStats
    ? [
        { name: "ITM", value: allStats.itm, color: COLORS.itm },
        { name: "OTM", value: allStats.otm, color: COLORS.otm },
        { name: "TIE", value: allStats.tie, color: COLORS.tie },
        { name: "Aberto", value: allStats.open, color: COLORS.open },
      ].filter((d) => d.value > 0)
    : []

  const barData = symbolStats.map((s) => ({
    name: s.name,
    ITM: s.itm,
    OTM: s.otm,
    TIE: s.tie,
    "Win Rate": s.win_rate,
  }))

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground animate-pulse">Carregando...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Estatisticas</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Performance de sinais binarios e metricas de auditoria
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value={7}>7 dias</option>
            <option value={14}>14 dias</option>
            <option value={30}>30 dias</option>
            <option value={90}>90 dias</option>
          </select>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="h-3.5 w-3.5" />
            Atualizar
          </Button>
        </div>
      </div>

      {/* Highlight KPIs */}
      {allStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-5 text-center">
              <p className="text-3xl font-bold">{allStats.total}</p>
              <p className="text-xs text-muted-foreground mt-1">Total de Sinais</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 text-center">
              <p className={`text-3xl font-bold ${allStats.win_rate >= 55 ? "text-profit" : allStats.win_rate >= 45 ? "text-warn" : "text-loss"}`}>
                {allStats.win_rate}%
              </p>
              <p className="text-xs text-muted-foreground mt-1">Win Rate Geral</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 text-center">
              <p className="text-3xl font-bold text-profit">{allStats.itm}</p>
              <p className="text-xs text-muted-foreground mt-1">ITM (Acertos)</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 text-center">
              <p className="text-3xl font-bold text-loss">{allStats.otm}</p>
              <p className="text-xs text-muted-foreground mt-1">OTM (Erros)</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Distribuicao de Resultados</CardTitle>
          </CardHeader>
          <CardContent>
            {pieData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">Sem dados suficientes.</p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={3}
                    dataKey="value"
                    nameKey="name"
                    stroke="none"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "hsl(222 47% 8%)",
                      border: "1px solid hsl(217 33% 15%)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "hsl(210 40% 93%)",
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: "12px", color: "hsl(215 20% 55%)" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Bar Chart per Symbol */}
        <Card>
          <CardHeader>
            <CardTitle>Performance por Ativo</CardTitle>
          </CardHeader>
          <CardContent>
            {barData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">Sem dados suficientes.</p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="hsl(217 33% 15%)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: "hsl(215 20% 55%)" }}
                    axisLine={{ stroke: "hsl(217 33% 15%)" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "hsl(215 20% 55%)" }}
                    axisLine={{ stroke: "hsl(217 33% 15%)" }}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(222 47% 8%)",
                      border: "1px solid hsl(217 33% 15%)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "hsl(210 40% 93%)",
                    }}
                  />
                  <Bar dataKey="ITM" fill={COLORS.itm} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="OTM" fill={COLORS.otm} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="TIE" fill={COLORS.tie} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Per-Symbol Table */}
      <Card>
        <CardHeader>
          <CardTitle>Detalhamento por Ativo</CardTitle>
        </CardHeader>
        <CardContent>
          {symbolStats.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem dados.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wider">
                    <th className="pb-3 pr-6">Ativo</th>
                    <th className="pb-3 pr-6">Total</th>
                    <th className="pb-3 pr-6">ITM</th>
                    <th className="pb-3 pr-6">OTM</th>
                    <th className="pb-3 pr-6">TIE</th>
                    <th className="pb-3 pr-6">Abertos</th>
                    <th className="pb-3">Win Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {symbolStats.map((s) => (
                    <tr key={s.name}>
                      <td className="py-3 pr-6 font-mono font-medium">{s.name}</td>
                      <td className="py-3 pr-6">{s.total}</td>
                      <td className="py-3 pr-6 text-profit font-medium">{s.itm}</td>
                      <td className="py-3 pr-6 text-loss font-medium">{s.otm}</td>
                      <td className="py-3 pr-6 text-warn">{s.tie}</td>
                      <td className="py-3 pr-6">
                        <Badge variant="default">{s.open}</Badge>
                      </td>
                      <td className="py-3">
                        <Badge
                          variant={s.win_rate >= 55 ? "profit" : s.win_rate >= 45 ? "warn" : "loss"}
                        >
                          {s.win_rate}%
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
