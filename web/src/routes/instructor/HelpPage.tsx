import { Card } from '../../components/ui'
import styles from './instructor.module.css'

const FAQ: [string, string][] = [
  [
    'How does matching work?',
    'A deterministic matcher forms groups of 3–5 that share at least the configured number of mutually free slots, then optimizes for schedule overlap and identity comfort in your configured priority order. The same roster and settings always produce the same groups.',
  ],
  [
    'What do students see?',
    'Only their own group: group number, member names, and meeting slots — after you publish. Never demographic data, theirs or anyone else’s.',
  ],
  [
    'Who can see survey answers?',
    'Only you, only on the review board and composition views, only while reviewing. They are never written into the proposal, notifications, or exports.',
  ],
  [
    'Why is a student unplaced?',
    'Usually not enough schedule overlap with any viable group. Unplaced students are always listed on the review board with a reason — resolve by dragging them into a group (validated live) or following up directly.',
  ],
  [
    'Can I edit groups by hand?',
    'Yes — drag students between groups on the review board while the proposal is in the Proposed state. Every move is re-validated against size and overlap constraints; invalid moves are blocked with the specific reason.',
  ],
  [
    'What does approve actually do?',
    'Approval is a hard gate: nothing reaches students until you approve, and approving requires having viewed the current version of the proposal. Publishing is a separate, final step.',
  ],
]

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
