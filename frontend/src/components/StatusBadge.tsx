type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'neutral'

interface Props {
  label: string
  variant?: BadgeVariant
  dot?: boolean
}

const variantStyles: Record<BadgeVariant, { bg: string; color: string; border: string; dotColor: string }> = {
  success: { bg: 'var(--sp-green-dim)', color: 'var(--sp-green)', border: 'var(--sp-green-border)', dotColor: 'var(--sp-green)' },
  error: { bg: 'var(--sp-red-dim)', color: 'var(--sp-red)', border: 'var(--sp-red-border)', dotColor: 'var(--sp-red)' },
  warning: { bg: 'var(--sp-amber-dim)', color: 'var(--sp-amber)', border: 'var(--sp-amber-border)', dotColor: 'var(--sp-amber)' },
  info: { bg: 'var(--sp-accent-dim)', color: 'var(--sp-accent)', border: 'var(--sp-accent-border)', dotColor: 'var(--sp-accent)' },
  neutral: { bg: 'rgba(255, 255, 255, 0.04)', color: 'var(--sp-text-secondary)', border: 'var(--sp-border)', dotColor: 'var(--sp-text-muted)' },
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
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-xs)',
        fontWeight: 'var(--weight-medium)',
        background: v.bg,
        color: v.color,
        border: `1px solid ${v.border}`,
        lineHeight: 1.6,
        whiteSpace: 'nowrap',
      }}
    >
      {dot && (
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: v.dotColor,
            flexShrink: 0,
            animation: variant === 'success' ? 'pulse-dot 2s ease-in-out infinite' : undefined,
          }}
        />
      )}
      {label}
    </span>
  )
}
