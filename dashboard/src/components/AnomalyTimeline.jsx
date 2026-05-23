import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

const SEVERITY_COLOR = {
  high:   '#ef4444',   // red-500
  medium: '#f97316',   // orange-500
  low:    '#facc15',   // yellow-400
}

function CustomDot({ cx, cy, payload }) {
  const fill = SEVERITY_COLOR[payload?.severity_label] ?? '#9ca3af'
  return <circle cx={cx} cy={cy} r={5} fill={fill} fillOpacity={0.85} stroke="white" strokeWidth={1} />
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-2.5 text-xs shadow-lg">
      <p className="font-semibold mb-1">{d.date}</p>
      <p>Actual cost: <strong>${Number(d.actual_cost).toFixed(4)}</strong></p>
      <p>Expected:    <strong>${Number(d.expected_cost).toFixed(4)}</strong></p>
      <p>
        Severity:{' '}
        <strong style={{ color: SEVERITY_COLOR[d.severity_label] }}>
          {d.severity_label} ({(d.severity * 100).toFixed(0)}%)
        </strong>
      </p>
      <p className="font-mono text-gray-400 mt-1 truncate max-w-[180px]">{d.resource_id}</p>
    </div>
  )
}

export default function AnomalyTimeline({ anomalies, loading }) {
  if (loading) {
    return <div className="h-44 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
  }

  if (!anomalies.length) {
    return (
      <p className="text-sm text-gray-400 py-8 text-center">
        No anomalies detected in the last 90 days.
      </p>
    )
  }

  // Display up to 200 anomalies; sort by date for clean x-axis layout
  const data = [...anomalies]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 200)

  return (
    <div>
      {/* Legend */}
      <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400 mb-2">
        {Object.entries(SEVERITY_COLOR).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            {label}
          </span>
        ))}
        <span className="ml-auto text-gray-400">{anomalies.length} anomaly points</span>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <ScatterChart margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="currentColor"
            className="text-gray-200 dark:text-gray-700"
          />
          <XAxis
            dataKey="date"
            name="Date"
            tick={{ fontSize: 10 }}
            tickFormatter={d => d?.slice(5)}
            minTickGap={20}
          />
          <YAxis
            dataKey="actual_cost"
            name="Actual cost"
            tick={{ fontSize: 10 }}
            tickFormatter={v => `$${Number(v).toFixed(2)}`}
            width={58}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={data} shape={<CustomDot />} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
