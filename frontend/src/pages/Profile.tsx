import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Section from '../components/Section'
import StatusBadge from '../components/StatusBadge'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import { api } from '../api/client'

interface Skill { name: string; category: string | null; proficiency: string | null }
interface Experience {
  company: string; title: string; location: string | null;
  start_date: string | null; end_date: string | null; is_current: boolean;
  description: string | null; technologies: string[];
}
interface Education {
  institution: string; degree: string; field_of_study: string | null;
  start_date: string | null; end_date: string | null; gpa: string | null;
  description: string | null;
}
interface Project {
  name: string; description: string; url: string | null;
  technologies: string[]; start_date: string | null; end_date: string | null;
}
interface Lang { name: string; proficiency: string | null }

interface Profile {
  personal_info: Record<string, string | null>
  skills: Skill[]
  experience: Experience[]
  education: Education[]
  projects: Project[]
  languages: Lang[]
  completeness: { score: number; breakdown: Record<string, number>; missing_fields: string[] }
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short' })
}

const PERSONAL_FIELDS = ['full_name', 'email', 'phone', 'location', 'nationality', 'linkedin_url', 'github_url', 'portfolio_url', 'summary']

export default function Profile() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.profile()
      .then((p) => setProfile(p as unknown as Profile))
      .catch(() => setError('Failed to load profile'))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!profile) return <LoadingState rows={4} />

  const pi = profile.personal_info
  const completeness = profile.completeness

  return (
    <div>
      <PageHeader
        title={pi.full_name || 'Profile'}
        description={pi.summary || 'Your candidate profile'}
        actions={
          <div style={styles.scoreContainer}>
            <div style={styles.scoreCircle}>
              <span style={styles.scoreValue}>{completeness.score}%</span>
            </div>
            <span style={styles.scoreLabel}>Complete</span>
          </div>
        }
      />

      {/* Personal Info */}
      <Section title="Personal Information">
        <div style={styles.card}>
          {PERSONAL_FIELDS.map((key) => {
            const val = pi[key]
            if (key === 'summary') return null
            if (!val) return null
            return (
              <div key={key} style={styles.row}>
                <span style={styles.label}>{formatFieldName(key)}</span>
                <span style={styles.value}>
                  {key.includes('_url') ? (
                    <a href={val} target="_blank" rel="noopener noreferrer" style={styles.link}>{val}</a>
                  ) : val}
                </span>
              </div>
            )
          })}
          {pi.summary && (
            <div style={styles.summaryRow}>
              <span style={styles.label}>Summary</span>
              <p style={styles.summaryText}>{pi.summary}</p>
            </div>
          )}
        </div>
      </Section>

      {/* Skills */}
      <Section title={`Skills (${profile.skills.length})`}>
        {profile.skills.length === 0 ? (
          <EmptyState title="No skills listed" />
        ) : (
          <div style={styles.tagWrap}>
            {profile.skills.map((s, i) => (
              <span key={i} style={styles.tag}>{s.name}</span>
            ))}
          </div>
        )}
      </Section>

      {/* Experience */}
      <Section title={`Experience (${profile.experience.length})`}>
        {profile.experience.length === 0 ? (
          <EmptyState title="No experience listed" />
        ) : (
          <div style={styles.cardStack}>
            {profile.experience.map((exp, i) => (
              <div key={i} style={styles.card}>
                <div style={styles.cardHeader}>
                  <div>
                    <h3 style={styles.cardTitle}>{exp.title}</h3>
                    <p style={styles.cardSubtitle}>{exp.company}</p>
                  </div>
                  <span style={styles.period}>
                    {formatDate(exp.start_date)} — {exp.is_current ? 'Present' : formatDate(exp.end_date)}
                  </span>
                </div>
                {exp.description && <p style={styles.cardDescription}>{exp.description}</p>}
                {exp.technologies.length > 0 && (
                  <div style={styles.techList}>
                    {exp.technologies.map((t, j) => (
                      <span key={j} style={styles.techTag}>{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Education */}
      <Section title={`Education (${profile.education.length})`}>
        {profile.education.length === 0 ? (
          <EmptyState title="No education listed" />
        ) : (
          <div style={styles.cardStack}>
            {profile.education.map((edu, i) => (
              <div key={i} style={styles.card}>
                <div style={styles.cardHeader}>
                  <div>
                    <h3 style={styles.cardTitle}>{edu.institution}</h3>
                    <p style={styles.cardSubtitle}>
                      {edu.degree}{edu.field_of_study ? ` — ${edu.field_of_study}` : ''}
                    </p>
                  </div>
                  <span style={styles.period}>
                    {formatDate(edu.start_date)} — {formatDate(edu.end_date)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Projects */}
      <Section title={`Projects (${profile.projects.length})`}>
        {profile.projects.length === 0 ? (
          <EmptyState title="No projects listed" />
        ) : (
          <div style={styles.cardStack}>
            {profile.projects.map((proj, i) => (
              <div key={i} style={styles.card}>
                <div style={styles.cardHeader}>
                  <div>
                    <h3 style={styles.cardTitle}>
                      {proj.url ? (
                        <a href={proj.url} target="_blank" rel="noopener noreferrer" style={styles.link}>{proj.name}</a>
                      ) : proj.name}
                    </h3>
                  </div>
                </div>
                <p style={styles.cardDescription}>{proj.description}</p>
                {proj.technologies.length > 0 && (
                  <div style={styles.techList}>
                    {proj.technologies.map((t, j) => (
                      <span key={j} style={styles.techTag}>{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Languages */}
      <Section title={`Languages (${profile.languages.length})`}>
        {profile.languages.length === 0 ? (
          <EmptyState title="No languages listed" />
        ) : (
          <div style={styles.card}>
            {profile.languages.map((lang, i) => (
              <div key={i} style={styles.row}>
                <span style={styles.label}>{lang.name}</span>
                <StatusBadge label={lang.proficiency || '—'} variant="neutral" dot={false} />
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Completeness */}
      <Section title="Completeness">
        <div style={styles.card}>
          <div style={styles.completenessBar}>
            <div style={{ ...styles.completenessFill, width: `${completeness.score}%` }} />
          </div>
          <div style={styles.completenessGrid}>
            {Object.entries(completeness.breakdown).map(([key, val]) => (
              <div key={key} style={styles.completenessItem}>
                <span style={styles.completenessLabel}>{formatFieldName(key)}</span>
                <span style={styles.completenessValue}>{val}%</span>
              </div>
            ))}
          </div>
          {completeness.missing_fields.length > 0 && (
            <div style={styles.missingFields}>
              <span style={styles.missingLabel}>Missing:</span>
              {completeness.missing_fields.map((f) => (
                <StatusBadge key={f} label={f} variant="warning" dot={false} />
              ))}
            </div>
          )}
        </div>
      </Section>
    </div>
  )
}

function formatFieldName(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const styles: Record<string, React.CSSProperties> = {
  scoreContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 'var(--space-1)',
  },
  scoreCircle: {
    width: 64,
    height: 64,
    borderRadius: '50%',
    border: '3px solid var(--blue-600)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreValue: {
    fontSize: 'var(--text-lg)',
    fontWeight: 'var(--weight-bold)' as unknown as number,
    color: 'var(--blue-600)',
  },
  scoreLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--gray-500)',
  },
  card: {
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
    padding: 'var(--space-5)',
  },
  cardStack: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--space-3)',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 'var(--space-4)',
    marginBottom: 'var(--space-2)',
  },
  cardTitle: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-900)',
  },
  cardSubtitle: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-500)',
    marginTop: 2,
  },
  cardDescription: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-600)',
    lineHeight: 1.6,
    marginTop: 'var(--space-2)',
  },
  period: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-400)',
    whiteSpace: 'nowrap' as const,
    flexShrink: 0,
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 'var(--space-2) 0',
    borderBottom: '1px solid var(--border-subtle)',
    gap: 'var(--space-4)',
  },
  label: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-500)',
    minWidth: 100,
    flexShrink: 0,
  },
  value: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-900)',
    overflowWrap: 'break-word' as const,
  },
  summaryRow: {
    paddingTop: 'var(--space-3)',
  },
  summaryText: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-700)',
    lineHeight: 1.6,
    marginTop: 'var(--space-2)',
  },
  link: {
    color: 'var(--blue-600)',
    textDecoration: 'none',
  },
  tagWrap: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 'var(--space-2)',
  },
  tag: {
    display: 'inline-block',
    padding: 'var(--space-1) var(--space-3)',
    borderRadius: 'var(--radius-md)',
    background: 'var(--gray-100)',
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-700)',
    border: '1px solid var(--gray-200)',
  },
  techList: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 'var(--space-1)',
    marginTop: 'var(--space-3)',
  },
  techTag: {
    display: 'inline-block',
    padding: '1px 8px',
    borderRadius: 'var(--radius-sm)',
    background: 'var(--blue-50)',
    fontSize: 'var(--text-xs)',
    color: 'var(--blue-700)',
    border: '1px solid var(--blue-100)',
  },
  completenessBar: {
    height: 8,
    background: 'var(--gray-100)',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 'var(--space-4)',
  },
  completenessFill: {
    height: '100%',
    background: 'var(--blue-600)',
    borderRadius: 4,
    transition: 'width 0.5s ease',
  },
  completenessGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
    gap: 'var(--space-3)',
  },
  completenessItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--gray-50)',
    borderRadius: 'var(--radius-md)',
  },
  completenessLabel: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-600)',
  },
  completenessValue: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-900)',
    fontVariantNumeric: 'tabular-nums',
  },
  missingFields: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    marginTop: 'var(--space-4)',
    flexWrap: 'wrap' as const,
  },
  missingLabel: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
  },
}
