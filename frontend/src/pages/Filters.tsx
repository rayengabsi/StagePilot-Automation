import { useEffect, useState } from 'react'
import { api } from '../api/client'

const LIST_FIELDS = [
  'excluded_keywords',
  'required_keywords',
  'excluded_titles',
  'required_titles',
  'excluded_companies',
  'required_companies',
  'excluded_locations',
  'required_locations',
  'employment_type_exclude',
  'employment_type_include',
  'seniority_exclude',
  'seniority_include',
  'visa_required_keywords',
  'visa_excluded_keywords',
  'excluded_sources',
  'included_sources',
] as const

export default function Filters() {
  const [filters, setFilters] = useState<Record<string, unknown>>({})
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    api.filters.get().then((f) => {
      setFilters(f)
      const initial: Record<string, string> = {}
      for (const key of LIST_FIELDS) {
        initial[key] = ((f[key] as string[]) ?? []).join(', ')
      }
      initial.remote_only = String(f.remote_only ?? false)
      initial.salary_min = String(f.salary_min ?? '')
      initial.salary_max = String(f.salary_max ?? '')
      initial.unknown_data_policy = String(f.unknown_data_policy ?? 'accept')
      setEditing(initial)
    })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMsg(null)
    const body: Record<string, unknown> = { ...filters }
    for (const key of LIST_FIELDS) {
      body[key] = (editing[key] ?? '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    }
    body.remote_only = editing.remote_only === 'true'
    body.salary_min = editing.salary_min ? Number(editing.salary_min) : null
    body.salary_max = editing.salary_max ? Number(editing.salary_max) : null
    body.unknown_data_policy = editing.unknown_data_policy || 'accept'
    try {
      await api.filters.update(body)
      setMsg('Saved!')
    } catch {
      setMsg('Save failed')
    }
    setSaving(false)
  }

  return (
    <div>
      <h1 style={title}>Filters</h1>
      <div style={form}>
        {LIST_FIELDS.map((key) => (
          <label key={key} style={field}>
            <span style={label}>{key.replace(/_/g, ' ')}</span>
            <input
              style={input}
              value={editing[key] ?? ''}
              onChange={(e) => setEditing({ ...editing, [key]: e.target.value })}
              placeholder="comma-separated"
            />
          </label>
        ))}
        <label style={field}>
          <span style={label}>remote_only</span>
          <select
            style={input}
            value={editing.remote_only ?? 'false'}
            onChange={(e) => setEditing({ ...editing, remote_only: e.target.value })}
          >
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </label>
        <label style={field}>
          <span style={label}>salary_min</span>
          <input
            style={input}
            type="number"
            value={editing.salary_min ?? ''}
            onChange={(e) => setEditing({ ...editing, salary_min: e.target.value })}
          />
        </label>
        <label style={field}>
          <span style={label}>salary_max</span>
          <input
            style={input}
            type="number"
            value={editing.salary_max ?? ''}
            onChange={(e) => setEditing({ ...editing, salary_max: e.target.value })}
          />
        </label>
        <label style={field}>
          <span style={label}>unknown_data_policy</span>
          <select
            style={input}
            value={editing.unknown_data_policy ?? 'accept'}
            onChange={(e) => setEditing({ ...editing, unknown_data_policy: e.target.value })}
          >
            <option value="accept">accept</option>
            <option value="reject">reject</option>
          </select>
        </label>
      </div>
      <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={handleSave} disabled={saving} style={saveBtn}>
          {saving ? 'Saving…' : 'Save Filters'}
        </button>
        {msg && <span style={{ fontSize: 13, color: msg === 'Saved!' ? '#16a34a' : '#ef4444' }}>{msg}</span>}
      </div>
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const form = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
  gap: 12,
}
const field = { display: 'flex', flexDirection: 'column' as const, gap: 4 }
const label = { fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase' as const }
const input = {
  padding: '8px 12px',
  border: '1px solid #e2e8f0',
  borderRadius: 6,
  fontSize: 14,
  background: '#fff',
}
const saveBtn = {
  padding: '8px 20px',
  borderRadius: 6,
  border: 'none',
  background: '#2563eb',
  color: '#fff',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: 14,
}
