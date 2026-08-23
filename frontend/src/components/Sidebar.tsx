import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard', icon: DashboardIcon },
  { to: '/jobs', label: 'Jobs', icon: JobsIcon },
  { to: '/matches', label: 'Matches', icon: MatchesIcon },
  { to: '/filters', label: 'Filters', icon: FiltersIcon },
  { to: '/scheduler', label: 'Scheduler', icon: SchedulerIcon },
  { to: '/profile', label: 'Profile', icon: ProfileIcon },
]

function SidebarContent({ onLinkClick }: { onLinkClick?: () => void }) {
  return (
    <>
      <div style={styles.logoArea}>
        <div style={styles.logoMark}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect width="24" height="24" rx="6" fill="#3b82f6" />
            <path d="M7 8h10M7 12h6M7 16h8" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>
        <span style={styles.logoText}>StagePilot</span>
      </div>
      <nav style={styles.nav} role="navigation" aria-label="Main navigation">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === '/'}
            onClick={onLinkClick}
            style={({ isActive }) => ({
              ...styles.link,
              ...(isActive ? styles.linkActive : styles.linkInactive),
            })}
          >
            <l.icon />
            <span>{l.label}</span>
          </NavLink>
        ))}
      </nav>
      <div style={styles.footer}>
        <div style={styles.footerDot} />
        <span style={styles.footerText}>v1.0</span>
      </div>
    </>
  )
}

export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  return (
    <div style={styles.shell}>
      {/* Desktop sidebar */}
      <aside style={styles.sidebar} className="sidebar-desktop">
        <SidebarContent />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && <div style={styles.overlay} onClick={() => setMobileOpen(false)} />}

      {/* Mobile sidebar */}
      <aside
        style={{
          ...styles.sidebar,
          ...styles.sidebarMobile,
          transform: mobileOpen ? 'translateX(0)' : 'translateX(-100%)',
        }}
        className="sidebar-mobile"
      >
        <SidebarContent onLinkClick={() => setMobileOpen(false)} />
      </aside>

      {/* Main content */}
      <div style={styles.mainWrapper}>
        <header style={styles.mobileHeader}>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            style={styles.hamburger}
            aria-label="Toggle navigation"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              {mobileOpen ? (
                <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              ) : (
                <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              )}
            </svg>
          </button>
          <span style={styles.mobileLogo}>StagePilot</span>
        </header>
        <main style={styles.main}>
          <Outlet />
        </main>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .sidebar-desktop { display: none !important; }
          .sidebar-mobile { display: flex !important; }
        }
        @media (min-width: 769px) {
          .sidebar-mobile { display: none !important; }
        }
      `}</style>
    </div>
  )
}

/* --- Icons --- */
function DashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="5.5" height="5.5" rx="1" />
      <rect x="10.5" y="2" width="5.5" height="5.5" rx="1" />
      <rect x="2" y="10.5" width="5.5" height="5.5" rx="1" />
      <rect x="10.5" y="10.5" width="5.5" height="5.5" rx="1" />
    </svg>
  )
}

function JobsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="14" height="12" rx="2" />
      <path d="M6 4V3a1 1 0 011-1h4a1 1 0 011 1v1" />
    </svg>
  )
}

function MatchesIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2l2.09 4.24L16 6.94l-3.5 3.41.83 4.81L9 12.77l-4.33 2.39.83-4.81L2 6.94l4.91-.7z" />
    </svg>
  )
}

function FiltersIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h14M4 7h10M6 11h6M8 15h2" />
    </svg>
  )
}

function SchedulerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="9" r="7" />
      <path d="M9 5v4l2.5 2.5" />
    </svg>
  )
}

function ProfileIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="6" r="3" />
      <path d="M3 16c0-3.314 2.686-6 6-6s6 2.686 6 6" />
    </svg>
  )
}

/* --- Styles --- */
const styles: Record<string, React.CSSProperties> = {
  shell: {
    display: 'flex',
    minHeight: '100vh',
  },
  sidebar: {
    width: 'var(--sidebar-width)',
    background: 'var(--surface-sidebar)',
    color: 'var(--gray-300)',
    display: 'flex',
    flexDirection: 'column',
    flexShrink: 0,
    position: 'fixed',
    top: 0,
    left: 0,
    bottom: 0,
    zIndex: 40,
    transition: 'transform var(--transition-base)',
  },
  sidebarMobile: {
    position: 'fixed',
    width: 'var(--sidebar-width)',
    boxShadow: 'var(--shadow-lg)',
  },
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.4)',
    zIndex: 30,
  },
  logoArea: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-5) var(--space-5)',
    borderBottom: '1px solid var(--gray-800)',
  },
  logoMark: {
    flexShrink: 0,
  },
  logoText: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-bold)' as unknown as number,
    color: '#ffffff',
    letterSpacing: '-0.01em',
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-1)',
    padding: 'var(--space-3) var(--space-3)',
    flex: 1,
  },
  link: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-2) var(--space-3)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-medium)' as unknown as number,
    textDecoration: 'none',
    transition: 'all var(--transition-fast)',
    lineHeight: 1,
  },
  linkActive: {
    background: 'var(--surface-sidebar-active)',
    color: '#ffffff',
  },
  linkInactive: {
    color: 'var(--gray-400)',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-4) var(--space-5)',
    borderTop: '1px solid var(--gray-800)',
  },
  footerDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: 'var(--green-500)',
  },
  footerText: {
    fontSize: 'var(--text-sm)',
    color: 'var(--gray-500)',
  },
  mainWrapper: {
    flex: 1,
    marginLeft: 'var(--sidebar-width)',
    display: 'flex',
    flexDirection: 'column',
    minHeight: '100vh',
  },
  main: {
    flex: 1,
    padding: 'var(--space-8)',
    maxWidth: 'var(--content-max-width)',
    width: '100%',
    animation: 'fadeIn 0.2s ease',
  },
  mobileHeader: {
    display: 'none',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-3) var(--space-4)',
    background: 'var(--surface-sidebar)',
    borderBottom: '1px solid var(--gray-800)',
  },
  hamburger: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 36,
    height: 36,
    border: 'none',
    background: 'transparent',
    color: '#ffffff',
    cursor: 'pointer',
    borderRadius: 'var(--radius-md)',
  },
  mobileLogo: {
    fontSize: 'var(--text-base)',
    fontWeight: 'var(--weight-bold)' as unknown as number,
    color: '#ffffff',
  },
}

/* Inject mobile styles */
const mobileCSS = `
  @media (max-width: 768px) {
    .sidebar-desktop { display: none !important; }
    .sidebar-mobile { display: flex !important; }
  }
  @media (min-width: 769px) {
    .sidebar-mobile { display: none !important; }
  }
`

// Inject the mobile CSS
if (typeof document !== 'undefined') {
  const existing = document.getElementById('sp-mobile-nav')
  if (!existing) {
    const style = document.createElement('style')
    style.id = 'sp-mobile-nav'
    style.textContent = mobileCSS
    document.head.appendChild(style)
  }
}

export default function Sidebar() {
  return null
}
