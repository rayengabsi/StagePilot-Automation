type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'neutral'

interface Props {
  label: string
  variant?: BadgeVariant
  dot?: boolean
}

const variantStyles: Record<BadgeVariant, { bg: string; color: string; border: string; dotColor: string }> = {
  success: { bg: 'var(--green-50)', color: 'var(--green-700)', border: 'var(--green-100)', dotColor: 'var(--green-500)' },
  error: { bg: 'var(--red-50)', color: 'var(--red-600)', border: 'var(--red-100)', dotColor: 'var(--red-500)' },
  warning: { bg: 'var(--amber-50)', color: 'var(--amber-600)', border: 'var(--amber-100)', dotColor: 'var(--amber-500)' },
  info: { bg: 'var(--blue-50)', color: 'var(--blue-700)', border: 'var(--blue-100)', dotColor: 'var(--blue-500)' },
  neutral: { bg: 'var(--gray-100)', color: 'var(--gray-600)', border: 'var(--gray-200)', dotColor: 'var(--gray-400)' },
}

export default function StatusBadge({ label, variant = 'neutral', dot = true }: Props) {
  const v = variantStyles[variant]
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 999,
        fontSize: 'var(--text-sm)',
        fontWeight: 'var(--weight-medium)' as unknown as number,
        background: v.bg,
        color: v.color,
        border: `1px solid ${v.border}`,
        lineHeight: 1.6,
        whiteSpace: 'nowrap' as const,
      }}
    >
      {dot && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: v.dotColor,
            flexShrink: 0,
          }}
        />
      )}
      {label}
    </span>
  )
}
