import { useEffect, useState } from 'react'
import StatCard from '../components/StatCard'
import { api } from '../api/client'

export default function Scheduler() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [interval, setInterval] = useState<number>(
    () => (status?.interval_minutes as number) ?? 30,
  )

  const refresh = () => {
    api.scheduler.status().then((s) => {
      setStatus(s)
      setLoading(false)
      if (s.interval_minutes != null) setInterval(s.interval_minutes as number)
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
      let msg = 'Start failed'
      if (e instanceof Error) {
        try {
          const parsed = JSON.parse(e.message.replace(/^API \d+: /, ''))
          msg = parsed?.detail?.error?.message ?? parsed?.detail ?? e.message
        } catch { msg = e.message }
      }
      setMsg(msg)
    }
    setBusy(false); refresh()
  }
  const doStop = async () => {
    setBusy(true); setMsg(null); setError(null)
    try { await api.scheduler.stop(); setMsg('Stopped') } catch { setMsg('Stop failed') }
    setBusy(false); refresh()
  }

  if (loading) return <p style={{ color: '#64748b' }}>Loading…</p>

  return (
    <div>
      <h1 style={title}>Scheduler</h1>
      {error && <div style={errorBox}>{error}</div>}
      <div style={grid}>
        <StatCard label="Status" value={status?.running ? 'Running' : 'Stopped'} />
        <StatCard label="Enabled" value={status?.enabled ? 'Yes' : 'No'} />
        <StatCard label="Interval" value={`${(status?.interval_minutes as number) ?? '—'} min`} />
        <StatCard label="Last Run" value={(status?.last_run_status as string) ?? '—'} hint={(status?.last_run_at as string) ?? ''} />
      </div>
      <div style={{ marginTop: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
        <label style={{ fontSize: 14, color: '#374151', fontWeight: 600 }}>
          Interval (min):
          <input
            type="number"
            min={1}
            value={interval}
            onChange={(e) => setInterval(Math.max(1, Number(e.target.value) || 1))}
            disabled={busy || status?.running === true}
            style={intervalInput}
          />
        </label>
        <button onClick={doOnce} disabled={busy} style={btn}>
          {busy ? 'Running…' : 'Run Once'}
        </button>
        <button onClick={doStart} disabled={busy} style={{ ...btn, background: '#16a34a', color: '#fff' }}>Start</button>
        <button onClick={doStop} disabled={busy} style={{ ...btn, background: '#ef4444', color: '#fff' }}>Stop</button>
        {msg && <span style={{ fontSize: 13, color: msg.includes('failed') || msg.includes('error') || msg.includes('disabled') ? '#ef4444' : '#16a34a' }}>{msg}</span>}
      </div>
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }
const btn = {
  padding: '8px 20px', borderRadius: 6, border: 'none',
  background: '#2563eb', color: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: 14,
}
const errorBox = {
  padding: 12, background: '#fef2f2', border: '1px solid #fecaca',
  borderRadius: 8, color: '#dc2626', fontSize: 14, marginBottom: 16,
}
const intervalInput = {
  marginLeft: 8, padding: '6px 10px', borderRadius: 4,
  border: '1px solid #d1d5db', fontSize: 14, width: 64,
}
