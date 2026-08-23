interface Column {
  key: string
  label: string
  width?: string
  align?: 'left' | 'center' | 'right'
  render?: (value: unknown, row: Record<string, unknown>) => React.ReactNode
}

interface Props {
  columns: (string | Column)[]
  rows: (string | number | boolean | null | undefined | React.ReactNode)[][] | Record<string, unknown>[]
  empty?: string
  emptyIcon?: React.ReactNode
  onRowClick?: (row: Record<string, unknown>) => void
}

function isColumnArray(columns: (string | Column)[]): columns is Column[] {
  return columns.length > 0 && typeof columns[0] === 'object' && 'key' in (columns[0] as Column)
}

function normalizeColumns(columns: (string | Column)[]): Column[] {
  if (isColumnArray(columns)) return columns
  return columns.map((label, i) => ({ key: `col_${i}`, label: String(label) }))
}

function normalizeRows(
  rows: (string | number | boolean | null | undefined | React.ReactNode)[][] | Record<string, unknown>[],
  columns: Column[],
): Record<string, unknown>[] {
  if (rows.length === 0) return []
  if (typeof rows[0] === 'object' && !Array.isArray(rows[0])) {
    return rows as Record<string, unknown>[]
  }
  return (rows as (string | number | boolean | null | undefined | React.ReactNode)[][]).map((row) => {
    const obj: Record<string, unknown> = {}
    columns.forEach((col, i) => { obj[col.key] = row[i] })
    return obj
  })
}

export default function Table({ columns: rawColumns, rows: rawRows, empty = 'No data', emptyIcon }: Props) {
  const columns = normalizeColumns(rawColumns)
  const rows = normalizeRows(rawRows, columns)

  if (rows.length === 0) {
    return (
      <div style={styles.emptyState}>
        {emptyIcon || <EmptyTableIcon />}
        <p style={styles.emptyText}>{empty}</p>
      </div>
    )
  }

  return (
    <div style={styles.tableWrap}>
      <table style={styles.table}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  ...styles.th,
                  width: col.width,
                  textAlign: col.align || 'left',
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={styles.tr}>
              {columns.map((col) => (
                <td
                  key={col.key}
                  style={{
                    ...styles.td,
                    textAlign: col.align || 'left',
                  }}
                >
                  {col.render
                    ? col.render(row[col.key], row)
                    : (row[col.key] == null ? '—' : String(row[col.key]))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EmptyTableIcon() {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="var(--gray-300)" strokeWidth="1.5">
      <rect x="4" y="8" width="32" height="28" rx="3" />
      <path d="M4 16h32M14 8v-4M26 8v-4" strokeLinecap="round" />
    </svg>
  )
}

const styles: Record<string, React.CSSProperties> = {
  tableWrap: {
    overflowX: 'auto',
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
    boxShadow: 'var(--shadow-xs)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
  },
  th: {
    padding: 'var(--space-3) var(--space-4)',
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-semibold)' as unknown as number,
    color: 'var(--gray-500)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    borderBottom: '1px solid var(--border-default)',
    whiteSpace: 'nowrap' as const,
    background: 'var(--gray-50)',
  },
  tr: {
    borderBottom: '1px solid var(--border-subtle)',
    transition: 'background var(--transition-fast)',
  },
  td: {
    padding: 'var(--space-3) var(--space-4)',
    fontSize: 'var(--text-base)',
    color: 'var(--gray-700)',
    maxWidth: 300,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-12) var(--space-8)',
    background: 'var(--surface-card)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-default)',
    gap: 'var(--space-3)',
  },
  emptyText: {
    fontSize: 'var(--text-base)',
    color: 'var(--gray-400)',
  },
}

/* Hover effect */
if (typeof document !== 'undefined') {
  const existing = document.getElementById('sp-table-hover')
  if (!existing) {
    const style = document.createElement('style')
    style.id = 'sp-table-hover'
    style.textContent = `table tbody tr:hover { background: var(--gray-50); }`
    document.head.appendChild(style)
  }
}
