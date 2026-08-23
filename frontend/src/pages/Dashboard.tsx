import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Briefcase, Star, User, Clock, Play, SlidersHorizontal, ArrowRight, Zap } from 'lucide-react'
import { api } from '../api/client'

interface HealthStatus {
  api: 'ok' | 'error' | 'loading'
  scheduler: 'running' | 'stopped' | 'loading'
}

interface Metrics {
  jobs: number | null
  matches: number | null
  profileScore: number | null
  profileName: string | null
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}

const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } },
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [health, setHealth] = useState<HealthStatus>({ api: 'loading', scheduler: 'loading' })
  const [metrics, setMetrics] = useState<Metrics>({ jobs: null, matches: null, profileScore: null, profileName: null })
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

        setHealth({
          api: h.status === 'fulfilled' ? 'ok' : 'error',
          scheduler: s.status === 'fulfilled' && (s.value as Record<string, unknown>).running
            ? 'running' : 'stopped',
        })

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
  const isRunning = health.scheduler === 'running'

  return (
    <motion.div variants={stagger} initial="hidden" animate="show">
      {/* Hero */}
      <motion.div variants={fadeUp} style={styles.hero}>
        <div style={styles.heroContent}>
          <h1 style={styles.greeting}>{greeting}</h1>
          <p style={styles.heroSub}>
            {isRunning
              ? 'Your job discovery pipeline is running automatically.'
              : 'Your next opportunity is waiting to be discovered.'}
          </p>
        </div>
        <button onClick={() => navigate('/scheduler')} style={styles.heroBtn}>
          <Play size={14} />
          Run discovery
        </button>
      </motion.div>

      {/* System Status */}
      <motion.div variants={fadeUp} style={styles.statusBar}>
        <div style={styles.statusItem}>
          <div style={{
            ...styles.statusDot,
            background: health.api === 'ok' ? 'var(--sp-green)' : health.api === 'loading' ? 'var(--sp-amber)' : 'var(--sp-red)',
          }} />
          <span style={styles.statusLabel}>API</span>
        </div>
        <div style={styles.statusDivider} />
        <div style={styles.statusItem}>
          <div style={{
            ...styles.statusDot,
            background: isRunning ? 'var(--sp-green)' : 'var(--sp-text-muted)',
          }} />
          <span style={styles.statusLabel}>Scheduler {isRunning ? 'Running' : 'Stopped'}</span>
        </div>
        <div style={styles.statusDivider} />
        <div style={styles.statusItem}>
          <div style={{ ...styles.statusDot, background: 'var(--sp-green)' }} />
          <span style={styles.statusLabel}>LinkedIn</span>
        </div>
        <div style={styles.statusDivider} />
        <div style={styles.statusItem}>
          <div style={{ ...styles.statusDot, background: 'var(--sp-green)' }} />
          <span style={styles.statusLabel}>Telegram</span>
        </div>
      </motion.div>

      {/* Metrics */}
      <motion.div variants={fadeUp} style={styles.metricsGrid}>
        <MetricCard icon={<Briefcase size={16} />} label="Jobs discovered" value={metrics.jobs ?? 0} color="var(--sp-accent)" />
        <MetricCard icon={<Star size={16} />} label="Matches" value={metrics.matches ?? 0} color="var(--sp-green)" />
        <MetricCard icon={<User size={16} />} label="Profile strength" value={`${metrics.profileScore ?? 0}%`} color="var(--sp-purple)" />
        <MetricCard icon={<Clock size={16} />} label="Automation interval" value={scheduler ? `${scheduler.interval_minutes ?? 30}m` : '—'} color="var(--sp-amber)" />
      </motion.div>

      {/* Pipeline */}
      <motion.div variants={fadeUp}>
        <h2 style={styles.sectionTitle}>Pipeline</h2>
        <div style={styles.pipeline}>
          {['LinkedIn', 'Discovery', 'Filters', 'Matching', 'Telegram'].map((stage, i) => (
            <div key={stage} style={styles.pipelineStage}>
              <div style={{
                ...styles.pipelineNode,
                background: isRunning ? 'var(--sp-accent-dim)' : 'var(--sp-surface-raised)',
                borderColor: isRunning ? 'var(--sp-accent-border)' : 'var(--sp-border)',
              }}>
                <span style={{
                  ...styles.pipelineLabel,
                  color: isRunning ? 'var(--sp-accent)' : 'var(--sp-text-secondary)',
                }}>{stage}</span>
              </div>
              {i < 4 && (
                <div style={{
                  ...styles.pipelineArrow,
                  color: isRunning ? 'var(--sp-accent)' : 'var(--sp-text-muted)',
                }}>
                  <ArrowRight size={14} />
                </div>
              )}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Quick Actions */}
      <motion.div variants={fadeUp}>
        <h2 style={styles.sectionTitle}>Quick actions</h2>
        <div style={styles.actionsGrid}>
          <ActionCard
            title="Run pipeline"
            description="Execute discovery once"
            onClick={() => navigate('/scheduler')}
            icon={<Zap size={18} />}
            color="var(--sp-accent)"
          />
          <ActionCard
            title="Configure filters"
            description="Set discovery preferences"
            onClick={() => navigate('/filters')}
            icon={<SlidersHorizontal size={18} />}
            color="var(--sp-purple)"
          />
          <ActionCard
            title="View matches"
            description="Review recommendations"
            onClick={() => navigate('/matches')}
            icon={<Star size={18} />}
            color="var(--sp-green)"
          />
        </div>
      </motion.div>
    </motion.div>
  )
}

function MetricCard({ icon, label, value, color }: {
  icon: React.ReactNode; label: string; value: string | number; color: string
}) {
  return (
    <div style={styles.metricCard}>
      <div style={{ ...styles.metricIcon, color, background: `${color}15` }}>{icon}</div>
      <div style={styles.metricValue}>{value}</div>
      <div style={styles.metricLabel}>{label}</div>
    </div>
  )
}

function ActionCard({ title, description, onClick, icon, color }: {
  title: string; description: string; onClick: () => void; icon: React.ReactNode; color: string
}) {
  return (
    <motion.button
      onClick={onClick}
      style={styles.actionCard}
      whileHover={{ borderColor: 'rgba(255, 255, 255, 0.10)', background: 'var(--sp-surface-hover)' }}
      whileTap={{ scale: 0.98 }}
    >
      <div style={{ ...styles.actionIcon, color }}>{icon}</div>
      <div style={styles.actionContent}>
        <div style={styles.actionTitle}>{title}</div>
        <div style={styles.actionDesc}>{description}</div>
      </div>
      <ArrowRight size={14} style={{ color: 'var(--sp-text-muted)', flexShrink: 0 }} />
    </motion.button>
  )
}

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

const styles: Record<string, React.CSSProperties> = {
  hero: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 'var(--space-6)',
    gap: 'var(--space-4)',
  },
  heroContent: { flex: 1 },
  greeting: {
    fontSize: 'var(--text-3xl)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-text-primary)',
    letterSpacing: 'var(--tracking-tight)',
    marginBottom: 'var(--space-2)',
  },
  heroSub: {
    fontSize: 'var(--text-md)',
    color: 'var(--sp-text-secondary)',
    lineHeight: 'var(--leading-relaxed)',
  },
  heroBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-2-5) var(--space-5)',
    borderRadius: 'var(--radius-lg)',
    border: 'none',
    background: 'var(--sp-accent)',
    color: '#fff',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)',
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
    whiteSpace: 'nowrap',
  },
  statusBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-4)',
    padding: 'var(--space-3) var(--space-5)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--sp-border)',
    marginBottom: 'var(--space-6)',
    flexWrap: 'wrap',
  },
  statusItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    flexShrink: 0,
  },
  statusLabel: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    fontWeight: 'var(--weight-medium)',
  },
  statusDivider: {
    width: 1,
    height: 16,
    background: 'var(--sp-border)',
  },
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 'var(--space-4)',
    marginBottom: 'var(--space-8)',
  },
  metricCard: {
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    padding: 'var(--space-5)',
    border: '1px solid var(--sp-border)',
  },
  metricIcon: {
    width: 32,
    height: 32,
    borderRadius: 'var(--radius-md)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 'var(--space-3)',
  },
  metricValue: {
    fontSize: 'var(--text-2xl)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-text-primary)',
    lineHeight: 'var(--leading-tight)',
    fontVariantNumeric: 'tabular-nums',
  },
  metricLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
    marginTop: 'var(--space-1)',
    fontWeight: 'var(--weight-medium)',
  },
  sectionTitle: {
    fontSize: 'var(--text-lg)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    marginBottom: 'var(--space-4)',
  },
  pipeline: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-5)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-border)',
    marginBottom: 'var(--space-8)',
    overflowX: 'auto',
  },
  pipelineStage: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
  },
  pipelineNode: {
    padding: 'var(--space-2) var(--space-4)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid',
    whiteSpace: 'nowrap',
  },
  pipelineLabel: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
  },
  pipelineArrow: {
    display: 'flex',
    alignItems: 'center',
    flexShrink: 0,
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
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-border)',
    cursor: 'pointer',
    textAlign: 'left',
    width: '100%',
    transition: 'all var(--transition-fast)',
    color: 'inherit',
  },
  actionIcon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 36,
    height: 36,
    borderRadius: 'var(--radius-md)',
    background: 'rgba(255, 255, 255, 0.04)',
    flexShrink: 0,
  },
  actionContent: { flex: 1 },
  actionTitle: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
  },
  actionDesc: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-muted)',
    marginTop: 2,
  },
}
