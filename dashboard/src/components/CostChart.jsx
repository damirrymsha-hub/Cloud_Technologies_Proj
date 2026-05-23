import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'

export default function CostChart({ forecastData, loading }) {
  if (loading) {
    return <div className="h-56 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
  }

  if (!forecastData.length) {
    return <p className="text-sm text-gray-400 py-10 text-center">No forecast data available.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={forecastData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="gradForecast" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradBand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#93c5fd" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#93c5fd" stopOpacity={0} />
          </linearGradient>
        </defs>

        <CartesianGrid
          strokeDasharray="3 3"
          stroke="currentColor"
          className="text-gray-200 dark:text-gray-700"
        />
        <XAxis
          dataKey="ds"
          tick={{ fontSize: 11 }}
          tickFormatter={d => d?.slice(5)}   /* show MM-DD only */
          minTickGap={20}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={v => `$${v.toFixed(0)}`}
          width={55}
        />
        <Tooltip
          formatter={(v, name) => [`$${Number(v).toFixed(2)}`, name]}
          labelFormatter={l => `Date: ${l}`}
          contentStyle={{
            backgroundColor: 'var(--tooltip-bg, #fff)',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            fontSize: '12px',
          }}
        />
        <Legend wrapperStyle={{ fontSize: '11px' }} />

        {/* 90 % confidence band */}
        <Area
          type="monotone"
          dataKey="yhat_upper"
          stroke="#93c5fd"
          strokeWidth={1}
          strokeDasharray="4 3"
          fill="url(#gradBand)"
          name="Upper bound"
          dot={false}
        />
        <Area
          type="monotone"
          dataKey="yhat_lower"
          stroke="#93c5fd"
          strokeWidth={1}
          strokeDasharray="4 3"
          fill="transparent"
          name="Lower bound"
          dot={false}
        />

        {/* Main forecast line */}
        <Area
          type="monotone"
          dataKey="yhat"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#gradForecast)"
          name="Forecast"
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
