import { useEffect, useState } from 'react'
import Table from '../components/Table'
import { api } from '../api/client'

interface Job {
  id: number
  title: string
  company: string | null
  location: string | null
  employment_type: string | null
  seniority: string | null
  posted_at: string | null
  url: string
}

const PAGE_SIZE = 25

export default function Jobs() {
  const [items, setItems] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.jobs({ limit: PAGE_SIZE, offset })
      .then((res) => {
        setItems(res.items as unknown as Job[])
        setTotal(res.total)
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load jobs')
        setLoading(false)
      })
  }, [offset])

  const hasNext = offset + PAGE_SIZE < total

  return (
    <div>
      <h1 style={title}>Jobs</h1>
      {error && <div style={errorBox}>{error}</div>}
      {loading ? (
        <p style={{ color: '#64748b' }}>Loading…</p>
      ) : (
        <>
          <Table
            columns={['ID', 'Title', 'Company', 'Location', 'Type', 'Seniority', 'Posted']}
            rows={items.map((j) => [
              j.id,
              <a href={j.url} target="_blank" rel="noopener noreferrer" style={link}>{j.title}</a>,
              j.company,
              j.location,
              j.employment_type,
              j.seniority,
              j.posted_at ? new Date(j.posted_at).toLocaleDateString() : '—',
            ])}
            empty="No jobs found"
          />
          <div style={paging}>
            <button disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)} style={btn}>
              ← Previous
            </button>
            <span style={{ fontSize: 13, color: '#64748b' }}>
              {total === 0 ? '0' : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)}`} of {total}
            </span>
            <button disabled={!hasNext} onClick={() => setOffset(offset + PAGE_SIZE)} style={btn}>
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const paging = { display: 'flex', alignItems: 'center', gap: 16, marginTop: 16, justifyContent: 'center' }
const btn = {
  padding: '6px 14px', borderRadius: 6, border: '1px solid #e2e8f0',
  background: '#fff', cursor: 'pointer', fontSize: 13,
}
const link = { color: '#2563eb', textDecoration: 'none', cursor: 'pointer' }
const errorBox = {
  padding: 12, background: '#fef2f2', border: '1px solid #fecaca',
  borderRadius: 8, color: '#dc2626', fontSize: 14, marginBottom: 16,
}
