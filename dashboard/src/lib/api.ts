import type {
  HealthResponse,
  RunRecord,
  ReportResponse,
  AgentResult,
  BinarySignalRecord,
  BinaryStatsResponse,
} from "./types"

const BASE = "/api"

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new Error(`API ${res.status}: ${body}`)
  }
  return res.json()
}

// ==========================================
// Health
// ==========================================

export function getHealth() {
  return fetchJSON<HealthResponse>("/health")
}

// ==========================================
// Forex / Runs
// ==========================================

export function getRecentRuns(limit = 20) {
  return fetchJSON<RunRecord[]>(`/recent-runs?limit=${limit}`)
}

export function getReport(runId: number) {
  return fetchJSON<ReportResponse>(`/report/${runId}`)
}

export function runAgent(symbol: string, timeframe = "H1") {
  return fetchJSON<AgentResult>(
    `/run-agent?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`,
    { method: "POST" }
  )
}

export function runAnalysis(symbol: string, timeframe = "H1") {
  return fetchJSON<AgentResult>(
    `/run-analysis?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`,
    { method: "POST" }
  )
}

// ==========================================
// Binary
// ==========================================

export function getBinaryRecent(limit = 20) {
  return fetchJSON<BinarySignalRecord[]>(`/binary/recent?limit=${limit}`)
}

export function getBinaryStats(days = 30, symbol?: string) {
  let url = `/binary/stats?days=${days}`
  if (symbol) url += `&symbol=${encodeURIComponent(symbol)}`
  return fetchJSON<BinaryStatsResponse>(url)
}

export function runBinary(symbol: string, expiration = "M5") {
  return fetchJSON<AgentResult>(
    `/run-binary?symbol=${encodeURIComponent(symbol)}&expiration=${expiration}`,
    { method: "POST" }
  )
}
