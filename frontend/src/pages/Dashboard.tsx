import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import Section from '../components/Section'
import { api } from '../api/client'

interface HealthStatus {
  api: 'ok' | 'error' | 'loading'
  scheduler: 'running' | 'stopped' | 'loading'
  linkedin: string
  telegram: string
}

interface Metrics {
  jobs: number | null
  matches: number | null
  profileScore: number | null
  profileName: string | null
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [health, setHealth] = useState<HealthStatus>({
    api: 'loading', scheduler: 'loading', linkedin: '—', telegram: '—',
  })
  const [metrics, setMetrics] = useState<Metrics>({
    jobs: null, matches: null, profileScore: null, profileName: null,
  })
  const [scheduler, setScheduler] = useState<Record<string, unknown> | null>(null)
  const [, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [h, j, m, s, p] = await Promise.allSettled([
          api.health(),
          api.jobs({ limit: 1 }),
          api.matches({ limit: 1 }),
          api.scheduler.status(),
          api.profile(),
        ])

        setHealth((prev) => ({
          ...prev,
          api: h.status === 'fulfilled' ? 'ok' : 'error',
          scheduler: s.status === 'fulfilled' && (s.value as Record<string, unknown>).running
            ? 'running' : 'stopped',
        }))

        if (j.status === 'fulfilled') setMetrics((prev) => ({ ...prev, jobs: (j.value as { total: number }).total }))
        if (m.status === 'fulfilled') setMetrics((prev) => ({ ...prev, matches: (m.value as { total: number }).total }))
        if (s.status === 'fulfilled') setScheduler(s.value as Record<string, unknown>)
        if (p.status === 'fulfilled') {
          const prof = p.value as Record<string, unknown>
          const pi = prof.personal_info as Record<string, unknown> | undefined
          const comp = prof.completeness as Record<string, unknown> | undefined
          setMetrics((prev) => ({
            ...prev,
            profileName: (pi?.full_name as string) || '—',
            profileScore: (comp?.score as number) ?? 0,
          }))
        }
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const greeting = getGreeting()

  return (
    <div>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>{greeting}</h1>
          <p style={styles.subtitle}>Here's what's happening with your job discovery pipeline.</p>
        </div>
      </div>

      {/* System Status */}
      <Section title="System Status">
        <div style={styles.statusGrid}>
          <StatusRow label="API" status={health.api} />
          <StatusRow label="Scheduler" status={health.scheduler} />
          <StatusRow label="LinkedIn" status="ok" detail="Authenticated" />
          <StatusRow label="Telegram" status="ok" detail="Configured" />
        </div>
      </Section>

      {/* Key Metrics */}
      <Section title="Overview">
        <div style={styles.metricsGrid}>
          <StatCard
            label="Jobs Discovered"
            value={metrics.jobs ?? '—'}
            hint="Total in database"
          />
          <StatCard
            label="Matches"
            value={metrics.matches ?? '—'}
            hint="Total recommendations"
          />
          <StatCard
            label="Profile"
            value={metrics.profileName ?? '—'}
            hint={`Completeness: ${metrics.profileScore ?? '—'}%`}
          />
          <StatCard
            label="Scheduler"
            value={health.scheduler === 'running' ? 'Running' : 'Stopped'}
            hint={scheduler ? `Interval: ${scheduler.interval_minutes ?? '—'} min` : ''}
          />
        </div>
      </Section>

      {/* Quick Actions */}
      <Section title="Quick Actions">
        <div style={styles.actionsGrid}>
          <ActionCard
            title="Run Pipeline"
            description="Execute the LinkedIn discovery pipeline once"
            onClick={() => navigate('/scheduler')}
            icon={<PlayIcon />}
          />
          <ActionCard
            title="Configure Filters"
            description="Set up job discovery preferences"
            onClick={() => navigate('/filters')}
            icon={<FilterIcon />}
          />
          <ActionCard
            title="View Matches"
            description="Review your latest job recommendations"
            onClick={() => navigate('/matches')}
            icon={<StarIcon />}
          />
        </div>
      </Section>
    </div>
  )
}

function StatusRow({ label, status, detail }: { label: string; status: string; detail?: string }) {
  const variant = status === 'ok' || status === 'running'
    ? 'success'
    : status === 'error' ? 'error'
    : status === 'loading' ? 'info' : 'neutral'
  const text = status === 'loading' ? 'Checking…'
    : status === 'ok' || status === 'running' ? 'Connected'
    : status === 'error' ? 'Error'
    : status === 'stopped' ? 'Stopped'
    : status

  return (
    <div style={styles.statusRow}>
      <span style={styles.statusLabel}>{label}</span>
      <StatusBadge label={detail || text} variant={variant} />
    </div>
  )
}

function ActionCard({ title, description, onClick, icon }: {
  title: string; description: string; onClick: () => void; icon: React.ReactNode
}) {
  return (
    <button onClick={onClick} style={styles.actionCard}>
      <span style={styles.actionIcon}>{icon}</span>
      <div>
        <div style={styles.actionTitle}>{title}</div>
        <div style={styles.actionDesc}>{description}</div>
      </div>
    </button>
  )
}

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function PlayIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="var(--blue-600)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="6,3 17,10 6,17" fill="var(--blue-100)" stroke="var(--blue-600)" />
    </svg>
  )
}

function FilterIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="var(--gray-600)" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 4h16M5 8h10M7 12h6M9 16h2" />
    </svg>
  )
}

function StarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="var(--amber-500)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 2l2.09 4.24L17 6.94l-3.5 3.41.83 4.81L10 12.77l-4.33 2.39.83-4.81L3 6.94l4.91-.7z" fill="var(--amber-100)" />
    </svg>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    marginBottom: 'var(--space-8)',
  },
  title: {
    fontSize: 'var(--text-xl)',
    fontWeight: 'var(--weight-bold)' as unknown as number,
    color: 'var(--gray-900)',
  },
  subtitle: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-500)',
    marginTop: 'var(--space-1)',
  },
  statusGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 'var(--space-3)',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 'var(--space-3) var(--space-4)',
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
  },
  statusLabel: {
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
    color: 'var(--gray-700)',
  },
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 'var(--space-4)',
  },
  actionsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: 'var(--space-3)',
  },
  actionCard: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-4)',
    padding: 'var(--space-4) var(--space-5)',
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
    cursor: 'pointer',
    textAlign: 'left' as const,
    transition: 'all var(--transition-fast)',
    width: '100%',
  },
  actionIcon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 40,
    height: 40,
    borderRadius: 'var(--radius-lg)',
    background: 'var(--gray-50)',
    border: '1px solid var(--border-default)',
    flexShrink: 0,
  },
  actionTitle: {
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-900)',
  },
  actionDesc: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    marginTop: 2,
  },
}
