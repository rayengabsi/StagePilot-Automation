import { useEffect, useState, useCallback } from 'react'
import Table from '../components/Table'
import Pagination from '../components/Pagination'
import PageHeader from '../components/PageHeader'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import { api } from '../api/client'

interface Job {
  id: number
  title: string
  company: string | null
  location: string | null
  url: string
  employment_type: string | null
  seniority: string | null
  remote_status: string | null
  posted_at: string | null
  created_at: string | null
}

const PAGE_SIZE = 25

export default function Jobs() {
  const [items, setItems] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.jobs({ limit: PAGE_SIZE, offset })
      setItems(res.items as unknown as Job[])
      setTotal(res.total)
    } catch {
      setError('Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [offset])

  useEffect(() => { loadJobs() }, [loadJobs])

  return (
    <div>
      <PageHeader
        title="Jobs"
        description={`${total} jobs discovered from LinkedIn`}
      />

      {error && <ErrorState message={error} onRetry={loadJobs} />}

      {!error && loading && <LoadingState rows={5} />}

      {!error && !loading && items.length === 0 && (
        <EmptyState
          title="No jobs discovered yet"
          description="Run the LinkedIn discovery pipeline to start finding jobs."
        />
      )}

      {!error && !loading && items.length > 0 && (
        <>
          <Table
            columns={[
              { key: 'title', label: 'Title', render: (v, row) => (
                <a href={row.url as string} target="_blank" rel="noopener noreferrer" style={styles.link}>
                  {String(v)}
                </a>
              )},
              { key: 'company', label: 'Company' },
              { key: 'location', label: 'Location' },
              { key: 'employment_type', label: 'Type' },
              { key: 'seniority', label: 'Seniority' },
              { key: 'remote_status', label: 'Remote' },
              { key: 'posted_at', label: 'Posted', render: (v) => (
                v ? new Date(v as string).toLocaleDateString() : '—'
              )},
            ]}
            rows={items.map((j) => ({
              id: j.id,
              title: j.title,
              company: j.company,
              location: j.location,
              url: j.url,
              employment_type: j.employment_type,
              seniority: j.seniority,
              remote_status: j.remote_status,
              posted_at: j.posted_at,
            }))}
            empty="No jobs found"
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
}
