import { Routes, Route } from "react-router-dom"
import { RootLayout } from "@/components/layout/root-layout"
import { OverviewPage } from "@/pages/overview"
import { ForexPage } from "@/pages/forex"
import { BinaryPage } from "@/pages/binary"
import { StatsPage } from "@/pages/stats"

export function App() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/forex" element={<ForexPage />} />
        <Route path="/binary" element={<BinaryPage />} />
        <Route path="/stats" element={<StatsPage />} />
      </Route>
    </Routes>
  )
}
