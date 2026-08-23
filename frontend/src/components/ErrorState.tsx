interface Props {
  message?: string
  onRetry?: () => void
}

export default function ErrorState({ message = 'Something went wrong', onRetry }: Props) {
  return (
    <div style={styles.container}>
      <div style={styles.icon}>
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="var(--red-500)" strokeWidth="1.5">
          <circle cx="16" cy="16" r="12" />
          <path d="M16 10v8M16 22v0" strokeLinecap="round" />
        </svg>
      </div>
      <h3 style={styles.title}>Error</h3>
      <p style={styles.message}>{message}</p>
      {onRetry && (
        <button onClick={onRetry} style={styles.btn}>
          Try again
        </button>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-12) var(--space-8)',
    textAlign: 'center' as const,
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--red-100)',
  },
  icon: {
    marginBottom: 'var(--space-3)',
  },
  title: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-900)',
    marginBottom: 'var(--space-2)',
  },
  message: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-500)',
    maxWidth: 360,
    marginBottom: 'var(--space-4)',
  },
  btn: {
    padding: 'var(--space-2) var(--space-4)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border-default)',
    background: 'var(--surface-card)',
    color: 'var(--gray-700)',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
    cursor: 'pointer',
  },
}
