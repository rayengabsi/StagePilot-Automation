import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { ExternalLink, Building2, Check, X } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import Pagination from '../components/Pagination'
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
  matched_technologies: string[]
  missing_technologies: string[]
  explanation: string
  ranking_position: number | null
  created_at: string | null
}

const PAGE_SIZE = 25

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
}

const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } },
}

function getScoreColor(score: number) {
  if (score >= 80) return 'var(--sp-green)'
  if (score >= 60) return 'var(--sp-accent)'
  if (score >= 40) return 'var(--sp-amber)'
  return 'var(--sp-text-muted)'
}

function getScoreLabel(score: number) {
  if (score >= 80) return 'Excellent'
  if (score >= 60) return 'Strong'
  if (score >= 40) return 'Moderate'
  return 'Low'
}

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
          description="StagePilot hasn't found a strong recommendation yet. Matches appear after the discovery pipeline finds jobs that match your profile."
        />
      )}

      {!error && !loading && items.length > 0 && (
        <motion.div variants={stagger} initial="hidden" animate="show">
          {items.map((match) => (
            <motion.div key={match.id} variants={fadeUp}>
              <div style={styles.card}>
                <div style={styles.scoreCol}>
                  <div style={{
                    ...styles.scoreRing,
                    borderColor: getScoreColor(match.final_score),
                  }}>
                    <span style={{ ...styles.scoreValue, color: getScoreColor(match.final_score) }}>
                      {Math.round(match.final_score)}
                    </span>
                  </div>
                  <span style={{ ...styles.scoreLabel, color: getScoreColor(match.final_score) }}>
                    {getScoreLabel(match.final_score)}
                  </span>
                  {match.ranking_position != null && match.ranking_position > 0 && (
                    <span style={styles.rank}>#{match.ranking_position}</span>
                  )}
                </div>

                <div style={styles.cardMain}>
                  <div style={styles.cardHeader}>
                    <div>
                      <h3 style={styles.title}>
                        {match.job_url ? (
                          <a href={match.job_url} target="_blank" rel="noopener noreferrer" style={styles.titleLink}>
                            {match.job_title}
                            <ExternalLink size={13} style={{ marginLeft: 6, opacity: 0.5 }} />
                          </a>
                        ) : match.job_title}
                      </h3>
                      {match.job_company && (
                        <div style={styles.company}>
                          <Building2 size={13} />
                          {match.job_company}
                        </div>
                      )}
                    </div>
                  </div>

                  {match.explanation && (
                    <p style={styles.explanation}>{match.explanation}</p>
                  )}

                  {match.matched_skills.length > 0 && (
                    <div style={styles.skillSection}>
                      <span style={styles.skillLabel}>Matching skills</span>
                      <div style={styles.skillList}>
                        {match.matched_skills.map((s) => (
                          <span key={s} style={styles.skillMatch}>
                            <Check size={10} />
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {match.missing_skills.length > 0 && (
                    <div style={styles.skillSection}>
                      <span style={styles.skillLabel}>Missing skills</span>
                      <div style={styles.skillList}>
                        {match.missing_skills.map((s) => (
                          <span key={s} style={styles.skillMissing}>
                            <X size={10} />
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
          <Pagination
            offset={offset}
            total={total}
            pageSize={PAGE_SIZE}
            onPageChange={setOffset}
          />
        </motion.div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    display: 'flex',
    gap: 'var(--space-5)',
    padding: 'var(--space-5)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-border)',
    marginBottom: 'var(--space-3)',
    transition: 'border-color var(--transition-fast)',
  },
  scoreCol: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 'var(--space-1)',
    flexShrink: 0,
    minWidth: 64,
  },
  scoreRing: {
    width: 56,
    height: 56,
    borderRadius: '50%',
    border: '2px solid',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreValue: {
    fontSize: 'var(--text-lg)',
    fontWeight: 'var(--weight-bold)',
    fontVariantNumeric: 'tabular-nums',
  },
  scoreLabel: {
    fontSize: 'var(--text-2xs)',
    fontWeight: 'var(--weight-medium)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-wide)',
  },
  rank: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
    fontVariantNumeric: 'tabular-nums',
  },
  cardMain: { flex: 1, minWidth: 0 },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 'var(--space-4)',
    marginBottom: 'var(--space-3)',
  },
  title: {
    fontSize: 'var(--text-lg)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    lineHeight: 'var(--leading-tight)',
  },
  titleLink: {
    color: 'var(--sp-text-primary)',
    textDecoration: 'none',
    display: 'inline-flex',
    alignItems: 'center',
  },
  company: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-1-5)',
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    marginTop: 'var(--space-1)',
  },
  explanation: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    lineHeight: 'var(--leading-relaxed)',
    marginBottom: 'var(--space-3)',
  },
  skillSection: {
    marginBottom: 'var(--space-2)',
  },
  skillLabel: {
    fontSize: 'var(--text-2xs)',
    fontWeight: 'var(--weight-medium)',
    color: 'var(--sp-text-muted)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-wide)',
    display: 'block',
    marginBottom: 'var(--space-1-5)',
  },
  skillList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 'var(--space-1)',
  },
  skillMatch: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 3,
    padding: '2px 8px',
    borderRadius: 'var(--radius-full)',
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-medium)',
    background: 'var(--sp-green-dim)',
    color: 'var(--sp-green)',
    border: '1px solid var(--sp-green-border)',
  },
  skillMissing: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 3,
    padding: '2px 8px',
    borderRadius: 'var(--radius-full)',
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-medium)',
    background: 'rgba(255, 255, 255, 0.03)',
    color: 'var(--sp-text-muted)',
    border: '1px solid var(--sp-border)',
  },
}
