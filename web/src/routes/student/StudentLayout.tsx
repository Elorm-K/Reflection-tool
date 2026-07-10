import { useQuery } from '@tanstack/react-query'
import { Navigate, NavLink, Outlet } from 'react-router-dom'
import { getRole } from '../../lib/api/client'
import { studentApi } from '../../lib/api/student'
import styles from './student.module.css'

const TABS = [
  { to: '/s/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/s/group', label: 'My Group', icon: '𐀪𐀪' },
  { to: '/s/tasks', label: 'Tasks', icon: '☰' },
  { to: '/s/profile', label: 'Profile', icon: '◉' },
]

export function StudentLayout() {
  const isStudent = getRole() === 'student'
  const { data: notifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: studentApi.notifications,
    enabled: isStudent,
    refetchInterval: 30000,
  })
  if (!isStudent) return <Navigate to="/join" replace />
  const unread = notifications?.unread ?? 0
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
            {t.to === '/s/group' && unread > 0 && (
              <span className={styles.navBadge} aria-label={`${unread} unread updates`}>
                {unread}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
