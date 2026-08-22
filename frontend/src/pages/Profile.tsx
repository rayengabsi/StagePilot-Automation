import { useEffect, useState } from 'react'
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
  certifications: unknown[]
  awards: unknown[]
  publications: unknown[]
  preferences: Record<string, unknown>
  completeness: { score: number; breakdown: Record<string, number>; missing_fields: string[] }
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short' })
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={sectionWrap}>
      <h2 style={sectionTitle}>{title}</h2>
      {children}
    </div>
  )
}

export default function Profile() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.profile()
      .then((p) => setProfile(p as unknown as Profile))
      .catch(() => setError('Failed to load profile'))
  }, [])

  if (error) return <div style={errorBox}>{error}</div>
  if (!profile) return <p style={{ color: '#64748b' }}>Loading…</p>

  const pi = profile.personal_info

  return (
    <div>
      <h1 style={title}>Profile</h1>

      <Section title="Personal Info">
        <div style={card}>
          {Object.entries(pi).map(([k, v]) => (
            <div key={k} style={row}>
              <span style={label}>{k.replace(/_/g, ' ')}</span>
              <span style={valueStyle}>{v == null || v === '' ? '—' : String(v)}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title={`Skills (${profile.skills.length})`}>
        <div style={tagWrap}>
          {profile.skills.map((s, i) => (
            <span key={i} style={tag}>{s.name}</span>
          ))}
          {profile.skills.length === 0 && <span style={{ color: '#94a3b8' }}>None</span>}
        </div>
      </Section>

      <Section title={`Experience (${profile.experience.length})`}>
        {profile.experience.map((e, i) => (
          <div key={i} style={card}>
            <div style={row}>
              <span style={label}>Title</span>
              <span style={valueStyle}>{e.title}</span>
            </div>
            <div style={row}>
              <span style={label}>Company</span>
              <span style={valueStyle}>{e.company}</span>
            </div>
            <div style={row}>
              <span style={label}>Period</span>
              <span style={valueStyle}>
                {formatDate(e.start_date)} — {e.is_current ? 'Present' : formatDate(e.end_date)}
              </span>
            </div>
            {e.description && (
              <div style={row}>
                <span style={label}>Description</span>
                <span style={valueStyle}>{e.description}</span>
              </div>
            )}
          </div>
        ))}
        {profile.experience.length === 0 && <p style={{ color: '#94a3b8' }}>None</p>}
      </Section>

      <Section title={`Education (${profile.education.length})`}>
        {profile.education.map((e, i) => (
          <div key={i} style={card}>
            <div style={row}>
              <span style={label}>Institution</span>
              <span style={valueStyle}>{e.institution}</span>
            </div>
            <div style={row}>
              <span style={label}>Degree</span>
              <span style={valueStyle}>{e.degree}{e.field_of_study ? ` — ${e.field_of_study}` : ''}</span>
            </div>
            <div style={row}>
              <span style={label}>Period</span>
              <span style={valueStyle}>{formatDate(e.start_date)} — {formatDate(e.end_date)}</span>
            </div>
          </div>
        ))}
        {profile.education.length === 0 && <p style={{ color: '#94a3b8' }}>None</p>}
      </Section>

      <Section title={`Projects (${profile.projects.length})`}>
        {profile.projects.map((p, i) => (
          <div key={i} style={card}>
            <div style={row}>
              <span style={label}>Name</span>
              <span style={valueStyle}>{p.name}</span>
            </div>
            <div style={row}>
              <span style={label}>Description</span>
              <span style={valueStyle}>{p.description}</span>
            </div>
            {p.technologies.length > 0 && (
              <div style={row}>
                <span style={label}>Technologies</span>
                <span style={valueStyle}>{p.technologies.join(', ')}</span>
              </div>
            )}
          </div>
        ))}
        {profile.projects.length === 0 && <p style={{ color: '#94a3b8' }}>None</p>}
      </Section>

      <Section title={`Languages (${profile.languages.length})`}>
        <div style={card}>
          {profile.languages.map((l, i) => (
            <div key={i} style={row}>
              <span style={label}>{l.name}</span>
              <span style={valueStyle}>{l.proficiency ?? '—'}</span>
            </div>
          ))}
          {profile.languages.length === 0 && <span style={{ color: '#94a3b8' }}>None</span>}
        </div>
      </Section>

      <Section title="Completeness">
        <div style={card}>
          <div style={row}>
            <span style={label}>Score</span>
            <span style={valueStyle}>{profile.completeness.score}%</span>
          </div>
          {Object.entries(profile.completeness.breakdown).map(([k, v]) => (
            <div key={k} style={row}>
              <span style={label}>{k.replace(/_/g, ' ')}</span>
              <span style={valueStyle}>{v}%</span>
            </div>
          ))}
          {profile.completeness.missing_fields.length > 0 && (
            <div style={row}>
              <span style={label}>Missing</span>
              <span style={valueStyle}>{profile.completeness.missing_fields.join(', ')}</span>
            </div>
          )}
        </div>
      </Section>
    </div>
  )
}

const title = { fontSize: 24, fontWeight: 700, color: '#0f172a', marginBottom: 24 }
const sectionWrap = { marginBottom: 28 }
const sectionTitle = { fontSize: 16, fontWeight: 600, color: '#334155', marginBottom: 8 }
const card = { background: '#fff', borderRadius: 10, border: '1px solid #e2e8f0', padding: 20, marginBottom: 8 }
const row = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
  padding: '8px 0', borderBottom: '1px solid #f1f5f9', gap: 16,
}
const label = { fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase' as const, minWidth: 120, flexShrink: 0 }
const valueStyle = { fontSize: 14, color: '#0f172a', overflowWrap: 'break-word' as const }
const tagWrap = { display: 'flex', flexWrap: 'wrap' as const, gap: 6 }
const tag = {
  display: 'inline-block', padding: '4px 10px', borderRadius: 6,
  background: '#f1f5f9', fontSize: 13, color: '#334155',
}
const errorBox = { padding: 20, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#dc2626' }
