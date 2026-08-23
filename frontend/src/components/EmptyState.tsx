import { motion } from 'framer-motion'
import { Search } from 'lucide-react'

interface Props {
  title: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
}

export default function EmptyState({ title, description, icon, action }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      style={styles.container}
    >
      <div style={styles.icon}>{icon || <Search size={32} strokeWidth={1.2} />}</div>
      <h3 style={styles.title}>{title}</h3>
      {description && <p style={styles.description}>{description}</p>}
      {action && <div style={styles.action}>{action}</div>}
    </motion.div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-12) var(--space-8)',
    textAlign: 'center',
  },
  icon: {
    marginBottom: 'var(--space-4)',
    color: 'var(--sp-text-muted)',
    opacity: 0.6,
  },
  title: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    marginBottom: 'var(--space-2)',
  },
  description: {
    fontSize: 'var(--text-base)',
    color: 'var(--sp-text-secondary)',
    maxWidth: 360,
    lineHeight: 'var(--leading-relaxed)',
  },
  action: {
    marginTop: 'var(--space-5)',
  },
}
