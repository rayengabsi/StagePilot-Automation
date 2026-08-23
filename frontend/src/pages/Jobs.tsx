import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { ExternalLink, MapPin, Briefcase, Building2 } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import Pagination from '../components/Pagination'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import { api } from '../api/client'

interface Job {
  id: number
  title: string
  company: string | null
  location: string | null
  url: string
  employment_type: string | null
  seniority: string | null
  remote_status: string | null
  posted_at: string | null
  created_at: string | null
}

const PAGE_SIZE = 25

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.03 } },
}

const fadeUp = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as const } },
}

export default function Jobs() {
  const [items, setItems] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.jobs({ limit: PAGE_SIZE, offset })
      setItems(res.items as unknown as Job[])
      setTotal(res.total)
    } catch {
      setError('Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [offset])

  useEffect(() => { loadJobs() }, [loadJobs])

  return (
    <div>
      <PageHeader
        title="Jobs"
        description={`${total} opportunities discovered from LinkedIn`}
      />

      {error && <ErrorState message={error} onRetry={loadJobs} />}

      {!error && loading && <LoadingState rows={5} />}

      {!error && !loading && items.length === 0 && (
        <EmptyState
          title="No jobs discovered yet"
          description="Run the discovery pipeline to start finding opportunities."
        />
      )}

      {!error && !loading && items.length > 0 && (
        <motion.div variants={stagger} initial="hidden" animate="show">
          {items.map((job) => (
            <motion.div key={job.id} variants={fadeUp}>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                style={styles.card}
              >
                <div style={styles.cardMain}>
                  <h3 style={styles.title}>{job.title}</h3>
                  <div style={styles.meta}>
                    {job.company && (
                      <span style={styles.metaItem}>
                        <Building2 size={13} />
                        {job.company}
                      </span>
                    )}
                    {job.location && (
                      <span style={styles.metaItem}>
                        <MapPin size={13} />
                        {job.location}
                      </span>
                    )}
                    {job.employment_type && (
                      <span style={styles.metaItem}>
                        <Briefcase size={13} />
                        {job.employment_type}
                      </span>
                    )}
                    {job.seniority && (
                      <span style={styles.tag}>{job.seniority}</span>
                    )}
                    {job.remote_status && (
                      <span style={styles.tag}>{job.remote_status}</span>
                    )}
                  </div>
                  <div style={styles.time}>
                    {job.created_at && timeAgo(job.created_at)}
                  </div>
                </div>
                <ExternalLink size={14} style={{ color: 'var(--sp-text-muted)', flexShrink: 0 }} />
              </a>
            </motion.div>
          ))}
          <Pagination
            offset={offset}
            total={total}
            pageSize={PAGE_SIZE}
            onPageChange={setOffset}
          />
        </motion.div>
      )}
    </div>
  )
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 'var(--space-4)',
    padding: 'var(--space-4) var(--space-5)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--sp-border)',
    marginBottom: 'var(--space-2)',
    textDecoration: 'none',
    color: 'inherit',
    transition: 'all var(--transition-fast)',
  },
  cardMain: { flex: 1, minWidth: 0 },
  title: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    marginBottom: 'var(--space-1-5)',
    lineHeight: 'var(--leading-tight)',
  },
  meta: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    flexWrap: 'wrap',
    marginBottom: 'var(--space-1-5)',
  },
  metaItem: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-1)',
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
  },
  tag: {
    display: 'inline-block',
    padding: '1px 8px',
    borderRadius: 'var(--radius-full)',
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-medium)',
    background: 'rgba(255, 255, 255, 0.04)',
    color: 'var(--sp-text-secondary)',
    border: '1px solid var(--sp-border)',
  },
  time: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
  },
}
