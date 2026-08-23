import { motion } from 'framer-motion'
import { AlertCircle, RefreshCw } from 'lucide-react'

interface Props {
  message?: string
  onRetry?: () => void
}

export default function ErrorState({ message = 'Something went wrong', onRetry }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      style={styles.container}
    >
      <div style={styles.icon}>
        <AlertCircle size={28} strokeWidth={1.5} />
      </div>
      <h3 style={styles.title}>Something went wrong</h3>
      <p style={styles.message}>{message}</p>
      {onRetry && (
        <button onClick={onRetry} style={styles.btn}>
          <RefreshCw size={14} />
          Try again
        </button>
      )}
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
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-red-border)',
  },
  icon: {
    marginBottom: 'var(--space-3)',
    color: 'var(--sp-red)',
    opacity: 0.8,
  },
  title: {
    fontSize: 'var(--text-lg)',
    fontWeight: 'var(--weight-semibold)',
    color: 'var(--sp-text-primary)',
    marginBottom: 'var(--space-2)',
  },
  message: {
    fontSize: 'var(--text-md)',
    color: 'var(--sp-text-secondary)',
    maxWidth: 360,
    marginBottom: 'var(--space-5)',
    lineHeight: 'var(--leading-relaxed)',
  },
  btn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-2) var(--space-4)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--sp-border-strong)',
    background: 'var(--sp-surface-raised)',
    color: 'var(--sp-text-primary)',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  },
}
