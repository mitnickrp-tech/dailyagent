import { useEffect, useState } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getRecentRuns, getReport, runAgent } from "@/lib/api"
import type { RunRecord } from "@/lib/types"
import { RefreshCw, FileText, Play } from "lucide-react"

function timeframeLabel(tf: number): string {
  const map: Record<number, string> = {
    1: "M1", 5: "M5", 15: "M15", 60: "H1", 16385: "H1", 1440: "D1", 16408: "D1",
  }
  return map[tf] ?? `TF${tf}`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "2-digit",
    hour: "2-digit", minute: "2-digit",
  })
}

function trendBadge(trend: string) {
  const t = trend?.toLowerCase() ?? ""
  if (t.includes("alta") || t.includes("bull")) return <Badge variant="profit">{trend}</Badge>
  if (t.includes("baix") || t.includes("bear")) return <Badge variant="loss">{trend}</Badge>
  return <Badge variant="warn">{trend}</Badge>
}

export function ForexPage() {
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [reportContent, setReportContent] = useState<string | null>(null)
  const [reportRunId, setReportRunId] = useState<number | null>(null)
  const [running, setRunning] = useState(false)
  const [quickSymbol, setQuickSymbol] = useState("EURUSD")

  const fetchRuns = () => {
    setLoading(true)
    getRecentRuns(30)
      .then(setRuns)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchRuns() }, [])

  const handleViewReport = async (runId: number) => {
    if (reportRunId === runId) {
      setReportContent(null)
      setReportRunId(null)
      return
    }
    try {
      const r = await getReport(runId)
      setReportContent(r.content)
      setReportRunId(runId)
    } catch {
      setReportContent("Relatorio nao encontrado.")
      setReportRunId(runId)
    }
  }

  const handleRunAgent = async () => {
    if (!quickSymbol.trim()) return
    setRunning(true)
    try {
      await runAgent(quickSymbol.trim().toUpperCase())
      fetchRuns()
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
          <h1 className="text-2xl font-semibold text-foreground">Forex</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Analises e sinais de pares de moedas
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchRuns}>
          <RefreshCw className="h-3.5 w-3.5" />
          Atualizar
        </Button>
      </div>

      {/* Quick Run */}
      <Card>
        <CardHeader>
          <CardTitle>Analise Rapida</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={quickSymbol}
              onChange={(e) => setQuickSymbol(e.target.value)}
              placeholder="EURUSD"
              className="h-9 rounded-md border border-border bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring w-36"
            />
            <Button size="sm" onClick={handleRunAgent} disabled={running}>
              <Play className="h-3.5 w-3.5" />
              {running ? "Executando..." : "Analisar"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Runs Table */}
      <Card>
        <CardHeader>
          <CardTitle>Historico de Analises</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground animate-pulse">Carregando...</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma analise encontrada.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wider">
                    <th className="pb-3 pr-4">Simbolo</th>
                    <th className="pb-3 pr-4">TF</th>
                    <th className="pb-3 pr-4">Tendencia</th>
                    <th className="pb-3 pr-4">Volatilidade</th>
                    <th className="pb-3 pr-4">RSI</th>
                    <th className="pb-3 pr-4">Macro</th>
                    <th className="pb-3 pr-4">Data</th>
                    <th className="pb-3">Acoes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {runs.map((run) => (
                    <tr key={run.id} className="group">
                      <td className="py-3 pr-4 font-mono font-medium">{run.symbol}</td>
                      <td className="py-3 pr-4">
                        <Badge variant="muted">{timeframeLabel(run.timeframe)}</Badge>
                      </td>
                      <td className="py-3 pr-4">{trendBadge(run.trend)}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{run.volatility}</td>
                      <td className="py-3 pr-4 font-mono">{run.rsi?.toFixed(1)}</td>
                      <td className="py-3 pr-4 font-mono">{run.macro_score?.toFixed(2)}</td>
                      <td className="py-3 pr-4 text-muted-foreground text-xs">
                        {formatDate(run.timestamp)}
                      </td>
                      <td className="py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewReport(run.id)}
                          className="opacity-60 group-hover:opacity-100"
                        >
                          <FileText className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Report Panel */}
          {reportContent && (
            <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-medium text-muted-foreground uppercase">
                  Relatorio - Run #{reportRunId}
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setReportContent(null); setReportRunId(null) }}
                >
                  Fechar
                </Button>
              </div>
              <pre className="text-xs text-foreground/80 whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-y-auto">
                {reportContent}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
