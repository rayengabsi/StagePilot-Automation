import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LayoutDashboard, Briefcase, Star, SlidersHorizontal, Clock, User, Menu, X, Navigation } from 'lucide-react'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/matches', label: 'Matches', icon: Star },
  { to: '/filters', label: 'Filters', icon: SlidersHorizontal },
  { to: '/scheduler', label: 'Automation', icon: Clock },
  { to: '/profile', label: 'Profile', icon: User },
]

function SidebarContent({ onLinkClick }: { onLinkClick?: () => void }) {
  return (
    <>
      <div style={styles.logoArea}>
        <div style={styles.logoMark}>
          <Navigation size={18} strokeWidth={2.5} />
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
            <l.icon size={16} strokeWidth={1.8} />
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
      <aside style={styles.sidebar} className="sidebar-desktop">
        <SidebarContent />
      </aside>

      {mobileOpen && <div style={styles.overlay} onClick={() => setMobileOpen(false)} />}

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

      <div style={styles.mainWrapper}>
        <header style={styles.mobileHeader}>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            style={styles.hamburger}
            aria-label="Toggle navigation"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div style={styles.mobileLogoMark}>
            <Navigation size={14} strokeWidth={2.5} />
          </div>
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

const styles: Record<string, React.CSSProperties> = {
  shell: {
    display: 'flex',
    minHeight: '100vh',
  },
  sidebar: {
    width: 'var(--sidebar-width)',
    background: 'var(--surface-sidebar)',
    color: 'var(--sp-text-secondary)',
    display: 'flex',
    flexDirection: 'column',
    flexShrink: 0,
    position: 'fixed',
    top: 0,
    left: 0,
    bottom: 0,
    zIndex: 40,
    borderRight: '1px solid var(--sp-border)',
  },
  sidebarMobile: {
    position: 'fixed',
    width: 'var(--sidebar-width)',
    boxShadow: 'var(--shadow-xl)',
  },
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.6)',
    backdropFilter: 'blur(4px)',
    zIndex: 30,
  },
  logoArea: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-5) var(--space-5)',
    borderBottom: '1px solid var(--sp-border)',
  },
  logoMark: {
    width: 32,
    height: 32,
    borderRadius: 'var(--radius-md)',
    background: 'linear-gradient(135deg, var(--sp-accent), #4F7AE6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    flexShrink: 0,
  },
  logoText: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-text-primary)',
    letterSpacing: 'var(--tracking-tight)',
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-0-5)',
    padding: 'var(--space-3) var(--space-3)',
    flex: 1,
  },
  link: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-2) var(--space-3)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-medium)',
    textDecoration: 'none',
    transition: 'all var(--transition-fast)',
    lineHeight: 1,
  },
  linkActive: {
    background: 'var(--sp-accent-dim)',
    color: 'var(--sp-accent)',
  },
  linkInactive: {
    color: 'var(--sp-text-muted)',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-4) var(--space-5)',
    borderTop: '1px solid var(--sp-border)',
  },
  footerDot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: 'var(--sp-green)',
    animation: 'pulse-dot 2s ease-in-out infinite',
  },
  footerText: {
    fontSize: 'var(--text-xs)',
    color: 'var(--sp-text-muted)',
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
    animation: 'fadeIn 0.3s var(--ease-out)',
  },
  mobileHeader: {
    display: 'none',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-3) var(--space-4)',
    background: 'var(--surface-sidebar)',
    borderBottom: '1px solid var(--sp-border)',
  },
  hamburger: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 36,
    height: 36,
    border: 'none',
    background: 'transparent',
    color: 'var(--sp-text-primary)',
    borderRadius: 'var(--radius-md)',
  },
  mobileLogoMark: {
    width: 22,
    height: 22,
    borderRadius: 'var(--radius-xs)',
    background: 'linear-gradient(135deg, var(--sp-accent), #4F7AE6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
  },
  mobileLogo: {
    fontSize: 'var(--text-md)',
    fontWeight: 'var(--weight-bold)',
    color: 'var(--sp-text-primary)',
    letterSpacing: 'var(--tracking-tight)',
  },
}

export default function Sidebar() {
  return null
}
