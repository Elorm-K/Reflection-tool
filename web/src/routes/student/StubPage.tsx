import { Card } from '../../components/ui'
import styles from './student.module.css'

export function StubPage({ title }: { title: string }) {
  return (
    <>
      <h2 className={styles.pageTitle}>{title}</h2>
      <Card flat>Coming soon — not part of the pilot.</Card>
    </>
  )
}
