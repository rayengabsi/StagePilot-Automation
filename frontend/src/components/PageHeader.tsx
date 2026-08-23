interface Props {
  title: string
  description?: string
  actions?: React.ReactNode
}

export default function PageHeader({ title, description, actions }: Props) {
  return (
    <div style={styles.header}>
      <div>
        <h1 style={styles.title}>{title}</h1>
        {description && <p style={styles.description}>{description}</p>}
      </div>
      {actions && <div style={styles.actions}>{actions}</div>}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 'var(--space-6)',
    gap: 'var(--space-4)',
  },
  title: {
    fontSize: 'var(--text-xl)',
    fontWeight: 'var(--weight-bold)' as unknown as number,
    color: 'var(--gray-900)',
    lineHeight: 1.2,
  },
  description: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-500)',
    marginTop: 'var(--space-1)',
  },
  actions: {
    display: 'flex',
    gap: 'var(--space-2)',
    flexShrink: 0,
  },
}
