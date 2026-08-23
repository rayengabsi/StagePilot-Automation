interface StatCardProps {
  label: string
  value: string | number
  hint?: string
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
}

export default function StatCard({ label, value, hint, icon }: StatCardProps) {
  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <span style={styles.label}>{label}</span>
        {icon && <span style={styles.icon}>{icon}</span>}
      </div>
      <div style={styles.value}>{value}</div>
      {hint && <div style={styles.hint}>{hint}</div>}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    padding: 'var(--space-5)',
    border: '1px solid var(--border-default)',
    boxShadow: 'var(--shadow-xs)',
    transition: 'box-shadow var(--transition-fast)',
    minWidth: 0,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 'var(--space-2)',
  },
  label: {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
    color: 'var(--gray-500)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  icon: {
    color: 'var(--gray-400)',
    display: 'flex',
    alignItems: 'center',
  },
  value: {
    fontSize: 'var(--text-xl)',
    fontWeight: 'var(--weight-bold)' as unknown as number,
    color: 'var(--gray-900)',
    lineHeight: 1.2,
  },
  hint: {
    fontSize: 'var(--text-xs)',
    color: 'var(--gray-400)',
    marginTop: 'var(--space-1)',
  },
}
