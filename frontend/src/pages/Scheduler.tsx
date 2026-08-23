import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Square, RotateCw, Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import Section from '../components/Section'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { api } from '../api/client'

const fadeUp = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as const } },
}

export default function Scheduler() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [interval, setIntervalValue] = useState<number>(30)

  const refresh = () => {
    api.scheduler.status().then((s) => {
      setStatus(s)
      setLoading(false)
      if (s.interval_minutes != null) setIntervalValue(s.interval_minutes as number)
    }).catch(() => { setError('Failed to load status'); setLoading(false) })
  }

  useEffect(refresh, [])

  const doOnce = async () => {
    setBusy(true); setMsg(null); setError(null)
    try {
      const res = await api.scheduler.once() as Record<string, unknown>
      setMsg({ type: res.success ? 'success' : 'error', text: res.success ? 'Pipeline run complete' : `Run finished: ${res.message ?? 'error'}` })
    } catch { setMsg({ type: 'error', text: 'Pipeline run failed' }) }
    setBusy(false); refresh()
  }

  const doStart = async () => {
    setBusy(true); setMsg(null); setError(null)
    try {
      await api.scheduler.start(interval)
      setMsg({ type: 'success', text: 'Automation started' })
    } catch (e: unknown) {
      let errorMessage = 'Start failed'
      if (e instanceof Error) {
        try {
          const parsed = JSON.parse(e.message.replace(/^API \d+: /, ''))
          errorMessage = parsed?.detail?.error?.message ?? parsed?.detail ?? e.message
        } catch { errorMessage = e.message }
      }
      setMsg({ type: 'error', text: errorMessage })
    }
    setBusy(false); refresh()
  }

  const doStop = async () => {
    setBusy(true); setMsg(null); setError(null)
    try { await api.scheduler.stop(); setMsg({ type: 'success', text: 'Automation stopped' }) }
    catch { setMsg({ type: 'error', text: 'Stop failed' }) }
    setBusy(false); refresh()
  }

  if (loading) return <LoadingState rows={3} />
  if (error) return <ErrorState message={error} onRetry={refresh} />

  const isRunning = status?.running === true
  const isEnabled = status?.enabled === true

  return (
    <div>
      <PageHeader title="Automation" description="Control the LinkedIn discovery pipeline" />

      <motion.div initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}>
        {/* Status Hero */}
        <motion.div variants={fadeUp} style={styles.statusHero}>
          <div style={styles.statusHeroContent}>
            <div style={{
              ...styles.statusIndicator,
              background: isRunning ? 'var(--sp-green-dim)' : isEnabled ? 'rgba(255, 255, 255, 0.04)' : 'var(--sp-amber-dim)',
              borderColor: isRunning ? 'var(--sp-green-border)' : isEnabled ? 'var(--sp-border)' : 'var(--sp-amber-border)',
            }}>
              <div style={{
                ...styles.statusDot,
                background: isRunning ? 'var(--sp-green)' : 'var(--sp-text-muted)',
              }} />
              <span style={{
                ...styles.statusText,
                color: isRunning ? 'var(--sp-green)' : 'var(--sp-text-secondary)',
              }}>
                {isRunning ? 'Running' : isEnabled ? 'Stopped' : 'Disabled'}
              </span>
            </div>
            {!isEnabled && (
              <div style={styles.disabledBanner}>
                <AlertTriangle size={14} />
                <span>Recurring discovery is disabled. Set <code style={styles.code}>enabled = true</code> in config/scheduler.toml</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Pipeline Flow */}
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
                  <div style={{ ...styles.pipelineArrow, color: isRunning ? 'var(--sp-accent)' : 'var(--sp-text-muted)' }}>
                    <ArrowRight size={14} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </motion.div>

        {/* Pipeline Details */}
        <motion.div variants={fadeUp}>
          <Section title="Status">
            <div style={styles.detailGrid}>
              <DetailRow icon={<Clock size={14} />} label="Interval" value={`${status?.interval_minutes ?? '\u2014'} min`} />
              <DetailRow icon={<CheckCircle2 size={14} />} label="Last run" value={status?.last_run_at ? new Date(status.last_run_at as string).toLocaleString() : '\u2014'} />
              <DetailRow icon={<Play size={14} />} label="Jobs fetched" value={status?.last_run_fetched != null ? String(status.last_run_fetched) : '\u2014'} />
              <DetailRow icon={<Clock size={14} />} label="Next run" value={status?.next_run_at ? new Date(status.next_run_at as string).toLocaleString() : '\u2014'} />
            </div>
          </Section>
        </motion.div>

        {/* Controls */}
        <motion.div variants={fadeUp}>
          <Section title="Controls">
            <div style={styles.controls}>
              <div style={styles.intervalRow}>
                <label style={styles.label}>Interval (minutes)</label>
                <input
                  type="number"
                  min={1}
                  value={interval}
                  onChange={(e) => setIntervalValue(Math.max(1, Number(e.target.value) || 1))}
                  disabled={busy || isRunning}
                  style={styles.intervalInput}
                />
              </div>
              <div style={styles.actions}>
                <motion.button
                  onClick={doOnce}
                  disabled={busy}
                  style={{ ...styles.btn, ...styles.btnPrimary, opacity: busy ? 0.5 : 1 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <RotateCw size={14} />
                  {busy ? 'Running\u2026' : 'Run once'}
                </motion.button>
                <motion.button
                  onClick={doStart}
                  disabled={busy || isRunning}
                  style={{ ...styles.btn, ...styles.btnSuccess, opacity: busy || isRunning ? 0.5 : 1 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <Play size={14} />
                  Start
                </motion.button>
                <motion.button
                  onClick={doStop}
                  disabled={busy || !isRunning}
                  style={{ ...styles.btn, ...styles.btnDanger, opacity: busy || !isRunning ? 0.5 : 1 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <Square size={14} />
                  Stop
                </motion.button>
              </div>
            </div>

            {msg && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  ...styles.message,
                  ...(msg.type === 'error' ? styles.messageError : styles.messageSuccess),
                }}
              >
                {msg.type === 'error' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
                {msg.text}
              </motion.div>
            )}
          </Section>
        </motion.div>
      </motion.div>
    </div>
  )
}

function DetailRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div style={styles.detailRow}>
      <div style={styles.detailLeft}>
        <span style={styles.detailIcon}>{icon}</span>
        <span style={styles.detailLabel}>{label}</span>
      </div>
      <span style={styles.detailValue}>{value}</span>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  statusHero: {
    marginBottom: 'var(--space-6)',
  },
  statusHeroContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
  },
  statusIndicator: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-2) var(--space-4)',
    borderRadius: 'var(--radius-full)',
    border: '1px solid',
    width: 'fit-content',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
  },
  statusText: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)',
  },
  disabledBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-3) var(--space-4)',
    borderRadius: 'var(--radius-md)',
    background: 'var(--sp-amber-dim)',
    border: '1px solid var(--sp-amber-border)',
    color: 'var(--sp-amber)',
    fontSize: 'var(--text-sm)',
  },
  code: {
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--text-xs)',
    padding: '1px 5px',
    borderRadius: 'var(--radius-xs)',
    background: 'rgba(255, 255, 255, 0.06)',
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
    marginBottom: 'var(--space-6)',
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
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
    gap: 'var(--space-3)',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 'var(--space-3) var(--space-4)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--sp-border)',
  },
  detailLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
  },
  detailIcon: {
    color: 'var(--sp-text-muted)',
    display: 'flex',
  },
  detailLabel: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    fontWeight: 'var(--weight-medium)',
  },
  detailValue: {
    fontSize: 'var(--text-md)',
    color: 'var(--sp-text-primary)',
    fontWeight: 'var(--weight-semibold)',
    fontVariantNumeric: 'tabular-nums',
  },
  controls: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-4)',
  },
  intervalRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
  },
  label: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
    color: 'var(--sp-text-secondary)',
  },
  intervalInput: {
    width: 80,
    padding: 'var(--space-2) var(--space-3)',
    border: '1px solid var(--sp-border)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--text-md)',
    background: 'var(--sp-surface-raised)',
    color: 'var(--sp-text-primary)',
    outline: 'none',
    fontVariantNumeric: 'tabular-nums',
  },
  actions: {
    display: 'flex',
    gap: 'var(--space-3)',
    flexWrap: 'wrap',
  },
  btn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-2) var(--space-5)',
    borderRadius: 'var(--radius-md)',
    border: 'none',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)',
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  },
  btnPrimary: { background: 'var(--sp-accent)', color: '#fff' },
  btnSuccess: { background: 'var(--sp-green)', color: 'var(--sp-text-inverted)' },
  btnDanger: { background: 'var(--sp-red)', color: '#fff' },
  message: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-3) var(--space-4)',
    borderRadius: 'var(--radius-lg)',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
    marginTop: 'var(--space-4)',
  },
  messageSuccess: {
    background: 'var(--sp-green-dim)',
    color: 'var(--sp-green)',
    border: '1px solid var(--sp-green-border)',
  },
  messageError: {
    background: 'var(--sp-red-dim)',
    color: 'var(--sp-red)',
    border: '1px solid var(--sp-red-border)',
  },
}
