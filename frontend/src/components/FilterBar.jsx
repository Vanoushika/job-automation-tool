export default function FilterBar({ filters, setFilters }) {
  const tiers = ['all', 'A', 'B', 'C', 'D']
  const types = [
    { value: 'all',       label: 'All Types' },
    { value: 'full_time', label: 'Full-Time' },
    { value: 'contract',  label: 'W2 / Contract' },
  ]
  const postedOptions = [
    { value: 'all', label: 'Any Time' },
    { value: '1',   label: 'Last 1h' },
    { value: '3',   label: 'Last 3h' },
    { value: '6',   label: 'Last 6h' },
    { value: '12',  label: 'Last 12h' },
    { value: '24',  label: 'Today' },
  ]
  const sortOptions = [
    { value: 'score',  label: 'Best Match' },
    { value: 'newest', label: 'Newest First' },
  ]

  return (
    <div className="flex flex-wrap gap-3 mb-6 items-center">
      {/* Tier filter */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
        {tiers.map((t) => {
          const active = filters.tier === t
          const colors = {
            all: 'bg-gray-700 text-white',
            A:   'bg-green-500 text-white',
            B:   'bg-blue-500 text-white',
            C:   'bg-yellow-500 text-white',
            D:   'bg-gray-400 text-white',
          }
          return (
            <button
              key={t}
              onClick={() => setFilters(f => ({ ...f, tier: t }))}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${
                active ? colors[t] : 'text-gray-600 hover:bg-gray-200'
              }`}
            >
              {t === 'all' ? 'All Tiers' : `Tier ${t}`}
            </button>
          )
        })}
      </div>

      {/* Job type filter */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
        {types.map((t) => (
          <button
            key={t.value}
            onClick={() => setFilters(f => ({ ...f, jobType: t.value }))}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${
              filters.jobType === t.value
                ? 'bg-indigo-500 text-white'
                : 'text-gray-600 hover:bg-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Posted within filter */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
        {postedOptions.map((o) => (
          <button
            key={o.value}
            onClick={() => setFilters(f => ({ ...f, postedWithin: o.value }))}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${
              filters.postedWithin === o.value
                ? 'bg-orange-500 text-white'
                : 'text-gray-600 hover:bg-gray-200'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {/* Sort */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
        {sortOptions.map((o) => (
          <button
            key={o.value}
            onClick={() => setFilters(f => ({ ...f, sortBy: o.value }))}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${
              filters.sortBy === o.value
                ? 'bg-teal-500 text-white'
                : 'text-gray-600 hover:bg-gray-200'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {/* New Only toggle */}
      <button
        onClick={() => setFilters(f => ({ ...f, newOnly: !f.newOnly }))}
        className={`px-3 py-1 rounded-lg text-sm font-semibold border transition-all ${
          filters.newOnly
            ? 'bg-red-500 text-white border-red-500'
            : 'text-red-600 border-red-300 hover:bg-red-50'
        }`}
      >
        🆕 New Only
      </button>

      {/* Applied toggle */}
      <button
        onClick={() => setFilters(f => ({ ...f, appliedOnly: !f.appliedOnly }))}
        className={`px-3 py-1 rounded-lg text-sm font-medium border transition-all ${
          filters.appliedOnly
            ? 'bg-purple-500 text-white border-purple-500'
            : 'text-gray-600 border-gray-300 hover:bg-gray-100'
        }`}
      >
        ✔ Applied Only
      </button>

      {/* Search */}
      <input
        type="text"
        placeholder="Search company or role..."
        value={filters.search}
        onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
        className="flex-1 min-w-48 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
      />
    </div>
  )
}
