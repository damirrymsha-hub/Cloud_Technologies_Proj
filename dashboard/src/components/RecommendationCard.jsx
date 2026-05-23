import { TrendingDown, Clock, Shield, Zap, AlertCircle } from 'lucide-react'

const ACTION_META = {
  downsize_instance:  { Icon: TrendingDown, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-950/40', border: 'border-orange-200 dark:border-orange-800' },
  schedule_shutdown:  { Icon: Clock,        color: 'text-blue-500',   bg: 'bg-blue-50 dark:bg-blue-950/40',    border: 'border-blue-200 dark:border-blue-800'   },
  switch_to_reserved: { Icon: Shield,       color: 'text-green-500',  bg: 'bg-green-50 dark:bg-green-950/40',  border: 'border-green-200 dark:border-green-800' },
  switch_to_spot:     { Icon: Zap,          color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-950/40',border: 'border-purple-200 dark:border-purple-800'},
}

const RISK_BADGE = {
  low:    'bg-green-100  text-green-700  dark:bg-green-900/40  dark:text-green-400',
  medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400',
  high:   'bg-red-100    text-red-700    dark:bg-red-900/40    dark:text-red-400',
}

const ACTION_LABEL = {
  downsize_instance:  'Downsize Instance',
  schedule_shutdown:  'Schedule Shutdown',
  switch_to_reserved: 'Switch to Reserved',
  switch_to_spot:     'Switch to Spot',
}

export default function RecommendationCard({ rec }) {
  const meta = ACTION_META[rec.action] ?? {
    Icon: AlertCircle, color: 'text-gray-500', bg: 'bg-gray-50', border: 'border-gray-200',
  }
  const { Icon } = meta

  return (
    <div
      className={`rounded-xl border p-4 transition-shadow hover:shadow-md ${meta.bg} ${meta.border}`}
    >
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon size={17} className={`shrink-0 ${meta.color}`} />
          <span className="text-xs font-mono text-gray-500 dark:text-gray-400 truncate">
            {rec.resource_id}
          </span>
        </div>
        <span className={`shrink-0 ml-2 text-xs px-2 py-0.5 rounded-full font-medium ${RISK_BADGE[rec.risk_level]}`}>
          {rec.risk_level}
        </span>
      </div>

      {/* ── Action title ─────────────────────────────────────────────────── */}
      <p className="font-semibold text-sm mb-1">
        {ACTION_LABEL[rec.action] ?? rec.action}
      </p>

      {/* ── Reason ───────────────────────────────────────────────────────── */}
      <p className="text-xs text-gray-600 dark:text-gray-400 mb-3 line-clamp-3 leading-relaxed">
        {rec.reason}
      </p>

      {/* ── Metrics row ──────────────────────────────────────────────────── */}
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Est. monthly savings</p>
          <p className="text-xl font-bold text-green-500">
            ${rec.estimated_monthly_savings_usd.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500 dark:text-gray-400">Confidence</p>
          <ConfidenceBar value={rec.confidence_score} />
        </div>
      </div>

      {/* ── Tags ─────────────────────────────────────────────────────────── */}
      <div className="mt-3 flex flex-wrap gap-1">
        <Tag>{rec.instance_type}</Tag>
        <Tag>{rec.environment}</Tag>
      </div>
    </div>
  )
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-red-400'
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span className="text-sm font-semibold">{pct}%</span>
      <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Tag({ children }) {
  return (
    <span className="text-xs bg-black/5 dark:bg-white/10 px-2 py-0.5 rounded-full text-gray-600 dark:text-gray-300">
      {children}
    </span>
  )
}
