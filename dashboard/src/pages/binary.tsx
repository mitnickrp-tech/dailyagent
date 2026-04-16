import { useEffect, useState, useCallback } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getBinaryRecent, getBinaryStats, runBinary } from "@/lib/api"
import type { BinarySignalRecord, BinaryStatsResponse } from "@/lib/types"
import { RefreshCw, Play, Target, TrendingUp, TrendingDown } from "lucide-react"

function formatDate(iso: string | null): string {
  if (!iso) return "--"
  const d = new Date(iso)
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  })
}

function directionIcon(dir: string) {
  if (dir === "CALL") return <TrendingUp className="h-4 w-4 text-profit" />
  if (dir === "PUT") return <TrendingDown className="h-4 w-4 text-loss" />
  return null
}

function directionBadge(dir: string) {
  if (dir === "CALL") return <Badge variant="profit">CALL</Badge>
  if (dir === "PUT") return <Badge variant="loss">PUT</Badge>
  return <Badge variant="warn">{dir}</Badge>
}

function statusBadge(status: string) {
  if (status === "ITM") return <Badge variant="profit">ITM</Badge>
  if (status === "OTM") return <Badge variant="loss">OTM</Badge>
  if (status === "TIE") return <Badge variant="warn">TIE</Badge>
  return <Badge variant="default">OPEN</Badge>
}

export function BinaryPage() {
  const [signals, setSignals] = useState<BinarySignalRecord[]>([])
  const [stats, setStats] = useState<BinaryStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [symbol, setSymbol] = useState("EURUSD")
  const [expiration, setExpiration] = useState("M5")

  const fetchData = useCallback(() => {
    setLoading(true)
    Promise.allSettled([
      getBinaryRecent(30),
      getBinaryStats(30),
    ]).then(([sig, st]) => {
      if (sig.status === "fulfilled") setSignals(sig.value)
      if (st.status === "fulfilled") setStats(st.value)
      setLoading(false)
    })
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const handleRunBinary = async () => {
    if (!symbol.trim()) return
    setRunning(true)
    try {
      await runBinary(symbol.trim().toUpperCase(), expiration)
      fetchData()
    } catch {
      // silently fail
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Binarias</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Sinais de opcoes binarias com auditoria ITM/OTM
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-3.5 w-3.5" />
          Atualizar
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="glass-card-hover">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">{stats.total}</p>
              <p className="text-xs text-muted-foreground mt-1">Total (30d)</p>
            </CardContent>
          </Card>
          <Card className="glass-card-hover">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-profit">{stats.itm}</p>
              <p className="text-xs text-muted-foreground mt-1">ITM</p>
            </CardContent>
          </Card>
          <Card className="glass-card-hover">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-loss">{stats.otm}</p>
              <p className="text-xs text-muted-foreground mt-1">OTM</p>
            </CardContent>
          </Card>
          <Card className="glass-card-hover">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-warn">{stats.open}</p>
              <p className="text-xs text-muted-foreground mt-1">Abertos</p>
            </CardContent>
          </Card>
          <Card className="glass-card-hover">
            <CardContent className="p-4 text-center">
              <p className={`text-2xl font-bold ${stats.win_rate >= 55 ? "text-profit" : stats.win_rate >= 45 ? "text-warn" : "text-loss"}`}>
                {stats.win_rate}%
              </p>
              <p className="text-xs text-muted-foreground mt-1">Win Rate</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Quick Binary Signal */}
      <Card>
        <CardHeader>
          <CardTitle>Gerar Sinal Binario</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="EURUSD"
              className="h-9 rounded-md border border-border bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring w-32"
            />
            <select
              value={expiration}
              onChange={(e) => setExpiration(e.target.value)}
              className="h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="M1">M1</option>
              <option value="M5">M5</option>
              <option value="M15">M15</option>
            </select>
            <Button size="sm" onClick={handleRunBinary} disabled={running}>
              <Play className="h-3.5 w-3.5" />
              {running ? "Gerando..." : "Gerar Sinal"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Signals Table */}
      <Card>
        <CardHeader>
          <CardTitle>Sinais Recentes</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground animate-pulse">Carregando...</p>
          ) : signals.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum sinal binario encontrado.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wider">
                    <th className="pb-3 pr-4">Ativo</th>
                    <th className="pb-3 pr-4">Direcao</th>
                    <th className="pb-3 pr-4">Exp.</th>
                    <th className="pb-3 pr-4">Confianca</th>
                    <th className="pb-3 pr-4">Entrada</th>
                    <th className="pb-3 pr-4">Saida</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 pr-4">Abertura</th>
                    <th className="pb-3">Fechamento</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {signals.map((sig, i) => (
                    <tr key={i} className="group hover:bg-accent/30 transition-colors">
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          {directionIcon(sig.direction)}
                          <span className="font-mono font-medium">{sig.symbol}</span>
                        </div>
                      </td>
                      <td className="py-3 pr-4">{directionBadge(sig.direction)}</td>
                      <td className="py-3 pr-4">
                        <Badge variant="muted">{sig.expiration}</Badge>
                      </td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className={`h-full rounded-full ${sig.confidence >= 70 ? "bg-profit" : sig.confidence >= 50 ? "bg-warn" : "bg-loss"}`}
                              style={{ width: `${sig.confidence}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono">{sig.confidence}%</span>
                        </div>
                      </td>
                      <td className="py-3 pr-4 font-mono text-xs">{sig.entry_price?.toFixed(5)}</td>
                      <td className="py-3 pr-4 font-mono text-xs">
                        {sig.expiry_price?.toFixed(5) ?? "--"}
                      </td>
                      <td className="py-3 pr-4">{statusBadge(sig.status)}</td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">
                        {formatDate(sig.opened_at)}
                      </td>
                      <td className="py-3 text-xs text-muted-foreground">
                        {formatDate(sig.closed_at)}
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
