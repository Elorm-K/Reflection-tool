import { Navigate, NavLink, Outlet } from 'react-router-dom'
import { getRole } from '../../lib/api/client'
import styles from './student.module.css'

const TABS = [
  { to: '/s/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/s/group', label: 'My Group', icon: '𐀪𐀪' },
  { to: '/s/tasks', label: 'Tasks', icon: '☰' },
  { to: '/s/profile', label: 'Profile', icon: '◉' },
]

export function StudentLayout() {
  if (getRole() !== 'student') return <Navigate to="/join" replace />
  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <h1>GroupMatcher</h1>
        <span className="mono-label">student</span>
      </header>
      <nav className={styles.bottomNav}>
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} className={({ isActive }) => (isActive ? 'active' : '')}>
            <span className={styles.navIcon}>{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
