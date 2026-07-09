import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { BackLink, Button, Card, Field, FormError, useToast } from '../../components/ui'
import styles from './instructor.module.css'

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const toast = useToast()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await instructorApi.resetPassword(token, password)
      toast('Password updated — log in with your new password')
      navigate('/login')
    } catch (err) {
      const detail = (err as ApiError).detail ?? 'could not reset the password'
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
      <div className={styles.logoSub}>Choose a new password</div>
      <Card>
        {token ? (
          <form onSubmit={submit}>
            <Field label="New password">
              <input
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  setError(null)
                }}
                minLength={6}
                required
              />
            </Field>
            {error && <FormError>{error}</FormError>}
            <Button type="submit" disabled={busy}>
              Set new password
            </Button>
          </form>
        ) : (
          <p>
            This page needs a reset link. Request one from the{' '}
            <a href="/forgot-password">forgot password</a> page.
          </p>
        )}
      </Card>
    </div>
  )
}
