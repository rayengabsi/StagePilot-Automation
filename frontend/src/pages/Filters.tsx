import { useEffect, useState, useCallback } from 'react'
import PageHeader from '../components/PageHeader'
import Section from '../components/Section'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { api } from '../api/client'

interface FilterState {
  excluded_keywords: string[]
  required_keywords: string[]
  excluded_titles: string[]
  required_titles: string[]
  excluded_companies: string[]
  required_companies: string[]
  excluded_locations: string[]
  required_locations: string[]
  employment_type_exclude: string[]
  employment_type_include: string[]
  seniority_exclude: string[]
  seniority_include: string[]
  visa_required_keywords: string[]
  visa_excluded_keywords: string[]
  excluded_sources: string[]
  included_sources: string[]
  remote_only: boolean
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  unknown_data_policy: string
  max_job_age_days: number | null
}

const INITIAL: FilterState = {
  excluded_keywords: [], required_keywords: [],
  excluded_titles: [], required_titles: [],
  excluded_companies: [], required_companies: [],
  excluded_locations: [], required_locations: [],
  employment_type_exclude: [], employment_type_include: [],
  seniority_exclude: [], seniority_include: [],
  visa_required_keywords: [], visa_excluded_keywords: [],
  excluded_sources: [], included_sources: [],
  remote_only: false, salary_min: null, salary_max: null,
  salary_currency: null, unknown_data_policy: 'accept',
  max_job_age_days: null,
}

export default function Filters() {
  const [filters, setFilters] = useState<FilterState>(INITIAL)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [dirty, setDirty] = useState(false)

  const loadFilters = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const raw = await api.filters.get()
      setFilters({
        excluded_keywords: (raw.excluded_keywords as string[]) ?? [],
        required_keywords: (raw.required_keywords as string[]) ?? [],
        excluded_titles: (raw.excluded_titles as string[]) ?? [],
        required_titles: (raw.required_titles as string[]) ?? [],
        excluded_companies: (raw.excluded_companies as string[]) ?? [],
        required_companies: (raw.required_companies as string[]) ?? [],
        excluded_locations: (raw.excluded_locations as string[]) ?? [],
        required_locations: (raw.required_locations as string[]) ?? [],
        employment_type_exclude: (raw.employment_type_exclude as string[]) ?? [],
        employment_type_include: (raw.employment_type_include as string[]) ?? [],
        seniority_exclude: (raw.seniority_exclude as string[]) ?? [],
        seniority_include: (raw.seniority_include as string[]) ?? [],
        visa_required_keywords: (raw.visa_required_keywords as string[]) ?? [],
        visa_excluded_keywords: (raw.visa_excluded_keywords as string[]) ?? [],
        excluded_sources: (raw.excluded_sources as string[]) ?? [],
        included_sources: (raw.included_sources as string[]) ?? [],
        remote_only: (raw.remote_only as boolean) ?? false,
        salary_min: (raw.salary_min as number) ?? null,
        salary_max: (raw.salary_max as number) ?? null,
        salary_currency: (raw.salary_currency as string) ?? null,
        unknown_data_policy: (raw.unknown_data_policy as string) ?? 'accept',
        max_job_age_days: (raw.max_job_age_days as number) ?? null,
      })
    } catch {
      setError('Failed to load filters')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadFilters() }, [loadFilters])

  const updateArray = (key: keyof FilterState, value: string[]) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
    setSaved(false)
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      await api.filters.update(filters as unknown as Record<string, unknown>)
      setSaved(true)
      setDirty(false)
    } catch {
      setError('Failed to save filters')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState rows={4} />
  if (error) return <ErrorState message={error} onRetry={loadFilters} />

  return (
    <div>
      <PageHeader
        title="Filters"
        description="Configure job discovery preferences"
        actions={
          <button onClick={handleSave} disabled={saving || !dirty} style={styles.saveBtn}>
            {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save Filters'}
          </button>
        }
      />

      <Section title="Keywords">
        <div style={styles.twoCol}>
          <TagInput label="Required keywords" tags={filters.required_keywords} onChange={(v) => updateArray('required_keywords', v)} placeholder="e.g. python, react" />
          <TagInput label="Excluded keywords" tags={filters.excluded_keywords} onChange={(v) => updateArray('excluded_keywords', v)} placeholder="e.g. senior, lead" />
        </div>
      </Section>

      <Section title="Titles">
        <div style={styles.twoCol}>
          <TagInput label="Required titles" tags={filters.required_titles} onChange={(v) => updateArray('required_titles', v)} placeholder="e.g. intern, junior" />
          <TagInput label="Excluded titles" tags={filters.excluded_titles} onChange={(v) => updateArray('excluded_titles', v)} placeholder="e.g. director, VP" />
        </div>
      </Section>

      <Section title="Companies">
        <div style={styles.twoCol}>
          <TagInput label="Required companies" tags={filters.required_companies} onChange={(v) => updateArray('required_companies', v)} placeholder="e.g. Google, Meta" />
          <TagInput label="Excluded companies" tags={filters.excluded_companies} onChange={(v) => updateArray('excluded_companies', v)} placeholder="e.g. company name" />
        </div>
      </Section>

      <Section title="Locations">
        <div style={styles.twoCol}>
          <TagInput label="Required locations" tags={filters.required_locations} onChange={(v) => updateArray('required_locations', v)} placeholder="e.g. Remote, Berlin" />
          <TagInput label="Excluded locations" tags={filters.excluded_locations} onChange={(v) => updateArray('excluded_locations', v)} placeholder="e.g. New York" />
        </div>
      </Section>

      <Section title="Work Preferences">
        <div style={styles.twoCol}>
          <div style={styles.field}>
            <label style={styles.label}>Remote Only</label>
            <select
              style={styles.select}
              value={filters.remote_only ? 'true' : 'false'}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, remote_only: e.target.value === 'true' }))
                setDirty(true)
                setSaved(false)
              }}
            >
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Unknown Data Policy</label>
            <select
              style={styles.select}
              value={filters.unknown_data_policy}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, unknown_data_policy: e.target.value }))
                setDirty(true)
                setSaved(false)
              }}
            >
              <option value="accept">Accept</option>
              <option value="reject">Reject</option>
            </select>
          </div>
        </div>
        <div style={styles.twoCol}>
          <TagInput label="Include employment types" tags={filters.employment_type_include} onChange={(v) => updateArray('employment_type_include', v)} placeholder="e.g. internship, full-time" />
          <TagInput label="Exclude employment types" tags={filters.employment_type_exclude} onChange={(v) => updateArray('employment_type_exclude', v)} placeholder="e.g. contract" />
        </div>
        <div style={styles.twoCol}>
          <TagInput label="Include seniority" tags={filters.seniority_include} onChange={(v) => updateArray('seniority_include', v)} placeholder="e.g. intern, junior" />
          <TagInput label="Exclude seniority" tags={filters.seniority_exclude} onChange={(v) => updateArray('seniority_exclude', v)} placeholder="e.g. director, VP" />
        </div>
      </Section>

      <Section title="Salary">
        <div style={styles.threeCol}>
          <div style={styles.field}>
            <label style={styles.label}>Minimum</label>
            <input
              style={styles.input}
              type="number"
              value={filters.salary_min ?? ''}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, salary_min: e.target.value ? Number(e.target.value) : null }))
                setDirty(true)
                setSaved(false)
              }}
              placeholder="e.g. 50000"
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Maximum</label>
            <input
              style={styles.input}
              type="number"
              value={filters.salary_max ?? ''}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, salary_max: e.target.value ? Number(e.target.value) : null }))
                setDirty(true)
                setSaved(false)
              }}
              placeholder="e.g. 100000"
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Currency</label>
            <input
              style={styles.input}
              value={filters.salary_currency ?? ''}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, salary_currency: e.target.value || null }))
                setDirty(true)
                setSaved(false)
              }}
              placeholder="e.g. EUR"
            />
          </div>
        </div>
      </Section>

      <Section title="Sources & Freshness">
        <div style={styles.twoCol}>
          <TagInput label="Included sources" tags={filters.included_sources} onChange={(v) => updateArray('included_sources', v)} placeholder="e.g. linkedin" />
          <TagInput label="Excluded sources" tags={filters.excluded_sources} onChange={(v) => updateArray('excluded_sources', v)} placeholder="e.g. indeed" />
        </div>
        <div style={styles.twoCol}>
          <TagInput label="Visa required keywords" tags={filters.visa_required_keywords} onChange={(v) => updateArray('visa_required_keywords', v)} placeholder="e.g. visa sponsorship" />
          <TagInput label="Visa excluded keywords" tags={filters.visa_excluded_keywords} onChange={(v) => updateArray('visa_excluded_keywords', v)} placeholder="e.g. no visa" />
        </div>
        <div style={{ ...styles.field, maxWidth: 300 }}>
          <label style={styles.label}>Max Job Age (days)</label>
          <input
            style={styles.input}
            type="number"
            value={filters.max_job_age_days ?? ''}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, max_job_age_days: e.target.value ? Number(e.target.value) : null }))
              setDirty(true)
              setSaved(false)
            }}
            placeholder="e.g. 30"
          />
        </div>
      </Section>
    </div>
  )
}

function TagInput({ label, tags, onChange, placeholder }: {
  label: string; tags: string[]; onChange: (tags: string[]) => void; placeholder?: string
}) {
  const [input, setInput] = useState('')

  const addTag = () => {
    const val = input.trim()
    if (val && !tags.includes(val)) {
      onChange([...tags, val])
    }
    setInput('')
  }

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag))
  }

  return (
    <div style={styles.field}>
      <label style={styles.label}>{label}</label>
      <div style={styles.tagContainer}>
        {tags.map((tag) => (
          <span key={tag} style={styles.tag}>
            {tag}
            <button onClick={() => removeTag(tag)} style={styles.tagRemove} aria-label={`Remove ${tag}`}>
              ×
            </button>
          </span>
        ))}
        <input
          style={styles.tagInput}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag() }}}
          onBlur={addTag}
          placeholder={tags.length === 0 ? placeholder : ''}
        />
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  twoCol: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: 'var(--space-4)',
    marginBottom: 'var(--space-4)',
  },
  threeCol: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 'var(--space-4)',
  },
  field: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--space-2)',
  },
  label: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-600)',
  },
  input: {
    padding: 'var(--space-2) var(--space-3)',
    border: '1px solid var(--border-default)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--text-base)',
    background: 'var(--surface-card)',
    color: 'var(--gray-700)',
    outline: 'none',
    transition: 'border-color var(--transition-fast)',
  },
  select: {
    padding: 'var(--space-2) var(--space-3)',
    border: '1px solid var(--border-default)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--text-base)',
    background: 'var(--surface-card)',
    color: 'var(--gray-700)',
    outline: 'none',
    cursor: 'pointer',
  },
  tagContainer: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 'var(--space-1)',
    padding: 'var(--space-2)',
    border: '1px solid var(--border-default)',
    borderRadius: 'var(--radius-md)',
    background: 'var(--surface-card)',
    minHeight: 40,
    alignItems: 'center',
  },
  tag: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    borderRadius: 'var(--radius-sm)',
    background: 'var(--blue-50)',
    color: 'var(--blue-700)',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
    border: '1px solid var(--blue-100)',
  },
  tagRemove: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 16,
    height: 16,
    border: 'none',
    background: 'transparent',
    color: 'var(--blue-500)',
    cursor: 'pointer',
    fontSize: 14,
    lineHeight: 1,
    padding: 0,
    borderRadius: 'var(--radius-sm)',
  },
  tagInput: {
    flex: 1,
    minWidth: 100,
    border: 'none',
    outline: 'none',
    fontSize: 'var(--text-base)',
    background: 'transparent',
    color: 'var(--gray-700)',
    padding: '2px 4px',
  },
  saveBtn: {
    padding: 'var(--space-2) var(--space-5)',
    borderRadius: 'var(--radius-md)',
    border: 'none',
    background: 'var(--blue-600)',
    color: '#ffffff',
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  },
}
