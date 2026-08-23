import { useEffect, useState, useCallback } from 'react'
import Table from '../components/Table'
import Pagination from '../components/Pagination'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import { api } from '../api/client'

interface Match {
  id: number
  job_id: number
  job_title: string
  job_company: string | null
  job_url: string | null
  final_score: number
  status: string
  hard_rule_passed: boolean
  matched_skills: string[]
  missing_skills: string[]
  ranking_position: number | null
  created_at: string | null
}

const PAGE_SIZE = 25

export default function Matches() {
  const [items, setItems] = useState<Match[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadMatches = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.matches({ limit: PAGE_SIZE, offset })
      setItems(res.items as unknown as Match[])
      setTotal(res.total)
    } catch {
      setError('Failed to load matches')
    } finally {
      setLoading(false)
    }
  }, [offset])

  useEffect(() => { loadMatches() }, [loadMatches])

  return (
    <div>
      <PageHeader
        title="Matches"
        description={`${total} job recommendations matched to your profile`}
      />

      {error && <ErrorState message={error} onRetry={loadMatches} />}

      {!error && loading && <LoadingState rows={5} />}

      {!error && !loading && items.length === 0 && (
        <EmptyState
          title="No matches yet"
          description="Matches appear after the discovery pipeline runs and finds jobs that match your profile."
        />
      )}

      {!error && !loading && items.length > 0 && (
        <>
          <Table
            columns={[
              { key: 'job_title', label: 'Job', width: '30%', render: (v, row) => (
                <div>
                  <a href={row.job_url as string} target="_blank" rel="noopener noreferrer" style={styles.link}>
                    {String(v)}
                  </a>
                  {row.job_company != null && <div style={styles.company}>{String(row.job_company)}</div>}
                </div>
              )},
              { key: 'final_score', label: 'Score', align: 'center', render: (v) => {
                const score = v as number
                const variant = score >= 70 ? 'success' : score >= 50 ? 'warning' : 'neutral'
                return <StatusBadge label={score.toFixed(1)} variant={variant} dot={false} />
              }},
              { key: 'matched_skills', label: 'Matching Skills', render: (v) => {
                const skills = (v as string[] || []).slice(0, 5)
                if (skills.length === 0) return <span style={styles.muted}>—</span>
                return (
                  <div style={styles.skillList}>
                    {skills.map((s) => <span key={s} style={styles.skill}>{s}</span>)}
                    {(v as string[]).length > 5 && <span style={styles.more}>+{(v as string[]).length - 5}</span>}
                  </div>
                )
              }},
              { key: 'status', label: 'Status', render: (v, row) => (
                <StatusBadge
                  label={String(v)}
                  variant={row.hard_rule_passed ? 'success' : 'error'}
                />
              )},
              { key: 'ranking_position', label: 'Rank', align: 'center', render: (v) => (
                v != null ? <span style={styles.rank}>#{String(v)}</span> : <span style={styles.muted}>—</span>
              )},
            ]}
            rows={items.map((m) => ({
              id: m.id,
              job_title: m.job_title,
              job_company: m.job_company,
              job_url: m.job_url,
              final_score: m.final_score,
              status: m.status,
              hard_rule_passed: m.hard_rule_passed,
              matched_skills: m.matched_skills,
              ranking_position: m.ranking_position,
            }))}
            empty="No matches found"
          />
          <Pagination
            offset={offset}
            total={total}
            pageSize={PAGE_SIZE}
            onPageChange={setOffset}
          />
        </>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  link: {
    color: 'var(--blue-600)',
    textDecoration: 'none',
    fontWeight: 'var(--weight-medium)' as unknown as number,
  },
  company: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    marginTop: 2,
  },
  skillList: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 4,
  },
  skill: {
    display: 'inline-block',
    padding: '1px 8px',
    borderRadius: 999,
    fontSize: 'var(--text-xs)',
    background: 'var(--gray-100)',
    color: 'var(--gray-600)',
    border: '1px solid var(--gray-200)',
    whiteSpace: 'nowrap' as const,
  },
  more: {
    fontSize: 'var(--text-xs)',
    color: 'var(--gray-400)',
    alignSelf: 'center',
  },
  muted: {
    color: 'var(--gray-400)',
  },
  rank: {
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-700)',
    fontVariantNumeric: 'tabular-nums',
  },
}
