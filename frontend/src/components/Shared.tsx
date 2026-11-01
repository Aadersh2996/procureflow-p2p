import { useEffect, useRef, type FormEvent, type ReactNode } from 'react'
import { CircleAlert, X } from 'lucide-react'

export function Modal({ title, close, children, wide = false }: { title: string; close: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { const dialog = ref.current; if (dialog && !dialog.open) dialog.showModal() }, [])
  return <dialog ref={ref} className={`modal ${wide ? 'modal-wide' : ''}`} onClose={close} onClick={e => { if (e.target === ref.current) close() }} aria-labelledby="modal-title">
    <div className="modal-head"><h2 id="modal-title">{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={close}><X size={18} /></button></div>
    {children}
  </dialog>
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export function Form({ children, onSubmit, busy = false, submitLabel = 'Save record' }: { children: ReactNode; onSubmit: (event: FormEvent<HTMLFormElement>) => void; busy?: boolean; submitLabel?: string }) {
  return <form className="form" onSubmit={onSubmit}>{children}<div className="form-actions"><button type="submit" className="button button-primary" disabled={busy}>{busy ? 'Saving…' : submitLabel}</button></div></form>
}

export function Status({ value }: { value: string }) {
  const tone = /partial|pending|submitted|draft|unmatched|unapproved/i.test(value) ? 'warning'
    : /exception|rejected|overdue|duplicate|variance/i.test(value) ? 'negative'
      : /approved|paid|received|resolved|matched|active|open$/i.test(value) ? 'positive' : 'neutral'
  return <span className={`status status-${tone}`}><i />{value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, x => x.toUpperCase())}</span>
}

export function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty"><CircleAlert size={24} /><strong>{title}</strong><span>{detail}</span></div>
}

export function TableFrame({ children, empty }: { children: ReactNode; empty?: boolean }) {
  return <div className={`table-frame ${empty ? 'table-empty' : ''}`}>{children}</div>
}

export function ErrorNotice({ message }: { message: string }) {
  return <div role="alert" className="error-notice"><CircleAlert size={17} />{message}</div>
}

export function FieldInput({ label, name, required = true, type = 'text', defaultValue, placeholder, min, step, hint, options }: {
  label: string; name: string; required?: boolean; type?: string; defaultValue?: string | number; placeholder?: string; min?: string; step?: string; hint?: string;
  options?: { value: string | number; label: string }[]
}) {
  return <Field label={label} hint={hint}>{options ? <select name={name} defaultValue={String(defaultValue ?? options[0]?.value)} required={required}>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
    : <input name={name} required={required} type={type} defaultValue={defaultValue} placeholder={placeholder} min={min} step={step} />}</Field>
}
