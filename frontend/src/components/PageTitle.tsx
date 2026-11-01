import type { ReactNode } from 'react'
export function PageTitle({ title, subtitle, action, eyebrow }: { title: string; subtitle: string; action?: ReactNode; eyebrow?: string }) {
  return <div className="page-title"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1><p>{subtitle}</p></div>{action && <div className="page-title-action">{action}</div>}</div>
}
