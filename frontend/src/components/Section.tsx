interface Props {
  title?: string
  description?: string
  actions?: React.ReactNode
  children: React.ReactNode
}

export default function Section({ title, description, actions, children }: Props) {
  return (
    <section style={styles.section}>
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
    </section>
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
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-900)',
    lineHeight: 1.3,
  },
  description: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    marginTop: 'var(--space-1)',
  },
  actions: {
    display: 'flex',
    gap: 'var(--space-2)',
    flexShrink: 0,
  },
}
