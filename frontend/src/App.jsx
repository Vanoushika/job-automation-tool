import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import StatsBar from './components/StatsBar'
import FilterBar from './components/FilterBar'
import JobCard from './components/JobCard'

const DEFAULT_FILTERS = { tier: 'all', jobType: 'all', appliedOnly: false, hideApplied: false, search: '', postedWithin: 'all', sortBy: 'newest', newOnly: true, roleType: 'all' }

const ROLE_TYPE_KEYWORDS = {
  swe:       ['software engineer', 'software developer', 'swe', 'software development'],
  backend:   ['backend', 'back end', 'back-end', 'server-side', 'api engineer', 'platform engineer'],
  frontend:  ['frontend', 'front end', 'front-end', 'ui engineer', 'react developer', 'web developer'],
  fullstack: ['full stack', 'fullstack', 'full-stack'],
  ml:        ['machine learning', 'ml engineer', 'ai engineer', 'data scientist', 'mlops', 'deep learning', 'nlp'],
  mobile:    ['ios', 'android', 'mobile', 'swift', 'kotlin', 'flutter', 'react native'],
}

const TIER_ORDER = ['A', 'B', 'C', 'D']

export default function App() {
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState({})
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [error, setError] = useState(null)
  const [hiddenIds, setHiddenIds] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('hiddenJobs') || '[]')) }
    catch { return new Set() }
  })
  const [appliedIds, setAppliedIds] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('appliedJobs') || '[]')) }
    catch { return new Set() }
  })

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

  // Auto-refresh every 10 minutes to catch new jobs from hourly pipeline
  useEffect(() => {
    const interval = setInterval(fetchAll, 10 * 60 * 1000)
    return () => clearInterval(interval)
  }, [fetchAll])

  // Merge localStorage applied status into jobs (survives Render restarts + refreshes)
  const jobsWithApplied = jobs.map(j => appliedIds.has(j.id) ? { ...j, applied: true } : j)

  // Client-side filtering
  let filtered = jobsWithApplied.filter(j => !hiddenIds.has(j.id)).filter(j => {
    if (filters.tier !== 'all' && j.tier !== filters.tier) return false
    if (filters.jobType !== 'all' && j.job_type !== filters.jobType) return false
    if (filters.appliedOnly && !j.applied) return false
    if (filters.hideApplied && j.applied) return false
    if (filters.search) {
      const q = filters.search.toLowerCase()
      if (!j.company?.toLowerCase().includes(q) && !j.role?.toLowerCase().includes(q)) return false
    }
    if (filters.postedWithin !== 'all') {
      const cutoff = Date.now() - parseInt(filters.postedWithin) * 3600000
      if (!j.posted_date || new Date(j.posted_date).getTime() < cutoff) return false
    }
    if (filters.newOnly && !j.is_new) return false
    if (filters.roleType !== 'all') {
      const kws = ROLE_TYPE_KEYWORDS[filters.roleType] || []
      if (!kws.some(kw => (j.role || '').toLowerCase().includes(kw))) return false
    }
    return true
  })

  // Sort
  if (filters.sortBy === 'newest') {
    filtered = [...filtered].sort((a, b) => {
      const ta = a.first_seen ? new Date(a.first_seen).getTime() : 0
      const tb = b.first_seen ? new Date(b.first_seen).getTime() : 0
      return tb - ta
    })
  }

  // Group by tier for display
  const grouped = TIER_ORDER.reduce((acc, t) => {
    const tier_jobs = filtered.filter(j => j.tier === t)
    if (tier_jobs.length) acc[t] = tier_jobs
    return acc
  }, {})

  function handleApplied(jobId) {
    setAppliedIds(prev => {
      const next = new Set(prev)
      next.add(jobId)
      localStorage.setItem('appliedJobs', JSON.stringify([...next]))
      return next
    })
    setStats(prev => ({ ...prev, applied: (prev.applied || 0) + 1 }))
  }

  function handleHide(jobId) {
    setHiddenIds(prev => {
      const next = new Set(prev)
      next.add(jobId)
      localStorage.setItem('hiddenJobs', JSON.stringify([...next]))
      return next
    })
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
    A: { label: 'Tier A — 72%+ Match', color: 'text-green-700 bg-green-50 border-green-200' },
    B: { label: 'Tier B — 58–71% Match', color: 'text-blue-700 bg-blue-50 border-blue-200' },
    C: { label: 'Tier C — 42–57% Match', color: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
    D: { label: 'Tier D — Below 42%', color: 'text-gray-600 bg-gray-50 border-gray-200' },
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

        {/* SimplifyJobs status banner */}
        {!loading && (() => {
          const simplifyJobs = jobsWithApplied.filter(j => j.source === 'SimplifyJobs')
          if (simplifyJobs.length === 0) return (
            <div className="mb-2 bg-gray-50 border border-gray-200 rounded-lg px-4 py-2 text-xs text-gray-500">
              📋 No new SimplifyJobs listings today — showing Greenhouse, Lever &amp; Adzuna results only
            </div>
          )
          return (
            <div className="mb-2 bg-gray-50 border border-gray-200 rounded-lg px-4 py-2 text-xs text-gray-500">
              📋 {simplifyJobs.length} SimplifyJobs listing{simplifyJobs.length !== 1 ? 's' : ''} included (no timestamp — posting date unknown)
            </div>
          )
        })()}

        {/* New jobs banner */}
        {!loading && (() => {
          const newCount = jobsWithApplied.filter(j => j.is_new).length
          const appliedCount = appliedIds.size
          return (
            <div className="mb-4 bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 flex items-center justify-between">
              <span className="text-indigo-700 font-semibold text-sm">
                🆕 {newCount} fresh job{newCount !== 1 ? 's' : ''} today
                <span className="font-normal text-indigo-500 ml-2">· {jobs.length} total</span>
                {appliedCount > 0 && <span className="font-normal text-purple-500 ml-2">· ✔ {appliedCount} applied</span>}
              </span>
              <button
                onClick={() => setFilters(f => ({ ...f, newOnly: !f.newOnly }))}
                className="text-xs text-indigo-600 underline hover:text-indigo-800"
              >
                {filters.newOnly ? 'Show all jobs' : 'Show today only'}
              </button>
            </div>
          )
        })()}

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
              {jobsWithApplied.length === 0
                ? 'Run the pipeline first to fetch and score jobs.'
                : 'Try changing your filters.'}
            </p>
            {jobsWithApplied.length === 0 && (
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
                  <JobCard key={job.id} job={job} onApplied={handleApplied} onHide={handleHide} />
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
