import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function Profile() {
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    api.profile().then(setProfile)
  }, [])

  if (!profile) return <p style={{ color: '#64748b' }}>Loading…</p>

  return (
    <div>
      <h1 style={title}>Profile</h1>
      <div style={card}>
        {Object.entries(profile).map(([k, v]) => (
          <div key={k} style={row}>
            <span style={label}>{k.replace(/_/g, ' ')}</span>
            <span style={value}>{v == null ? '—' : String(v)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const card = { background: '#fff', borderRadius: 10, border: '1px solid #e2e8f0', padding: 24 }
const row = {
  display: 'flex',
  justifyContent: 'space-between',
  padding: '10px 0',
  borderBottom: '1px solid #f1f5f9',
}
const label = { fontSize: 13, fontWeight: 600, color: '#64748b', textTransform: 'uppercase' as const }
const value = { fontSize: 14, color: '#0f172a' }
