export default function StatsBar({ stats }) {
  const cards = [
    { label: 'Total Jobs',  value: stats.total,     bg: 'bg-gray-100',   text: 'text-gray-800' },
    { label: '🔥 Tier A',   value: stats.tier_a,    bg: 'bg-green-100',  text: 'text-green-800' },
    { label: '⭐ Tier B',   value: stats.tier_b,    bg: 'bg-blue-100',   text: 'text-blue-800' },
    { label: '✅ Tier C',   value: stats.tier_c,    bg: 'bg-yellow-100', text: 'text-yellow-800' },
    { label: 'Full-Time',   value: stats.full_time, bg: 'bg-indigo-100', text: 'text-indigo-800' },
    { label: 'W2/Contract', value: stats.contract,  bg: 'bg-orange-100', text: 'text-orange-800' },
    { label: '✔ Applied',   value: stats.applied,   bg: 'bg-purple-100', text: 'text-purple-800' },
  ]

  return (
    <div className="grid grid-cols-4 sm:grid-cols-7 gap-3 mb-6">
      {cards.map((c) => (
        <div key={c.label} className={`${c.bg} rounded-xl p-3 text-center shadow-sm`}>
          <p className={`text-2xl font-bold ${c.text}`}>{c.value ?? 0}</p>
          <p className="text-xs text-gray-500 mt-0.5">{c.label}</p>
        </div>
      ))}
    </div>
  )
}
