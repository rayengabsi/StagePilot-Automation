import { motion } from 'framer-motion'

interface Props {
  title: string
  description?: string
  actions?: React.ReactNode
}

export default function PageHeader({ title, description, actions }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      style={styles.header}
    >
      <div>
        <h1 style={styles.title}>{title}</h1>
        {description && <p style={styles.description}>{description}</p>}
      </div>
      {actions && <div style={styles.actions}>{actions}</div>}
    </motion.div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 'var(--space-8)',
    gap: 'var(--space-4)',
  },
  title: {
    fontSize: 'var(--text-2xl)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-text-primary)',
    lineHeight: 'var(--leading-tight)',
    letterSpacing: 'var(--tracking-tight)',
  },
  description: {
    fontSize: 'var(--text-md)',
    color: 'var(--sp-text-secondary)',
    marginTop: 'var(--space-1-5)',
  },
  actions: {
    display: 'flex',
    gap: 'var(--space-2)',
    flexShrink: 0,
  },
}
