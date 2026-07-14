import { Link } from 'react-router-dom'
import { FAQ } from './faq'
import styles from './instructor.module.css'

/**
 * Public instructor-facing landing page (the logged-out `/` route).
 *
 * Content/IA follows Greg's brief (outcomes-first ordering); the visual layer
 * matches the Figma frame "Instructor - Landing / Onboarding" (36:1536),
 * rendered with the repo's existing brutalist tokens rather than Figma's inline
 * literals. Two deliberate departures from the mockup, per the brief + the
 * project's demographic-privacy invariant:
 *   - matching criteria are framed generically ("designed to help the group
 *     work well"), never as diversity/demographic matching;
 *   - the "what reflection groups are" section (absent from Figma) is added
 *     before the effort breakdown.
 */

/**
 * Real student quotes go here (from the reflection-groups papers). Until then
 * these render as visibly-labeled placeholders — this is a public page, so we
 * never ship realistic-looking fake testimonials. Replace `text`/`attribution`
 * with the real quote and remove `placeholder`.
 */
const QUOTES: { text: string; attribution: string; placeholder?: boolean }[] = [
  {
    text: '[ Student quote about combating isolation — how the group made them feel less alone. From the reflection-groups paper. ]',
    attribution: '[ attribution ]',
    placeholder: true,
  },
  {
    text: '[ Student quote about learning together — thinking out loud with peers. From the reflection-groups paper. ]',
    attribution: '[ attribution ]',
    placeholder: true,
  },
  {
    text: '[ Student quote about reflection quality or belonging. From the reflection-groups paper. ]',
    attribution: '[ attribution ]',
    placeholder: true,
  },
]

/** Effort breakdown — the Figma "What's Involved" section, reframed per the brief. */
const WHAT_YOU_DO = [
  'Upload your roster and course schedule.',
  'Choose the criteria that help groups work well together.',
  'Review and approve the final groups.',
]
const WHAT_STUDENTS_DO = [
  'Mark their weekly availability.',
  'Answer a short, optional survey.',
  'Meet with their group each week.',
]

/** Low-effort meter bars. Values are estimates awaiting confirmation — see [VERIFY]. */
const EFFORT = [
  { label: 'Setup', value: '15–20 minutes', fill: 25 },
  { label: 'Ongoing', value: '~5 minutes / week', fill: 8 },
]

function PersonIcon() {
  return (
    <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" focusable="false">
      <circle cx="8" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.5 14c0-3 2.5-5 5.5-5s5.5 2 5.5 5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}
function PeopleIcon() {
  return (
    <svg viewBox="0 0 24 16" width="26" height="18" aria-hidden="true" focusable="false">
      <circle cx="8" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.5 14c0-3 2.5-4.5 5.5-4.5S13.5 11 13.5 14" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="17" cy="5.5" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M14 14c0-2.5 1.8-4 4-4s3.5 1.5 3.5 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}
function ClockIcon() {
  return (
    <svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true" focusable="false">
      <circle cx="9" cy="9" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M9 5v4.5l3 2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
function LockIcon() {
  return (
    <svg viewBox="0 0 16 20" width="16" height="20" aria-hidden="true" focusable="false">
      <rect x="2.5" y="8" width="11" height="9" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5 8V5.5a3 3 0 0 1 6 0V8" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}
function Chevron() {
  return (
    <svg className={styles.faqChevron} viewBox="0 0 12 8" width="12" height="8" aria-hidden="true" focusable="false">
      <path d="M1 1.5 6 6.5l5-5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  )
}

export function LandingPage() {
  return (
    <div className={styles.landingPage}>
      {/* Public header — brand + the one real pre-login action */}
      <header className={styles.landingHeader}>
        <span className={styles.landingBrand}>Reflection Groups</span>
        <nav className={styles.landingHeaderNav} aria-label="Primary">
          <Link to="/join">Join a class</Link>
          <Link to="/login" className={styles.landingHeaderCta}>
            Instructor login
          </Link>
        </nav>
      </header>

      <main className={styles.landing}>
        {/* 1. Hero — lead with outcomes */}
        <section className={styles.hero}>
          <span className={styles.heroBadge}>For instructors</span>
          <h1 className={styles.heroTitle}>
            No student learns <span className={styles.heroMark}>alone</span>.
          </h1>
          <p className={styles.heroSub}>
            Reflection groups are small weekly discussion groups where students reflect together on
            their learning and their AI use — building belonging, surfacing shared challenges, and
            giving everyone a place to think out loud. Without adding to your workload.
          </p>
          <div className={`${styles.landingSection} ${styles.placeholder} ${styles.heroOutcome}`}>
            <span className="mono-label">Outcomes — replace with real findings</span>
            <p style={{ margin: '8px 0 0' }}>
              [ Headline outcome from the reflection-groups papers — what students reported about
              belonging, engagement, or reflection quality. ]
            </p>
          </div>
          <div className={styles.heroActions}>
            <Link to="/login">
              <button type="button" className={styles.ctaLarge}>
                Get started ▷
              </button>
            </Link>
            <a href="#how-it-works" className={styles.heroSecondary}>
              See how it works
            </a>
          </div>
        </section>

        {/* 2. Student quotes */}
        <section className={styles.landingSection} aria-labelledby="quotes-head">
          <p id="quotes-head" className={styles.sectionEyebrow}>
            Student success stories
          </p>
          <div className={styles.quoteGrid}>
            {QUOTES.map((q, i) => (
              <figure key={i} className={`${styles.quoteCard} ${q.placeholder ? styles.placeholder : ''}`}>
                <span className={styles.quoteChip}>Student quote</span>
                <blockquote className={styles.quote}>
                  <p style={{ margin: 0 }}>“{q.text}”</p>
                </blockquote>
                <figcaption className={styles.quoteAttrRow}>
                  <span className={styles.quoteAvatar} aria-hidden="true" />
                  <span className={styles.quoteAttr}>{q.attribution}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>

        {/* 3. What reflection groups are (not in Figma — added per brief) */}
        <section className={`${styles.landingSection} ${styles.whatIs}`} aria-labelledby="whatis-head">
          <h2 id="whatis-head">What are reflection groups?</h2>
          <p>
            Each week, a small group of 3–5 students meets to reflect on how their learning is going
            and how they’re using AI. The point isn’t more content — it’s helping students build the
            skills and character to learn well: noticing what’s hard, being honest about it, and
            getting into the habit of thinking alongside peers.
          </p>
          <p>
            It’s a high-agency space where students learn <em>together</em> rather than feeling alone.
            Groups are matched on criteria designed to help the group work well — so the conversation
            feels safe enough for real reflection, and no one feels like the only one in the room.
          </p>
        </section>

        {/* 4. How easy it is — the Figma "What's Involved" three columns */}
        <section className={styles.landingSection} id="how-it-works" aria-labelledby="involved-head">
          <p id="involved-head" className={styles.sectionEyebrow}>
            Low effort to run
          </p>
          <div className={styles.involvedGrid}>
            <div className={styles.involvedCol}>
              <h3 className={styles.involvedHead}>
                <PersonIcon /> What you do
              </h3>
              <ol className={styles.involvedList}>
                {WHAT_YOU_DO.map((item, i) => (
                  <li key={item}>
                    <span className={styles.involvedNum}>{String(i + 1).padStart(2, '0')}.</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </div>
            <div className={styles.involvedCol}>
              <h3 className={styles.involvedHead}>
                <PeopleIcon /> What students do
              </h3>
              <ol className={styles.involvedList}>
                {WHAT_STUDENTS_DO.map((item, i) => (
                  <li key={item}>
                    <span className={styles.involvedNum}>{String(i + 1).padStart(2, '0')}.</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </div>
            <div className={styles.involvedCol}>
              <h3 className={styles.involvedHead}>
                <ClockIcon /> How long it takes
              </h3>
              <div className={styles.meterList}>
                {EFFORT.map((e) => (
                  <div key={e.label} className={styles.meter}>
                    <span className={styles.meterLabel}>{e.label}</span>
                    <div className={styles.meterBar}>
                      <span className={styles.meterFill} style={{ width: `${e.fill}%` }} />
                    </div>
                    <span className={styles.meterValue}>
                      {e.value} <span className="mono-label">[VERIFY]</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* 5. FAQ — instructor objections (shared, privacy-safe content) */}
        <section className={`${styles.landingSection} ${styles.faqSection}`} aria-labelledby="faq-head">
          <h2 id="faq-head" className={styles.faqHeading}>
            Frequently asked questions
          </h2>
          <div className={styles.faqList}>
            {FAQ.map(([q, a]) => (
              <details key={q} className={styles.faqItem}>
                <summary className={styles.faqSummary}>
                  <span>{q}</span>
                  <Chevron />
                </summary>
                <p className={styles.faqAnswer}>{a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* 6. Final call to action + privacy note */}
        <section className={styles.finalCta}>
          <Link to="/login">
            <button type="button" className={styles.ctaLarge}>
              Create your first group ▷
            </button>
          </Link>
          <div className={styles.privacyNote}>
            <span className={styles.privacyIcon} aria-hidden="true">
              <LockIcon />
            </span>
            <div>
              <span className="mono-label">Privacy note</span>
              <p style={{ margin: '4px 0 0' }}>
                Survey answers are visible only to you, only during review — never to students, never
                after publication.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Dark footer — real links only */}
      <footer className={styles.landingFooter}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrandCol}>
            <p className={styles.footerBrand}>Reflection Groups</p>
            <p className={styles.footerTagline}>
              Small weekly groups that help students reflect, build belonging, and learn together —
              part of Reflectool.
            </p>
          </div>
          <nav className={styles.footerLinks} aria-label="Footer">
            <span className={styles.footerColHead}>Get started</span>
            <Link to="/login">Instructor login</Link>
            <Link to="/join">Join a class</Link>
          </nav>
        </div>
        <div className={styles.footerBar}>
          <span>© Reflection Groups</span>
        </div>
      </footer>
    </div>
  )
}
