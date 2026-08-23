import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import Section from '../components/Section'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { api } from '../api/client'

export default function Scheduler() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
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
      setMsg(res.success ? 'Run complete' : `Run finished: ${res.message ?? 'error'}`)
    } catch { setMsg('Run failed') }
    setBusy(false); refresh()
  }

  const doStart = async () => {
    setBusy(true); setMsg(null); setError(null)
    try {
      await api.scheduler.start(interval)
      setMsg('Started')
    } catch (e: unknown) {
      let errorMessage = 'Start failed'
      if (e instanceof Error) {
        try {
          const parsed = JSON.parse(e.message.replace(/^API \d+: /, ''))
          errorMessage = parsed?.detail?.error?.message ?? parsed?.detail ?? e.message
        } catch { errorMessage = e.message }
      }
      setMsg(errorMessage)
    }
    setBusy(false); refresh()
  }

  const doStop = async () => {
    setBusy(true); setMsg(null); setError(null)
    try { await api.scheduler.stop(); setMsg('Stopped') } catch { setMsg('Stop failed') }
    setBusy(false); refresh()
  }

  if (loading) return <LoadingState rows={3} />
  if (error) return <ErrorState message={error} onRetry={refresh} />

  const isRunning = status?.running === true
  const isEnabled = status?.enabled === true
  const statusVariant = isRunning ? 'success' : isEnabled ? 'neutral' : 'warning'

  return (
    <div>
      <PageHeader
        title="Scheduler"
        description="Control the LinkedIn discovery pipeline"
      />

      {/* Status Indicator */}
      <Section>
        <div style={styles.statusHero}>
          <div style={styles.statusMain}>
            <StatusBadge
              label={isRunning ? 'RUNNING' : isEnabled ? 'STOPPED' : 'DISABLED'}
              variant={statusVariant}
              dot={true}
            />
            {!isEnabled && (
              <p style={styles.disabledNote}>
                Scheduler is disabled in config/scheduler.toml. Set <code>enabled = true</code> to allow recurring runs.
              </p>
            )}
          </div>
        </div>
      </Section>

      {/* Pipeline Details */}
      <Section title="Pipeline Status">
        <div style={styles.detailGrid}>
          <DetailRow label="Interval" value={`${status?.interval_minutes ?? '—'} min`} />
          <DetailRow label="Last Run Status" value={status?.last_run_status as string ?? '—'} />
          <DetailRow label="Last Run At" value={status?.last_run_at ? new Date(status.last_run_at as string).toLocaleString() : '—'} />
          <DetailRow label="Last Run Fetched" value={status?.last_run_fetched != null ? String(status.last_run_fetched) : '—'} />
          <DetailRow label="Next Run" value={status?.next_run_at ? new Date(status.next_run_at as string).toLocaleString() : '—'} />
          <DetailRow label="Stop Requested" value={status?.stop_requested ? 'Yes' : 'No'} />
        </div>
      </Section>

      {/* Controls */}
      <Section title="Controls">
        <div style={styles.controls}>
          <div style={styles.intervalControl}>
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
            <button
              onClick={doOnce}
              disabled={busy}
              style={{ ...styles.btn, ...styles.btnPrimary }}
            >
              {busy ? 'Running…' : 'Run Once'}
            </button>
            <button
              onClick={doStart}
              disabled={busy || isRunning}
              style={{ ...styles.btn, ...styles.btnSuccess, ...(busy || isRunning ? styles.btnDisabled : {}) }}
            >
              Start Scheduler
            </button>
            <button
              onClick={doStop}
              disabled={busy || !isRunning}
              style={{ ...styles.btn, ...styles.btnDanger, ...(busy || !isRunning ? styles.btnDisabled : {}) }}
            >
              Stop Scheduler
            </button>
          </div>
        </div>

        {msg && (
          <div style={{
            ...styles.message,
            ...(msg.includes('failed') || msg.includes('error') || msg.includes('disabled')
              ? styles.messageError : styles.messageSuccess),
          }}>
            {msg}
          </div>
        )}
      </Section>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.detailRow}>
      <span style={styles.detailLabel}>{label}</span>
      <span style={styles.detailValue}>{value}</span>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  statusHero: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-6) 0',
  },
  statusMain: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 'var(--space-3)',
  },
  disabledNote: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    textAlign: 'center' as const,
    maxWidth: 400,
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
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
  },
  detailLabel: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
  },
  detailValue: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-900)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    fontVariantNumeric: 'tabular-nums',
  },
  controls: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--space-4)',
  },
  intervalControl: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
  },
  label: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-600)',
  },
  intervalInput: {
    width: 80,
    padding: 'var(--space-2) var(--space-3)',
    border: '1px solid var(--border-default)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--text-base)',
    background: 'var(--surface-card)',
    color: 'var(--gray-700)',
    outline: 'none',
    fontVariantNumeric: 'tabular-nums',
  },
  actions: {
    display: 'flex',
    gap: 'var(--space-3)',
    flexWrap: 'wrap' as const,
  },
  btn: {
    padding: 'var(--space-2) var(--space-5)',
    borderRadius: 'var(--radius-md)',
    border: 'none',
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  },
  btnPrimary: {
    background: 'var(--blue-600)',
    color: '#ffffff',
  },
  btnSuccess: {
    background: 'var(--green-600)',
    color: '#ffffff',
  },
  btnDanger: {
    background: 'var(--red-500)',
    color: '#ffffff',
  },
  btnDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  message: {
    padding: 'var(--space-3) var(--space-4)',
    borderRadius: 'var(--radius-lg)',
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
  },
  messageSuccess: {
    background: 'var(--green-50)',
    color: 'var(--green-700)',
    border: '1px solid var(--green-100)',
  },
  messageError: {
    background: 'var(--red-50)',
    color: 'var(--red-600)',
    border: '1px solid var(--red-100)',
  },
}
