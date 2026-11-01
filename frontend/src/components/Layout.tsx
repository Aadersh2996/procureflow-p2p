import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Activity, ArrowLeftRight, Boxes, Building2, ChevronDown, CircleDollarSign, ClipboardCheck, FileCheck2, FileText, LayoutDashboard, LogOut, Menu, ReceiptText, ShieldAlert, Truck, Users, X } from 'lucide-react'
import type { Role, User } from '../types'
import { saveSession, signIn } from '../services/api'

const links = [
  { label: 'Overview', path: '/', icon: LayoutDashboard, end: true },
  { label: 'Suppliers', path: '/suppliers', icon: Building2 },
  { label: 'Requisitions', path: '/requisitions', icon: FileText },
  { label: 'Purchase orders', path: '/purchase-orders', icon: ClipboardCheck },
  { label: 'Goods receipts', path: '/goods-receipts', icon: Boxes },
  { label: 'Invoices', path: '/invoices', icon: ReceiptText },
  { label: 'Exceptions', path: '/exceptions', icon: ShieldAlert },
  { label: 'Payments', path: '/payments', icon: CircleDollarSign },
  { label: 'Reconciliation', path: '/reconciliation', icon: ArrowLeftRight },
  { label: 'Reports & exports', path: '/reports', icon: Activity },
]
const titles: Record<string, string> = Object.fromEntries(links.map(x => [x.path, x.label]))
const roles: { id: Role; label: string }[] = [{ id: 'admin', label: 'Administrator' }, { id: 'requester', label: 'Requester' }, { id: 'procurement', label: 'Procurement' }, { id: 'receiving', label: 'Receiving' }, { id: 'ap', label: 'Accounts payable' }, { id: 'approver', label: 'Approver' }, { id: 'viewer', label: 'Read only' }]

export function Layout({ user, onUser }: { user: User; onUser: (user: User | null) => void }) {
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [roleError, setRoleError] = useState('')
  const location = useLocation(); const navigate = useNavigate()
  const title = titles[location.pathname] ?? 'Procurement workspace'
  async function switchRole(event: React.ChangeEvent<HTMLSelectElement>) {
    const role = event.target.value as Role
    if (role === user.role) return
    setSwitching(true)
    setRoleError('')
    try { const session = await signIn(role); saveSession(session); onUser(session.user) }
    catch (error) { setRoleError(error instanceof Error ? error.message : 'Role switch failed.') }
    finally { setSwitching(false) }
  }
  function signOut() { saveSession(null); onUser(null); navigate('/login') }
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Boxes size={19} /></div><div><strong>Procure<span>Flow</span></strong><small>FINANCE OPERATIONS</small></div><button className="icon-button sidebar-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{links.map(item => { const Icon = item.icon; return <NavLink key={item.path} to={item.path} end={item.end} className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`} onClick={() => setOpen(false)}><Icon size={17} strokeWidth={1.8} /><span>{item.label}</span>{item.label === 'Exceptions' && <i className="nav-dot" />}</NavLink> })}</nav>
      <div className="sidebar-foot"><div className="assurance-mark"><span><Truck size={16} /></span><div><strong>Every step connected</strong><small>Requisition to reconciliation</small></div></div><p>LOCAL DEMONSTRATION · FICTIONAL DATA</p></div>
    </aside>
    {open && <button className="scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <div className="main-column">
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="crumb"><span>Operations</span><span className="crumb-slash">/</span><strong>{title}</strong></div><div className="topbar-right"><span className="environment"><i /> DEMO ENVIRONMENT</span><div className="role-control"><Users size={15} /><select aria-label="Switch demo role" value={user.role} onChange={switchRole} disabled={switching}>{roles.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}</select><ChevronDown size={14} /></div>{roleError && <span role="alert" className="role-error">{roleError}</span>}<div className="avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</div><button className="icon-button signout" aria-label="Sign out" title="Sign out" onClick={signOut}><LogOut size={17} /></button></div></header>
      <main id="main-content" className="page"><Outlet /></main>
      <footer className="app-footer"><span>ProcureFlow · P2P simulation</span><span><FileCheck2 size={13} /> Local data workspace</span></footer>
    </div>
  </div>
}
