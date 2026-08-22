import { useEffect, useState } from 'react'
import StatCard from '../components/StatCard'
import { api } from '../api/client'

export default function Dashboard() {
  const [health, setHealth] = useState<string | null>(null)
  const [jobs, setJobs] = useState<{ total: number } | null>(null)
  const [matches, setMatches] = useState<{ total: number } | null>(null)
  const [scheduler, setScheduler] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    api.health().then((h) => setHealth(h.status)).catch(() => setHealth('error'))
    api.jobs({ limit: 1 }).then((j) => setJobs(j)).catch(() => {})
    api.matches({ limit: 1 }).then((m) => setMatches(m)).catch(() => {})
    api.scheduler.status().then((s) => setScheduler(s)).catch(() => {})
  }, [])

  return (
    <div>
      <h1 style={title}>Dashboard</h1>
      <div style={grid}>
        <StatCard label="API Health" value={health ?? '…'} hint="Backend status" />
        <StatCard label="Jobs" value={jobs?.total ?? '…'} hint="Total in database" />
        <StatCard label="Matches" value={matches?.total ?? '…'} hint="Total recommendations" />
        <StatCard
          label="Scheduler"
          value={scheduler?.running ? 'Running' : 'Stopped'}
          hint={`Interval: ${scheduler?.interval_minutes ?? '—'} min`}
        />
      </div>
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }
