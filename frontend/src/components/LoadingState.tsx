interface Props {
  rows?: number
}

export default function LoadingState({ rows = 5 }: Props) {
  return (
    <div style={styles.container}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={styles.row}>
          <div style={{ ...styles.line, width: `${40 + Math.random() * 30}%` }} />
          <div style={{ ...styles.line, width: `${20 + Math.random() * 20}%` }} />
        </div>
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--space-3)',
    padding: 'var(--space-4) 0',
  },
  row: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--space-2)',
    padding: 'var(--space-4)',
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
  },
  line: {
    height: 14,
    borderRadius: 'var(--radius-sm)',
    background: 'linear-gradient(90deg, var(--gray-100) 25%, var(--gray-200) 50%, var(--gray-100) 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
  },
}
