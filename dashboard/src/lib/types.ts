// ==========================================
// API Response Types
// ==========================================

export interface HealthResponse {
  status: string
  mt5_connected: boolean
}

export interface RunRecord {
  id: number
  symbol: string
  timeframe: number
  timestamp: string
  trend: string
  volatility: string
  macro_score: number
  rsi: number
}

export interface SignalRecord {
  id: number
  run: number
  type: string
  direction: string
  strength: number
  final_score: number
  entry_price: number | null
  tp_price: number | null
  sl_price: number | null
  status: string
  pnl_points: number | null
  validated_at: string | null
}

export interface ReportResponse {
  run_id: number
  content: string
}

export interface AgentResult {
  symbol: string
  timeframe: number
  verdict: string
  direction: string
  confidence: number
  run_id: number
  [key: string]: unknown
}

export interface BinarySignalRecord {
  symbol: string
  direction: "CALL" | "PUT" | "WAIT"
  expiration: "M1" | "M5" | "M15"
  confidence: number
  entry_price: number
  expiry_price: number | null
  status: "OPEN" | "ITM" | "OTM" | "TIE"
  opened_at: string | null
  expires_at: string | null
  closed_at: string | null
}

export interface BinaryStatsResponse {
  days: number
  symbol: string | null
  total: number
  itm: number
  otm: number
  tie: number
  open: number
  win_rate: number
}

// ==========================================
// UI Types
// ==========================================

export type SignalDirection = "COMPRA" | "VENDA" | "AGUARDAR" | "CALL" | "PUT" | "WAIT"

export type SignalStatus = "PENDING" | "WIN" | "LOSS" | "EXPIRED" | "OPEN" | "ITM" | "OTM" | "TIE"

export interface NavItem {
  label: string
  href: string
  icon: string
}
