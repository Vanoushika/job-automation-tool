import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import StatsBar from './components/StatsBar'
import FilterBar from './components/FilterBar'
import JobCard from './components/JobCard'

const DEFAULT_FILTERS = { tier: 'all', jobType: 'all', appliedOnly: false, search: '' }

const TIER_ORDER = ['A', 'B', 'C', 'D']

export default function App() {
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState({})
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [error, setError] = useState(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [jobsRes, statsRes] = await Promise.all([
        axios.get('/api/jobs'),
        axios.get('/api/stats'),
      ])
      setJobs(jobsRes.data)
      setStats(statsRes.data)
      setLastUpdated(new Date())
    } catch (e) {
      setError('Cannot connect to backend. Make sure the API is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Client-side filtering on top of already-sorted data from API
  const filtered = jobs.filter(j => {
    if (filters.tier !== 'all' && j.tier !== filters.tier) return false
    if (filters.jobType !== 'all' && j.job_type !== filters.jobType) return false
    if (filters.appliedOnly && !j.applied) return false
    if (filters.search) {
      const q = filters.search.toLowerCase()
      if (!j.company?.toLowerCase().includes(q) && !j.role?.toLowerCase().includes(q)) return false
    }
    return true
  })

  // Group by tier for display
  const grouped = TIER_ORDER.reduce((acc, t) => {
    const tier_jobs = filtered.filter(j => j.tier === t)
    if (tier_jobs.length) acc[t] = tier_jobs
    return acc
  }, {})

  function handleApplied(jobId) {
    setJobs(prev => prev.map(j => j.id === jobId ? { ...j, applied: true } : j))
    setStats(prev => ({ ...prev, applied: (prev.applied || 0) + 1 }))
  }

  async function triggerRun() {
    setRunning(true)
    try {
      const res = await axios.post('/api/run')
      alert(res.data.message)
    } catch {
      alert('Failed to start pipeline.')
    } finally {
      setTimeout(() => setRunning(false), 2000)
    }
  }

  const TIER_LABELS = {
    A: { label: 'Tier A — 85%+ Match', color: 'text-green-700 bg-green-50 border-green-200' },
    B: { label: 'Tier B — 75–84% Match', color: 'text-blue-700 bg-blue-50 border-blue-200' },
    C: { label: 'Tier C — 65–74% Match', color: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
    D: { label: 'Tier D — Below 65%', color: 'text-gray-600 bg-gray-50 border-gray-200' },
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">🎯 Job Dashboard</h1>
            {lastUpdated && (
              <p className="text-xs text-gray-400">Last updated: {lastUpdated.toLocaleTimeString()}</p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={fetchAll}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-100 transition"
            >
              ↻ Refresh
            </button>
            <button
              onClick={triggerRun}
              disabled={running}
              className={`px-4 py-1.5 text-sm font-medium rounded-lg text-white transition ${
                running ? 'bg-gray-400 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-700'
              }`}
            >
              {running ? 'Running...' : '⚡ Run Pipeline'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* Error */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {/* Stats */}
        {!loading && <StatsBar stats={stats} />}

        {/* Filters */}
        <FilterBar filters={filters} setFilters={setFilters} />

        {/* Loading */}
        {loading && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-4xl mb-3 animate-pulse">⚙️</p>
            <p>Loading jobs...</p>
          </div>
        )}

        {/* Empty state */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-5xl mb-3">🔍</p>
            <p className="font-medium">No jobs found</p>
            <p className="text-sm mt-1">
              {jobs.length === 0
                ? 'Run the pipeline first to fetch and score jobs.'
                : 'Try changing your filters.'}
            </p>
            {jobs.length === 0 && (
              <button
                onClick={triggerRun}
                className="mt-4 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
              >
                ⚡ Run Pipeline Now
              </button>
            )}
          </div>
        )}

        {/* Job groups by tier */}
        {!loading && Object.entries(grouped).map(([tier, tierJobs]) => {
          const info = TIER_LABELS[tier]
          return (
            <div key={tier} className="mb-8">
              <div className={`flex items-center justify-between px-3 py-2 rounded-lg border mb-3 ${info.color}`}>
                <span className="font-semibold text-sm">{info.label}</span>
                <span className="text-sm font-medium">{tierJobs.length} job{tierJobs.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="flex flex-col gap-3">
                {tierJobs.map(job => (
                  <JobCard key={job.id} job={job} onApplied={handleApplied} />
                ))}
              </div>
            </div>
          )
        })}

        {/* Footer */}
        {!loading && filtered.length > 0 && (
          <p className="text-center text-xs text-gray-400 py-4">
            Showing {filtered.length} of {jobs.length} jobs
          </p>
        )}
      </main>
    </div>
  )
}
