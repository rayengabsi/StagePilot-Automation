interface Props {
  columns: string[]
  rows: (string | number | boolean | null | undefined | React.ReactNode)[][]
  empty?: string
}

export default function Table({ columns, rows, empty = 'No data' }: Props) {
  return (
    <div style={tableWrap}>
      <table style={table}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} style={th}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} style={emptyStyle}>{empty}</td>
            </tr>
          )}
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} style={td}>
                  {cell == null ? '—' : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const tableWrap = { overflowX: 'auto' as const }
const table = {
  width: '100%', borderCollapse: 'collapse' as const,
  background: '#fff', borderRadius: 10, overflow: 'hidden', border: '1px solid #e2e8f0',
}
const th = {
  textAlign: 'left' as const, padding: '12px 16px', fontSize: 12, fontWeight: 600,
  color: '#64748b', textTransform: 'uppercase' as const, letterSpacing: 0.5,
  borderBottom: '1px solid #e2e8f0', whiteSpace: 'nowrap' as const,
}
const td = {
  padding: '10px 16px', fontSize: 13, color: '#334155', borderBottom: '1px solid #f1f5f9',
  maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
}
const emptyStyle = { padding: 32, textAlign: 'center' as const, color: '#94a3b8' }
