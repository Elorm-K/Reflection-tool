import { Link } from 'react-router-dom'
import { Button, Card } from '../../components/ui'
import styles from './instructor.module.css'

export function LandingPage() {
  return (
    <div className={styles.landing}>
      <div className={styles.logo}>GroupMatcher</div>
      <p className={styles.pageIntro} style={{ fontSize: '1.125rem' }}>
        Sort your class into small weekly discussion groups of 3–5, based on when students can
        meet and who they'd feel comfortable opening up around. You review and approve every
        grouping before students see anything.
      </p>
      <div className={styles.landingGrid}>
        <Card>
          <h3>Students</h3>
          <p style={{ color: 'var(--muted)' }}>
            Join with the class code from your instructor, paint your free times, done.
          </p>
          <Link to="/join">
            <Button>Join a class ▷</Button>
          </Link>
        </Card>
        <Card>
          <h3>Instructors</h3>
          <p style={{ color: 'var(--muted)' }}>
            Upload a roster, collect availability, run the matcher, review, publish.
          </p>
          <Link to="/login">
            <Button variant="secondary">Instructor portal ▷</Button>
          </Link>
        </Card>
      </div>
      <p className="mono-label" style={{ marginTop: 32 }}>
        Privacy: demographic survey data is only ever visible to the instructor during review —
        never to other students, never after publication.
      </p>
    </div>
  )
}
