import { motion } from 'framer-motion'

interface StatCardProps {
  label: string
  value: string | number
  hint?: string
  icon?: React.ReactNode
}

export default function StatCard({ label, value, hint, icon }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      style={styles.card}
      whileHover={{ borderColor: 'rgba(255, 255, 255, 0.10)' }}
    >
      <div style={styles.header}>
        <span style={styles.label}>{label}</span>
        {icon && <span style={styles.icon}>{icon}</span>}
      </div>
      <div style={styles.value}>{value}</div>
      {hint && <div style={styles.hint}>{hint}</div>}
    </motion.div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-lg)',
    padding: 'var(--space-5)',
    border: '1px solid var(--sp-border)',
    transition: 'border-color var(--transition-fast)',
    minWidth: 0,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 'var(--space-3)',
  },
  label: {
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-medium)',
    color: 'var(--sp-text-muted)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-wide)',
  },
  icon: {
    color: 'var(--sp-text-muted)',
    display: 'flex',
    alignItems: 'center',
  },
  value: {
    fontSize: 'var(--text-2xl)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-text-primary)',
    lineHeight: 'var(--leading-tight)',
    letterSpacing: 'var(--tracking-tight)',
    fontVariantNumeric: 'tabular-nums',
  },
  hint: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
    marginTop: 'var(--space-1)',
  },
}
