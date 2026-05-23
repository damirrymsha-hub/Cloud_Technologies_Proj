import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'

export default function SavingsGauge({ currentSpend, potentialSavings, loading }) {
  if (loading) {
    return (
      <div className="flex flex-col items-center gap-3 w-full">
        <div className="w-40 h-24 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
        <div className="w-24 h-6 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
      </div>
    )
  }

  const savings = Math.max(0, Math.min(potentialSavings, currentSpend))
  const remaining = Math.max(0, currentSpend - savings)
  const pct = currentSpend > 0 ? (savings / currentSpend) * 100 : 0

  const data = [
    { name: 'Potential Savings', value: savings },
    { name: 'Remaining Spend',   value: remaining },
  ]

  return (
    <div className="w-full flex flex-col items-center">
      <h2 className="font-semibold text-sm mb-1">Savings Opportunity</h2>

      {/* Half-donut gauge */}
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="90%"        /* push centre to bottom so only upper half shows */
            startAngle={180}
            endAngle={0}
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={2}
            dataKey="value"
            strokeWidth={0}
          >
            <Cell fill="#22c55e" />   {/* savings — green */}
            <Cell fill="#e5e7eb" />   {/* remaining — gray */}
          </Pie>
          <Tooltip
            formatter={(v, name) =>
              [`$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, name]
            }
            contentStyle={{
              fontSize: '11px',
              borderRadius: '8px',
              border: '1px solid #e5e7eb',
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Centred label over the gauge */}
      <div className="-mt-8 flex flex-col items-center">
        <p className="text-3xl font-bold text-green-500">{pct.toFixed(1)}%</p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          ${savings.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} of ${currentSpend.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </p>
      </div>

      {/* Legend */}
      <div className="mt-4 flex gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500" />
          Savings
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-gray-300 dark:bg-gray-600" />
          Spend
        </span>
      </div>
    </div>
  )
}
