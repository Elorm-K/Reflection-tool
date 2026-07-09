import { useState } from 'react'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { BackLink, Button, Card, Field, FormError, useToast } from '../../components/ui'
import styles from './instructor.module.css'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const toast = useToast()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await instructorApi.forgotPassword(email.trim())
      setSent(true)
    } catch (err) {
      const detail = (err as ApiError).detail ?? 'could not request a reset'
      setError(detail)
      toast(detail, true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.authShell}>
      <BackLink to="/login">Log in</BackLink>
      <div className={styles.logo}>GroupMatcher</div>
      <div className={styles.logoSub}>Reset your password</div>
      <Card>
        {sent ? (
          <p>
            If that email is registered, a reset link has been created — contact your pilot
            administrator to receive it. The link expires in 60 minutes.
          </p>
        ) : (
          <form onSubmit={submit}>
            <Field label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setError(null)
                }}
                required
              />
            </Field>
            {error && <FormError>{error}</FormError>}
            <Button type="submit" disabled={busy}>
              Request reset link
            </Button>
          </form>
        )}
      </Card>
    </div>
  )
}
