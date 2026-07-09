import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentApi } from '../../lib/api/student'
import type { ApiError } from '../../lib/api/client'
import { BackLink, Badge, Button, Card, Field, useToast } from '../../components/ui'
import styles from './student.module.css'

const GENDER_OPTIONS = ['Woman', 'Man', 'Non-binary', 'Prefer not to disclose']
const DISABILITY_OPTIONS = ['None', 'ADHD', 'Learning', 'Prefer not to disclose']

function OptionRow({
  options,
  value,
  onPick,
}: {
  options: string[]
  value: string
  onPick: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '8px 0' }}>
      {options.map((o) => (
        <Button
          key={o}
          type="button"
          variant={value === o ? 'primary' : 'secondary'}
          onClick={() => onPick(o)}
        >
          {o}
        </Button>
      ))}
    </div>
  )
}

export function SurveyPage() {
  const [gender, setGender] = useState('')
  const [genderOther, setGenderOther] = useState('')
  const [disability, setDisability] = useState('')
  const [disabilityOther, setDisabilityOther] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const navigate = useNavigate()

  async function submit(skip: boolean) {
    setBusy(true)
    try {
      if (skip) {
        await studentApi.submitSurvey({ skip: true })
      } else {
        await studentApi.submitSurvey({
          gender: genderOther.trim() || gender || undefined,
          disability: disabilityOther.trim() || disability || undefined,
        })
      }
      toast('Survey saved. Thank you!')
      navigate('/s/group')
    } catch (err) {
      toast((err as ApiError).detail ?? 'could not submit', true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <BackLink to="/s/availability">Availability</BackLink>
      <h2 className={styles.pageTitle}>Demographic Survey</h2>
      <Badge>Optional</Badge>
      <p className={styles.pageIntro} style={{ marginTop: 12 }}>
        Optional — you can skip any question. This data helps us ensure balanced group matching.
      </p>

      <Card flat>
        <h3>
          <Badge>Q1</Badge> Gender
        </h3>
        <OptionRow options={GENDER_OPTIONS} value={gender} onPick={setGender} />
        <Field label="Self-describe or other">
          <input
            value={genderOther}
            onChange={(e) => setGenderOther(e.target.value)}
            placeholder="Type here…"
          />
        </Field>
      </Card>

      <div style={{ height: 16 }} />

      <Card flat>
        <h3>
          <Badge>Q2</Badge> Disability
        </h3>
        <OptionRow options={DISABILITY_OPTIONS} value={disability} onPick={setDisability} />
        <Field label="Self-describe or other">
          <input
            value={disabilityOther}
            onChange={(e) => setDisabilityOther(e.target.value)}
            placeholder="Type here…"
          />
        </Field>
      </Card>

      <div className={styles.privacyNote}>
        <span aria-hidden>🔒</span>
        <span>
          <strong>Privacy:</strong> Data only visible to instructors during review. This
          information will never be shared with other students.
        </span>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <Button onClick={() => submit(false)} disabled={busy}>
          Submit survey
        </Button>
        <Button variant="ghost" onClick={() => submit(true)} disabled={busy}>
          Skip
        </Button>
      </div>
    </>
  )
}
