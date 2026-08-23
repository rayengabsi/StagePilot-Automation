import { ChevronLeft, ChevronRight } from 'lucide-react'

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
        <ChevronLeft size={14} />
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
        <ChevronRight size={14} />
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
    border: '1px solid var(--sp-border)',
    background: 'var(--sp-surface-card)',
    color: 'var(--sp-text-secondary)',
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  },
  btnDisabled: {
    opacity: 0.3,
    cursor: 'not-allowed',
  },
  info: {
    fontSize: 'var(--text-sm)',
    color: 'var(--sp-text-muted)',
    fontVariantNumeric: 'tabular-nums',
  },
}
