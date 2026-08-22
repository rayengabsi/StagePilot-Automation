import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/matches', label: 'Matches' },
  { to: '/filters', label: 'Filters' },
  { to: '/scheduler', label: 'Scheduler' },
  { to: '/profile', label: 'Profile' },
]

export default function Sidebar() {
  return (
    <aside style={aside}>
      <div style={logo}>StagePilot</div>
      <nav style={nav}>
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === '/'}
            style={({ isActive }) => ({
              ...link,
              background: isActive ? '#2563eb' : 'transparent',
              color: isActive ? '#fff' : '#cbd5e1',
            })}
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

export function Layout() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <main style={main}>
        <Outlet />
      </main>
    </div>
  )
}

const aside = {
  width: 220,
  background: '#0f172a',
  color: '#e2e8f0',
  display: 'flex',
  flexDirection: 'column' as const,
  flexShrink: 0,
}

const logo = {
  fontSize: 20,
  fontWeight: 700,
  padding: '20px 16px',
  borderBottom: '1px solid #1e293b',
}

const nav = { display: 'flex', flexDirection: 'column' as const, gap: 2, padding: '8px 0' }

const link = {
  display: 'block',
  padding: '10px 16px',
  borderRadius: 6,
  margin: '0 8px',
  textDecoration: 'none',
  fontSize: 14,
  fontWeight: 500,
}

const main = { flex: 1, padding: 32, background: '#f8fafc', overflow: 'auto' }
