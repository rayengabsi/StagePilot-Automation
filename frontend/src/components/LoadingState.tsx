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
    flexDirection: 'column',
    gap: 'var(--space-3)',
    padding: 'var(--space-4) 0',
  },
  row: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    padding: 'var(--space-4)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--sp-border)',
  },
  line: {
    height: 14,
    borderRadius: 'var(--radius-sm)',
    background: 'linear-gradient(90deg, var(--sp-surface-raised) 25%, var(--sp-surface-hover) 50%, var(--sp-surface-raised) 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
  },
}
