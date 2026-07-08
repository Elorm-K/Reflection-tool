import { Navigate, NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { clearAuth, getRole } from '../../lib/api/client'
import styles from './instructor.module.css'

export function InstructorLayout() {
  const { classId } = useParams()
  const navigate = useNavigate()
  if (getRole() !== 'instructor') return <Navigate to="/login" replace />

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          Group
          <br />
          Matcher
        </div>
        <div className={styles.logoSub}>Instructor Portal</div>
        <nav className={styles.nav}>
          <NavLink to="/i/classes" end>
            ▦ Classes
          </NavLink>
          {classId && (
            <>
              <NavLink to={`/i/classes/${classId}`} end>
                1. Overview
              </NavLink>
              <NavLink to={`/i/classes/${classId}/config`}>2. Match Logic</NavLink>
              <NavLink to={`/i/classes/${classId}/review`}>3. Review</NavLink>
              <NavLink to={`/i/classes/${classId}/publish`}>4. Publish</NavLink>
            </>
          )}
        </nav>
        <div className={styles.sidebarFooter}>
          <NavLink to="/i/help">? Help</NavLink>
          <button
            style={{ background: 'none', border: 'none', textAlign: 'left', fontWeight: 700, padding: 0 }}
            onClick={() => {
              clearAuth()
              navigate('/')
            }}
          >
            ⇥ Logout
          </button>
        </div>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
