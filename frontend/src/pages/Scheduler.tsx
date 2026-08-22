import { useEffect, useState } from 'react'
import StatCard from '../components/StatCard'
import { api } from '../api/client'

export default function Scheduler() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const refresh = () => {
    api.scheduler.status().then((s) => { setStatus(s); setLoading(false) })
  }

  useEffect(refresh, [])

  const doOnce = async () => {
    setBusy(true); setMsg(null)
    try { await api.scheduler.once(); setMsg('Run complete') } catch { setMsg('Run failed') }
    setBusy(false); refresh()
  }
  const doStart = async () => {
    setBusy(true); setMsg(null)
    try { await api.scheduler.start(); setMsg('Started') } catch { setMsg('Start failed') }
    setBusy(false); refresh()
  }
  const doStop = async () => {
    setBusy(true); setMsg(null)
    try { await api.scheduler.stop(); setMsg('Stopped') } catch { setMsg('Stop failed') }
    setBusy(false); refresh()
  }

  if (loading) return <p style={{ color: '#64748b' }}>Loading…</p>

  return (
    <div>
      <h1 style={title}>Scheduler</h1>
      <div style={grid}>
        <StatCard label="Status" value={status?.running ? 'Running' : 'Stopped'} />
        <StatCard label="Enabled" value={status?.enabled ? 'Yes' : 'No'} />
        <StatCard label="Interval" value={`${(status?.interval_minutes as number) ?? '—'} min`} />
        <StatCard label="Last Run" value={(status?.last_run_status as string) ?? '—'} hint={(status?.last_run_at as string) ?? ''} />
      </div>
      <div style={{ marginTop: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={doOnce} disabled={busy} style={btn}>Run Once</button>
        <button onClick={doStart} disabled={busy} style={{ ...btn, background: '#16a34a', color: '#fff' }}>Start</button>
        <button onClick={doStop} disabled={busy} style={{ ...btn, background: '#ef4444', color: '#fff' }}>Stop</button>
        {msg && <span style={{ fontSize: 13, color: msg.includes('failed') ? '#ef4444' : '#16a34a' }}>{msg}</span>}
      </div>
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }
const btn = {
  padding: '8px 20px',
  borderRadius: 6,
  border: 'none',
  background: '#2563eb',
  color: '#fff',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: 14,
}
