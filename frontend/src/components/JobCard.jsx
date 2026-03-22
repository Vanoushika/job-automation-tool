import axios from 'axios'

const TIER_STYLES = {
  A: { badge: 'bg-green-100 text-green-800 border-green-200',  ring: 'border-l-green-400',  icon: '🔥' },
  B: { badge: 'bg-blue-100 text-blue-800 border-blue-200',     ring: 'border-l-blue-400',   icon: '⭐' },
  C: { badge: 'bg-yellow-100 text-yellow-800 border-yellow-200', ring: 'border-l-yellow-400', icon: '✅' },
  D: { badge: 'bg-gray-100 text-gray-600 border-gray-200',     ring: 'border-l-gray-300',   icon: '📋' },
}

function scoreColor(score) {
  if (score >= 72) return 'text-green-600'   // Tier A
  if (score >= 58) return 'text-blue-600'    // Tier B
  if (score >= 42) return 'text-yellow-600'  // Tier C
  return 'text-gray-500'                     // Tier D
}

function timeAgo(isoStr) {
  if (!isoStr) return ''
  const date = new Date(isoStr)
  // If time is midnight UTC, it's a day-level date (SimplifyJobs) — show Today/Yesterday/Xd ago
  const isMidnight = date.getUTCHours() === 0 && date.getUTCMinutes() === 0 && date.getUTCSeconds() === 0
  const diff = Date.now() - date.getTime()
  const days = Math.floor(diff / 86400000)
  if (isMidnight) {
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    return `${days}d ago`
  }
  // Exact timestamp — show precise time
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'Just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${days}d ago`
}

export default function JobCard({ job, onApplied, onHide }) {
  const tier = job.tier || 'D'
  const styles = TIER_STYLES[tier] || TIER_STYLES.D
  const score = job.best_score ?? 0

  async function handleApply() {
    window.open(job.apply_url, '_blank')
    try {
      await axios.post(`/api/jobs/${job.id}/apply`)
      onApplied(job.id)
    } catch (e) {
      console.error('Failed to mark as applied:', e)
    }
  }

  return (
    <div className={`bg-white rounded-xl border border-gray-200 border-l-4 ${styles.ring} shadow-sm hover:shadow-md transition-shadow p-4`}>
      <div className="flex items-start justify-between gap-3">
        {/* Left: job info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="font-bold text-gray-900 text-base leading-tight">{job.company}</h3>

            {/* Tier badge */}
            <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${styles.badge}`}>
              {styles.icon} Tier {tier}
            </span>

            {/* New badge */}
            {job.is_new && (
              <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold animate-pulse">
                🆕 New
              </span>
            )}

            {/* Applied badge */}
            {job.applied && (
              <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">
                ✔ Applied
              </span>
            )}
          </div>

          <p className="text-gray-700 font-medium text-sm leading-snug mb-2">{job.role}</p>

          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
            <span>📍 {job.location}</span>
            <span className={`font-medium ${job.job_type === 'contract' ? 'text-orange-600' : 'text-indigo-600'}`}>
              {job.job_type === 'contract' ? '💼 W2/Contract' : '🏢 Full-Time'}
            </span>
            <span>🌐 {job.source}</span>
            {job.posted_date && <span>🕐 {timeAgo(job.posted_date)}</span>}
          </div>
        </div>

        {/* Right: score + buttons */}
        <div className="flex flex-col items-center gap-2 shrink-0">
          <div className="text-center">
            <p className={`text-3xl font-black leading-none ${scoreColor(score)}`}>{score.toFixed(0)}%</p>
            <p className="text-xs text-gray-400 mt-0.5">ATS · {job.best_resume} Resume</p>
            {job.ats_score_ai != null && job.ats_score_fullstack != null && (
              <p className="text-xs text-gray-400 mt-0.5 leading-tight">
                AI {job.ats_score_ai?.toFixed(0)}% · FS {job.ats_score_fullstack?.toFixed(0)}%
              </p>
            )}
          </div>

          <button
            onClick={handleApply}
            disabled={job.applied}
            className={`text-sm font-medium px-4 py-1.5 rounded-lg transition-all ${
              job.applied
                ? 'bg-gray-100 text-gray-400 cursor-default'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hover:shadow'
            }`}
          >
            {job.applied ? 'Applied' : 'Apply Now'}
          </button>

          <button
            onClick={() => onHide(job.id)}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors"
            title="Hide this job"
          >
            ✕ Hide
          </button>
        </div>
      </div>
    </div>
  )
}
