import { useState, useEffect } from 'react'
import { CloudLightning, Moon, Sun } from 'lucide-react'
import CostChart from './components/CostChart'
import RecommendationCard from './components/RecommendationCard'
import SavingsGauge from './components/SavingsGauge'
import AnomalyTimeline from './components/AnomalyTimeline'

// In dev mode Vite proxies /api → localhost:8000.
// In production the nginx config proxies /api → the api container.
const API = '/api'

function useFetch(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [url])

  return { data, loading, error }
}

export default function App() {
  const [dark, setDark] = useState(false)
  const [env, setEnv] = useState('all')
  const [horizon, setHorizon] = useState(30)
  const [riskFilter, setRiskFilter] = useState('all')

  const { data: summary, loading: summaryLoading } =
    useFetch(`${API}/summary`)

  const recsUrl = `${API}/recommendations?page_size=50` +
    (env !== 'all' ? `&environment=${env}` : '') +
    (riskFilter !== 'all' ? `&risk_level=${riskFilter}` : '')
  const { data: recsData, loading: recsLoading } = useFetch(recsUrl)

  const { data: forecastData, loading: forecastLoading } =
    useFetch(`${API}/forecast?horizon=${horizon}`)

  const { data: anomalyData, loading: anomalyLoading } =
    useFetch(`${API}/anomalies`)

  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 transition-colors duration-200">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 py-3 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-3">
            <CloudLightning className="text-blue-500" size={26} />
            <div>
              <h1 className="text-lg font-bold leading-tight">Cloud Cost Optimizer</h1>
              <p className="text-xs text-gray-400">AI-powered cost analysis & recommendations</p>
            </div>
          </div>
          <button
            onClick={() => setDark(d => !d)}
            title="Toggle dark mode"
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">

          {/* ── KPI cards ──────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <KpiCard
              label="Total Cost (last 30 d)"
              value={summary ? `$${summary.total_cost_last_30d.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '…'}
              loading={summaryLoading}
            />
            <KpiCard
              label="Projected Monthly Savings"
              value={summary ? `$${summary.projected_monthly_savings_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '…'}
              loading={summaryLoading}
              accent="green"
            />
            <KpiCard
              label="Actionable Recommendations"
              value={summary ? summary.num_recommendations : '…'}
              loading={summaryLoading}
              accent="blue"
            />
          </div>

          {/* ── Gauge + Cost chart ──────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="flex flex-col items-center justify-center py-4">
              <SavingsGauge
                currentSpend={summary?.total_cost_last_30d ?? 0}
                potentialSavings={summary?.projected_monthly_savings_usd ?? 0}
                loading={summaryLoading}
              />
            </Card>
            <Card className="lg:col-span-2">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h2 className="font-semibold text-sm">Cost Forecast</h2>
                <div className="flex gap-1 text-xs">
                  {[30, 90].map(h => (
                    <Pill key={h} active={horizon === h} onClick={() => setHorizon(h)}>
                      {h}d
                    </Pill>
                  ))}
                </div>
              </div>
              <CostChart
                forecastData={forecastData?.forecast ?? []}
                loading={forecastLoading}
              />
            </Card>
          </div>

          {/* ── Anomaly timeline ──────────────────────────────────────────── */}
          <Card>
            <h2 className="font-semibold text-sm mb-3">
              Anomaly Timeline
              <span className="ml-2 text-xs font-normal text-gray-400">(last 90 days)</span>
            </h2>
            <AnomalyTimeline
              anomalies={anomalyData ?? []}
              loading={anomalyLoading}
            />
          </Card>

          {/* ── Recommendations ───────────────────────────────────────────── */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h2 className="font-semibold">
                Recommendations
                {recsData && (
                  <span className="ml-2 text-sm font-normal text-gray-400">
                    ({recsData.length} shown)
                  </span>
                )}
              </h2>
              <div className="flex flex-wrap gap-2 text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">Env:</span>
                  {['all', 'prod', 'dev', 'staging'].map(e => (
                    <Pill key={e} active={env === e} onClick={() => setEnv(e)}>{e}</Pill>
                  ))}
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">Risk:</span>
                  {['all', 'low', 'medium', 'high'].map(r => (
                    <Pill key={r} active={riskFilter === r} onClick={() => setRiskFilter(r)}>{r}</Pill>
                  ))}
                </div>
              </div>
            </div>

            {recsLoading ? (
              <LoadingGrid />
            ) : recsData?.length === 0 ? (
              <p className="text-sm text-gray-400 py-8 text-center">
                No recommendations match the current filters.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {(recsData ?? []).map(r => (
                  <RecommendationCard key={r.resource_id} rec={r} />
                ))}
              </div>
            )}
          </div>
        </main>

        <footer className="text-center text-xs text-gray-400 py-6">
          Cloud Cost Optimizer — University Project · Data is fully synthetic
        </footer>
      </div>
    </div>
  )
}

/* ── Shared UI primitives ──────────────────────────────────────────────────── */

function Card({ children, className = '' }) {
  return (
    <div className={`bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-800 p-4 ${className}`}>
      {children}
    </div>
  )
}

function KpiCard({ label, value, accent, loading }) {
  const color =
    accent === 'green' ? 'text-green-500' :
    accent === 'blue'  ? 'text-blue-500'  :
    'text-gray-800 dark:text-gray-100'

  return (
    <Card>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</p>
      {loading
        ? <div className="h-8 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        : <p className={`text-2xl font-bold ${color}`}>{value}</p>
      }
    </Card>
  )
}

function Pill({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded transition-colors ${
        active
          ? 'bg-blue-500 text-white'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
      }`}
    >
      {children}
    </button>
  )
}

function LoadingGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-48 rounded-xl bg-gray-200 dark:bg-gray-800 animate-pulse" />
      ))}
    </div>
  )
}
