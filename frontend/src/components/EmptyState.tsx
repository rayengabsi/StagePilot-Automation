interface Props {
  title: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
}

export default function EmptyState({ title, description, icon, action }: Props) {
  return (
    <div style={styles.container}>
      <div style={styles.icon}>{icon || <DefaultIcon />}</div>
      <h3 style={styles.title}>{title}</h3>
      {description && <p style={styles.description}>{description}</p>}
      {action && <div style={styles.action}>{action}</div>}
    </div>
  )
}

function DefaultIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--gray-300)" strokeWidth="1.5">
      <rect x="6" y="10" width="36" height="32" rx="4" />
      <path d="M6 20h36M16 10v-6M32 10v-6" strokeLinecap="round" />
    </svg>
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
  },
  icon: {
    marginBottom: 'var(--space-4)',
    opacity: 0.6,
  },
  title: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-700)',
    marginBottom: 'var(--space-2)',
  },
  description: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-400)',
    maxWidth: 360,
    lineHeight: 1.5,
  },
  action: {
    marginTop: 'var(--space-4)',
  },
}
