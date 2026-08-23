import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { MapPin, Mail, Phone, Globe, Link, GitBranch, GraduationCap, Briefcase, Code2 } from 'lucide-react'
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
  if (!d) return '\u2014'
  return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short' })
}

const fadeUp = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as const } },
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
}

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
            <div style={{
              ...styles.scoreRing,
              background: `conic-gradient(var(--sp-accent) ${completeness.score * 3.6}deg, var(--sp-border) ${completeness.score * 3.6}deg)`,
            }}>
              <div style={styles.scoreInner}>
                <span style={styles.scoreValue}>{completeness.score}%</span>
              </div>
            </div>
          </div>
        }
      />

      <motion.div initial="hidden" animate="show" variants={stagger}>
        {/* Personal Info */}
        <motion.div variants={fadeUp}>
          <Section title="Personal Information">
            <div style={styles.card}>
              <div style={styles.infoGrid}>
                {pi.email && <InfoRow icon={<Mail size={14} />} label="Email" value={pi.email} />}
                {pi.phone && <InfoRow icon={<Phone size={14} />} label="Phone" value={pi.phone} />}
                {pi.location && <InfoRow icon={<MapPin size={14} />} label="Location" value={pi.location} />}
                {pi.nationality && <InfoRow icon={<Globe size={14} />} label="Nationality" value={pi.nationality} />}
                {pi.linkedin_url && <InfoRow icon={<Link size={14} />} label="LinkedIn" value={pi.linkedin_url} href={pi.linkedin_url} />}
                {pi.github_url && <InfoRow icon={<GitBranch size={14} />} label="GitHub" value={pi.github_url} href={pi.github_url} />}
                {pi.portfolio_url && <InfoRow icon={<Globe size={14} />} label="Portfolio" value={pi.portfolio_url} href={pi.portfolio_url} />}
              </div>
              {pi.summary && (
                <div style={styles.summarySection}>
                  <p style={styles.summaryText}>{pi.summary}</p>
                </div>
              )}
            </div>
          </Section>
        </motion.div>

        {/* Skills */}
        <motion.div variants={fadeUp}>
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
        </motion.div>

        {/* Experience */}
        <motion.div variants={fadeUp}>
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
                        <p style={styles.cardSubtitle}>
                          <Briefcase size={12} style={{ marginRight: 4, opacity: 0.5 }} />
                          {exp.company}
                        </p>
                      </div>
                      <span style={styles.period}>
                        {formatDate(exp.start_date)} \u2014 {exp.is_current ? 'Present' : formatDate(exp.end_date)}
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
        </motion.div>

        {/* Education */}
        <motion.div variants={fadeUp}>
          <Section title={`Education (${profile.education.length})`}>
            {profile.education.length === 0 ? (
              <EmptyState title="No education listed" />
            ) : (
              <div style={styles.cardStack}>
                {profile.education.map((edu, i) => (
                  <div key={i} style={styles.card}>
                    <div style={styles.cardHeader}>
                      <div>
                        <h3 style={styles.cardTitle}>
                          <GraduationCap size={14} style={{ marginRight: 6, opacity: 0.5 }} />
                          {edu.institution}
                        </h3>
                        <p style={styles.cardSubtitle}>
                          {edu.degree}{edu.field_of_study ? ` \u2014 ${edu.field_of_study}` : ''}
                        </p>
                      </div>
                      <span style={styles.period}>
                        {formatDate(edu.start_date)} \u2014 {formatDate(edu.end_date)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </motion.div>

        {/* Projects */}
        <motion.div variants={fadeUp}>
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
                          <Code2 size={14} style={{ marginRight: 6, opacity: 0.5 }} />
                          {proj.url ? (
                            <a href={proj.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>{proj.name}</a>
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
        </motion.div>

        {/* Languages */}
        <motion.div variants={fadeUp}>
          <Section title={`Languages (${profile.languages.length})`}>
            {profile.languages.length === 0 ? (
              <EmptyState title="No languages listed" />
            ) : (
              <div style={styles.card}>
                {profile.languages.map((lang, i) => (
                  <div key={i} style={styles.row}>
                    <span style={styles.rowLabel}>{lang.name}</span>
                    <StatusBadge label={lang.proficiency || '\u2014'} variant="neutral" dot={false} />
                  </div>
                ))}
              </div>
            )}
          </Section>
        </motion.div>

        {/* Completeness */}
        <motion.div variants={fadeUp}>
          <Section title="Profile completeness">
            <div style={styles.card}>
              <div style={styles.completenessBar}>
                <motion.div
                  style={styles.completenessFill}
                  initial={{ width: 0 }}
                  animate={{ width: `${completeness.score}%` }}
                  transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] as const }}
                />
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
        </motion.div>
      </motion.div>
    </div>
  )
}

function InfoRow({ icon, label, value, href }: { icon: React.ReactNode; label: string; value: string; href?: string }) {
  return (
    <div style={styles.infoRow}>
      <span style={styles.infoIcon}>{icon}</span>
      <div>
        <span style={styles.infoLabel}>{label}</span>
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" style={styles.infoValue}>{value}</a>
        ) : (
          <span style={styles.infoValue}>{value}</span>
        )}
      </div>
    </div>
  )
}

function formatFieldName(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const styles: Record<string, React.CSSProperties> = {
  scoreContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 'var(--space-1)',
  },
  scoreRing: {
    width: 56,
    height: 56,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 3,
  },
  scoreInner: {
    width: '100%',
    height: '100%',
    borderRadius: '50%',
    background: 'var(--sp-surface-card)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreValue: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-accent)',
    fontVariantNumeric: 'tabular-nums',
  },
  card: {
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-border)',
    padding: 'var(--space-5)',
  },
  cardStack: {
    display: 'flex',
    flexDirection: 'column',
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
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    display: 'flex',
    alignItems: 'center',
  },
  cardSubtitle: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    marginTop: 'var(--space-1)',
    display: 'flex',
    alignItems: 'center',
  },
  cardDescription: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    lineHeight: 'var(--leading-relaxed)',
    marginTop: 'var(--space-2)',
  },
  period: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
    whiteSpace: 'nowrap',
    flexShrink: 0,
    fontVariantNumeric: 'tabular-nums',
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 'var(--space-2-5) 0',
    borderBottom: '1px solid var(--sp-border)',
    gap: 'var(--space-4)',
  },
  rowLabel: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
    color: 'var(--sp-text-primary)',
  },
  tagWrap: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 'var(--space-1-5)',
  },
  tag: {
    display: 'inline-block',
    padding: 'var(--space-1) var(--space-3)',
    borderRadius: 'var(--radius-full)',
    background: 'rgba(255, 255, 255, 0.04)',
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    border: '1px solid var(--sp-border)',
  },
  techList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 'var(--space-1)',
    marginTop: 'var(--space-3)',
  },
  techTag: {
    display: 'inline-block',
    padding: '1px 8px',
    borderRadius: 'var(--radius-full)',
    background: 'var(--sp-accent-dim)',
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-accent)',
    border: '1px solid var(--sp-accent-border)',
  },
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: 'var(--space-3)',
  },
  infoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
  },
  infoIcon: {
    color: 'var(--sp-text-muted)',
    flexShrink: 0,
  },
  infoLabel: {
    display: 'block',
    fontSize: 'var(--text-2xs)',
    color: 'var(--sp-text-muted)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-wide)',
    fontWeight: 'var(--weight-medium)',
  },
  infoValue: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-primary)',
    wordBreak: 'break-all',
  },
  summarySection: {
    marginTop: 'var(--space-4)',
    paddingTop: 'var(--space-4)',
    borderTop: '1px solid var(--sp-border)',
  },
  summaryText: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    lineHeight: 'var(--leading-relaxed)',
  },
  completenessBar: {
    height: 4,
    background: 'var(--sp-surface-raised)',
    borderRadius: 2,
    overflow: 'hidden',
    marginBottom: 'var(--space-4)',
  },
  completenessFill: {
    height: '100%',
    background: 'var(--sp-accent)',
    borderRadius: 2,
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
    background: 'var(--sp-surface-raised)',
    borderRadius: 'var(--radius-md)',
  },
  completenessLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-secondary)',
  },
  completenessValue: {
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    fontVariantNumeric: 'tabular-nums',
  },
  missingFields: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    marginTop: 'var(--space-4)',
    flexWrap: 'wrap',
  },
  missingLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
    fontWeight: 'var(--weight-medium)',
  },
}
