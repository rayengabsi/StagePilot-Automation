import { motion } from 'framer-motion'

interface Props {
  title?: string
  description?: string
  actions?: React.ReactNode
  children: React.ReactNode
}

export default function Section({ title, description, actions, children }: Props) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      style={styles.section}
    >
      {(title || actions) && (
        <div style={styles.header}>
          <div>
            {title && <h2 style={styles.title}>{title}</h2>}
            {description && <p style={styles.description}>{description}</p>}
          </div>
          {actions && <div style={styles.actions}>{actions}</div>}
        </div>
      )}
      {children}
    </motion.section>
  )
}

const styles: Record<string, React.CSSProperties> = {
  section: {
    marginBottom: 'var(--space-8)',
  },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 'var(--space-4)',
    gap: 'var(--space-4)',
  },
  title: {
    fontSize: 'var(--text-lg)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    lineHeight: 'var(--leading-tight)',
  },
  description: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-secondary)',
    marginTop: 'var(--space-1)',
  },
  actions: {
    display: 'flex',
    gap: 'var(--space-2)',
    flexShrink: 0,
  },
}
