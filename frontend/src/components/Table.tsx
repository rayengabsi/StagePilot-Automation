import { motion } from 'framer-motion'

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

export default function Table({ columns: rawColumns, rows: rawRows, empty = 'No data', emptyIcon, onRowClick }: Props) {
  const columns = normalizeColumns(rawColumns)
  const rows = normalizeRows(rawRows, columns)

  if (rows.length === 0) {
    return (
      <div style={styles.emptyState}>
        {emptyIcon}
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
            <motion.tr
              key={i}
              style={{
                ...styles.tr,
                cursor: onRowClick ? 'pointer' : undefined,
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.02, duration: 0.2 }}
              onClick={() => onRowClick?.(row)}
              whileHover={{ background: 'var(--sp-surface-hover)' }}
            >
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
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  tableWrap: {
    overflowX: 'auto',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-border)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    padding: 'var(--space-3) var(--space-4)',
    fontSize: 'var(--text-xs)',
    fontWeight: 'var(--weight-medium)',
    color: 'var(--sp-text-muted)',
    textTransform: 'uppercase',
    letterSpacing: 'var(--tracking-wide)',
    borderBottom: '1px solid var(--sp-border)',
    whiteSpace: 'nowrap',
    textAlign: 'left',
  },
  tr: {
    borderBottom: '1px solid var(--sp-border)',
    transition: 'background var(--transition-fast)',
  },
  td: {
    padding: 'var(--space-3) var(--space-4)',
    fontSize: 'var(--text-md)',
    color: 'var(--sp-text-primary)',
    maxWidth: 300,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-12) var(--space-8)',
    background: 'var(--sp-surface-card)',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--sp-border)',
    gap: 'var(--space-3)',
  },
  emptyText: {
    fontSize: 'var(--text-md)',
    color: 'var(--sp-text-secondary)',
  },
}
