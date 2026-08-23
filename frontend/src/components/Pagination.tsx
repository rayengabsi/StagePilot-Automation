interface Props {
  offset: number
  total: number
  pageSize: number
  onPageChange: (offset: number) => void
}

export default function Pagination({ offset, total, pageSize, onPageChange }: Props) {
  const hasNext = offset + pageSize < total
  const hasPrev = offset > 0
  const start = total === 0 ? 0 : offset + 1
  const end = Math.min(offset + pageSize, total)

  return (
    <div style={styles.pagination}>
      <button
        disabled={!hasPrev}
        onClick={() => onPageChange(offset - pageSize)}
        style={{ ...styles.btn, ...(!hasPrev ? styles.btnDisabled : {}) }}
        aria-label="Previous page"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <path d="M9 3L5 7l4 4" />
        </svg>
        Previous
      </button>
      <span style={styles.info}>
        {start}–{end} of {total}
      </span>
      <button
        disabled={!hasNext}
        onClick={() => onPageChange(offset + pageSize)}
        style={{ ...styles.btn, ...(!hasNext ? styles.btnDisabled : {}) }}
        aria-label="Next page"
      >
        Next
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <path d="M5 3l4 4-4 4" />
        </svg>
      </button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  pagination: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--space-4)',
    marginTop: 'var(--space-4)',
    padding: 'var(--space-3) 0',
  },
  btn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-1)',
    padding: 'var(--space-2) var(--space-3)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border-default)',
    background: 'var(--surface-card)',
    color: 'var(--gray-700)',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  },
  btnDisabled: {
    opacity: 0.4,
    cursor: 'not-allowed',
  },
  info: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
    fontVariantNumeric: 'tabular-nums',
  },
}
