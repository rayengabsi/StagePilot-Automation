import { useEffect, useState } from 'react'
import Table from '../components/Table'
import { api } from '../api/client'

interface Match {
  id: number
  job_id: number
  job_title: string
  job_company: string | null
  final_score: number
  status: string
  hard_rule_passed: boolean
  created_at: string | null
}

const PAGE_SIZE = 25

export default function Matches() {
  const [items, setItems] = useState<Match[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.matches({ limit: PAGE_SIZE, offset }).then((res) => {
      setItems(res.items as unknown as Match[])
      setTotal(res.total)
      setLoading(false)
    })
  }, [offset])

  const hasNext = offset + PAGE_SIZE < total

  return (
    <div>
      <h1 style={title}>Matches</h1>
      {loading ? (
        <p style={{ color: '#64748b' }}>Loading…</p>
      ) : (
        <>
          <Table
            columns={['ID', 'Job ID', 'Title', 'Company', 'Score', 'Status', 'Hard Pass']}
            rows={items.map((m) => [
              m.id,
              m.job_id,
              m.job_title,
              m.job_company,
              m.final_score.toFixed(2),
              m.status,
              m.hard_rule_passed ? '✓' : '✗',
            ])}
            empty="No matches found"
          />
          <div style={paging}>
            <button disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)} style={btn}>
              ← Previous
            </button>
            <span style={{ fontSize: 13, color: '#64748b' }}>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
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
  padding: '6px 14px',
  borderRadius: 6,
  border: '1px solid #e2e8f0',
  background: '#fff',
  cursor: 'pointer',
  fontSize: 13,
}
