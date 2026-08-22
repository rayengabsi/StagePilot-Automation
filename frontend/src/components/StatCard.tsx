interface StatCardProps {
  label: string
  value: string | number
  hint?: string
}

export default function StatCard({ label, value, hint }: StatCardProps) {
  return (
    <div style={card}>
      <div style={labelStyle}>{label}</div>
      <div style={valueStyle}>{value}</div>
      {hint && <div style={hintStyle}>{hint}</div>}
    </div>
  )
}

const card = {
  background: '#fff',
  borderRadius: 10,
  padding: '20px 24px',
  border: '1px solid #e2e8f0',
  minWidth: 180,
}

const labelStyle = { fontSize: 13, color: '#64748b', marginBottom: 4, fontWeight: 500 }
const valueStyle = { fontSize: 28, fontWeight: 700, color: '#0f172a' }
const hintStyle = { fontSize: 12, color: '#94a3b8', marginTop: 4 }
