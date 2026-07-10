import type { ReactNode } from 'react'
import {
  cloneElement,
  createContext,
  isValidElement,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'
import { Link } from 'react-router-dom'
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
  error,
  children,
}: {
  label: string
  error?: string
  children: ReactNode
}) {
  const generatedId = useId()
  const child = isValidElement<{ id?: string }>(children) ? children : null
  const inputId = child ? (child.props.id ?? generatedId) : undefined
  return (
    <div className={styles.field}>
      <label htmlFor={inputId}>{label}</label>
      {child ? cloneElement(child, { id: inputId }) : children}
      {error && (
        <p className={styles.formError} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

export function FormError({ children }: { children: ReactNode }) {
  return (
    <p className={styles.formError} role="alert">
      {children}
    </p>
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

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Omitting `onClose` makes the modal a forced choice: no Escape / backdrop dismiss. */
export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title?: string
  onClose?: () => void
  children: ReactNode
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const titleId = useId()

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    panelRef.current?.focus()
    return () => previous?.focus()
  }, [open])

  if (!open) return null

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose?.()
      return
    }
    if (e.key !== 'Tab' || !panelRef.current) return
    const els = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (els.length === 0) return
    const first = els[0]
    const last = els[els.length - 1]
    const active = document.activeElement
    if (e.shiftKey && (active === first || active === panelRef.current)) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && active === last) {
      e.preventDefault()
      first.focus()
    }
  }

  return (
    <div
      className={styles.modalBackdrop}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        ref={panelRef}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        {title && (
          <h3 id={titleId} className={styles.modalTitle}>
            {title}
          </h3>
        )}
        {children}
      </div>
    </div>
  )
}

/* --- back link ------------------------------------------------------------ */

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className={styles.backLink}>
      ← {children}
    </Link>
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
