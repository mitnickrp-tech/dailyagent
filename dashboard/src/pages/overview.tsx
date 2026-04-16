import { useEffect, useState } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { getHealth, getRecentRuns, getBinaryStats, getBinaryRecent } from "@/lib/api"
import type { RunRecord, BinarySignalRecord, BinaryStatsResponse, HealthResponse } from "@/lib/types"
import { Activity, TrendingUp, Target, Wifi, WifiOff } from "lucide-react"

function timeframeLabel(tf: number): string {
  const map: Record<number, string> = {
    1: "M1", 5: "M5", 15: "M15", 60: "H1", 16385: "H1", 1440: "D1", 16408: "D1",
  }
  return map[tf] ?? `TF${tf}`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  })
}

function directionBadge(dir: string) {
  if (dir === "COMPRA" || dir === "CALL") return <Badge variant="profit">{dir}</Badge>
  if (dir === "VENDA" || dir === "PUT") return <Badge variant="loss">{dir}</Badge>
  return <Badge variant="warn">{dir}</Badge>
}

function statusBadge(status: string) {
  if (status === "WIN" || status === "ITM") return <Badge variant="profit">{status}</Badge>
  if (status === "LOSS" || status === "OTM") return <Badge variant="loss">{status}</Badge>
  if (status === "OPEN" || status === "PENDING") return <Badge variant="default">{status}</Badge>
  return <Badge variant="muted">{status}</Badge>
}

export function OverviewPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [binaryStats, setBinaryStats] = useState<BinaryStatsResponse | null>(null)
  const [binaryRecent, setBinaryRecent] = useState<BinarySignalRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      getHealth(),
      getRecentRuns(8),
      getBinaryStats(7),
      getBinaryRecent(5),
    ]).then(([h, r, bs, br]) => {
      if (h.status === "fulfilled") setHealth(h.value)
      if (r.status === "fulfilled") setRuns(r.value)
      if (bs.status === "fulfilled") setBinaryStats(bs.value)
      if (br.status === "fulfilled") setBinaryRecent(br.value)
      setLoading(false)
    })
  }, [])

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
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Visao Geral</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Monitoramento em tempo real do DailyAgent 2.0
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Status */}
        <Card className="glass-card-hover">
          <CardHeader>
            <CardTitle>Status da API</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              {health?.status === "healthy" ? (
                <Wifi className="h-5 w-5 text-profit" />
              ) : (
                <WifiOff className="h-5 w-5 text-loss" />
              )}
              <div>
                <p className="text-lg font-semibold">
                  {health?.status === "healthy" ? "Online" : "Offline"}
                </p>
                <p className="text-xs text-muted-foreground">
                  MT5: {health?.mt5_connected ? "Conectado" : "Desconectado"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Total Runs */}
        <Card className="glass-card-hover">
          <CardHeader>
            <CardTitle>Analises Recentes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <Activity className="h-5 w-5 text-primary" />
              <div>
                <p className="text-lg font-semibold">{runs.length}</p>
                <p className="text-xs text-muted-foreground">Ultimas execucoes</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Binary Win Rate */}
        <Card className="glass-card-hover">
          <CardHeader>
            <CardTitle>Win Rate Binarias</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <Target className="h-5 w-5 text-warn" />
              <div>
                <p className="text-lg font-semibold">
                  {binaryStats ? `${binaryStats.win_rate}%` : "--"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {binaryStats
                    ? `${binaryStats.itm} ITM / ${binaryStats.otm} OTM (7d)`
                    : "Sem dados"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Binary Open */}
        <Card className="glass-card-hover">
          <CardHeader>
            <CardTitle>Sinais Abertos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <TrendingUp className="h-5 w-5 text-primary" />
              <div>
                <p className="text-lg font-semibold">{binaryStats?.open ?? 0}</p>
                <p className="text-xs text-muted-foreground">Aguardando resultado</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Runs + Binary Signals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Forex Runs */}
        <Card>
          <CardHeader>
            <CardTitle>Ultimas Analises Forex</CardTitle>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma analise recente.</p>
            ) : (
              <div className="space-y-3">
                {runs.map((run) => (
                  <div
                    key={run.id}
                    className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono font-medium">{run.symbol}</span>
                      <Badge variant="muted">{timeframeLabel(run.timeframe)}</Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>RSI {run.rsi?.toFixed(1)}</span>
                      <span>{run.trend}</span>
                      <span>{formatDate(run.timestamp)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Binary Signals */}
        <Card>
          <CardHeader>
            <CardTitle>Ultimos Sinais Binarios</CardTitle>
          </CardHeader>
          <CardContent>
            {binaryRecent.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhum sinal binario recente.</p>
            ) : (
              <div className="space-y-3">
                {binaryRecent.map((sig, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono font-medium">{sig.symbol}</span>
                      {directionBadge(sig.direction)}
                      <Badge variant="muted">{sig.expiration}</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground">
                        {sig.confidence}%
                      </span>
                      {statusBadge(sig.status)}
                      <span className="text-xs text-muted-foreground">
                        {sig.opened_at ? formatDate(sig.opened_at) : ""}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
