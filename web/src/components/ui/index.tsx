import type { ReactNode } from 'react'
import { createContext, useCallback, useContext, useState } from 'react'
import styles from './ui.module.css'

/* --- buttons ---------------------------------------------------------- */

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
}

export function Button({ variant = 'primary', ...rest }: BtnProps) {
  const cls = {
    primary: styles.btn,
    secondary: styles.btnSecondary,
    danger: styles.btnDanger,
    ghost: styles.btnGhost,
  }[variant]
  return <button className={cls} {...rest} />
}

/* --- surfaces ---------------------------------------------------------- */

export function Card({
  children,
  flat,
  className,
}: {
  children: ReactNode
  flat?: boolean
  className?: string
}) {
  return (
    <div className={`${flat ? styles.cardFlat : styles.card} ${className ?? ''}`}>{children}</div>
  )
}

export function Badge({
  children,
  variant = 'solid',
}: {
  children: ReactNode
  variant?: 'solid' | 'outline' | 'alert'
}) {
  const cls = {
    solid: styles.badge,
    outline: styles.badgeOutline,
    alert: styles.badgeAlert,
  }[variant]
  return <span className={cls}>{children}</span>
}

/* --- form -------------------------------------------------------------- */

export function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className={styles.field}>
      <label>{label}</label>
      {children}
    </div>
  )
}

export function NumberStepper({
  value,
  min,
  max,
  onChange,
}: {
  value: number
  min: number
  max: number
  onChange: (v: number) => void
}) {
  return (
    <div className={styles.stepper}>
      <button type="button" aria-label="decrease" onClick={() => onChange(Math.max(min, value - 1))}>
        −
      </button>
      <span>{value}</span>
      <button type="button" aria-label="increase" onClick={() => onChange(Math.min(max, value + 1))}>
        +
      </button>
    </div>
  )
}

/* --- modal -------------------------------------------------------------- */

export function Modal({
  open,
  children,
}: {
  open: boolean
  children: ReactNode
}) {
  if (!open) return null
  return (
    <div className={styles.modalBackdrop} role="dialog" aria-modal="true">
      <div className={styles.modal}>{children}</div>
    </div>
  )
}

/* --- lifecycle steps (proposed -> approved -> published) ----------------- */

export function LifecycleSteps({
  steps,
  activeIndex,
}: {
  steps: string[]
  activeIndex: number
}) {
  return (
    <div className={styles.lifecycle}>
      {steps.map((s, i) => (
        <div key={s} className={i === activeIndex ? styles.lifecycleActive : styles.lifecycleStep}>
          <span className={styles.lifecycleNum}>{i + 1}</span>
          {s}
        </div>
      ))}
    </div>
  )
}

/* --- toast --------------------------------------------------------------- */

interface Toast {
  id: number
  text: string
  error?: boolean
}

const ToastContext = createContext<(text: string, error?: boolean) => void>(() => {})

export function useToast() {
  return useContext(ToastContext)
}

let toastId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((text: string, error = false) => {
    const id = ++toastId
    setToasts((t) => [...t, { id, text, error }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className={styles.toastHost}>
        {toasts.map((t) => (
          <div key={t.id} className={t.error ? styles.toastError : styles.toast} role="status">
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

/* --- table ---------------------------------------------------------------- */

export function Table({ children }: { children: ReactNode }) {
  return <table className={styles.table}>{children}</table>
}
