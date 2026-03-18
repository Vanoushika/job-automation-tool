import axios from 'axios'

const TIER_STYLES = {
  A: { badge: 'bg-green-100 text-green-800 border-green-200',  ring: 'border-l-green-400',  icon: '🔥' },
  B: { badge: 'bg-blue-100 text-blue-800 border-blue-200',     ring: 'border-l-blue-400',   icon: '⭐' },
  C: { badge: 'bg-yellow-100 text-yellow-800 border-yellow-200', ring: 'border-l-yellow-400', icon: '✅' },
  D: { badge: 'bg-gray-100 text-gray-600 border-gray-200',     ring: 'border-l-gray-300',   icon: '📋' },
}

function scoreColor(score) {
  if (score >= 85) return 'text-green-600'
  if (score >= 75) return 'text-blue-600'
  if (score >= 65) return 'text-yellow-600'
  return 'text-gray-500'
}

function timeAgo(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

export default function JobCard({ job, onApplied }) {
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
            <span>📄 {job.best_resume} Resume</span>
            <span>🌐 {job.source}</span>
            {job.posted_date && <span>🕐 {timeAgo(job.posted_date)}</span>}
          </div>
        </div>

        {/* Right: score + button */}
        <div className="flex flex-col items-center gap-2 shrink-0">
          <div className="text-center">
            <p className={`text-3xl font-black leading-none ${scoreColor(score)}`}>{score.toFixed(0)}%</p>
            <p className="text-xs text-gray-400 mt-0.5">ATS match</p>
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
        </div>
      </div>
    </div>
  )
}
