import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { setAuth } from '../../lib/api/client'
import type { ApiError } from '../../lib/api/client'
import { instructorApi } from '../../lib/api/instructor'
import { BackLink, Button, Card, Field, FormError, useToast } from '../../components/ui'
import styles from './instructor.module.css'

export function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const toast = useToast()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const resp =
        mode === 'login'
          ? await instructorApi.login(email, password)
          : await instructorApi.register(email, password, name)
      setAuth(resp.token, 'instructor')
      navigate('/i/classes')
    } catch (err) {
      const detail = (err as ApiError).detail ?? 'authentication failed'
      setError(detail)
      toast(detail, true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.authShell}>
      <BackLink to="/">Home</BackLink>
      <div className={styles.logo}>GroupMatcher</div>
      <div className={styles.logoSub}>Instructor Portal</div>
      <Card>
        <form onSubmit={submit}>
          {mode === 'register' && (
            <Field label="Name">
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
          )}
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
          <Field label="Password">
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
            {mode === 'login' ? 'Log in' : 'Create account'}
          </Button>
        </form>
        <Button variant="ghost" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Need an account? Register' : 'Have an account? Log in'}
        </Button>
      </Card>
    </div>
  )
}
