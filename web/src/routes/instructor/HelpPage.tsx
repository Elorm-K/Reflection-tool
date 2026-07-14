import { Card } from '../../components/ui'
import { FAQ } from './faq'
import styles from './instructor.module.css'

export function HelpPage() {
  return (
    <>
      <h2 className={styles.pageTitle}>Help center</h2>
      <p className={styles.pageIntro}>The lifecycle: collect → match → review → approve → publish.</p>
      {FAQ.map(([q, a]) => (
        <div key={q} style={{ marginBottom: 16 }}>
          <Card flat>
            <h3 style={{ marginBottom: 8 }}>{q}</h3>
            <p style={{ margin: 0, color: 'var(--muted)' }}>{a}</p>
          </Card>
        </div>
      ))}
    </>
  )
}
