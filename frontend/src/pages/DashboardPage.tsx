import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, CircleDollarSign, Clock3, FileCheck2, Layers3, Plus, ReceiptText, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageTitle } from '../components/PageTitle'
import { Empty, Status, TableFrame } from '../components/Shared'
import { money, request, dateLabel } from '../services/api'
import type { Dashboard } from '../types'

export function DashboardPage() {
  const query = useQuery({ queryKey: ['dashboard'], queryFn: () => request<Dashboard>('/dashboard') })
  const data = query.data
  return <>
    <PageTitle title="Procurement overview" subtitle="A clear view of commitments, invoices, and cash moving through the process." action={<Link className="button button-primary" to="/requisitions"><Plus size={16} /> New requisition</Link>} />
    {query.isError && <div className="error-notice">Couldn’t load the live workspace. Check that the API is running, then refresh.</div>}
    <section className="metrics-grid" aria-label="Key procurement metrics">
      <Metric label="Outstanding balance" value={data ? money(data.metrics.outstanding_paise) : '—'} change={data?.metrics.overdue_paise ? `${money(data.metrics.overdue_paise)} overdue` : 'No overdue balance'} icon={CircleDollarSign} tone="teal" />
      <Metric label="Open purchase orders" value={data?.metrics.open_purchase_orders.toString() ?? '—'} change="Awaiting completion" icon={Layers3} tone="blue" />
      <Metric label="Pending approvals" value={data?.metrics.pending_approvals.toString() ?? '—'} change="Invoices ready for review" icon={Clock3} tone="amber" />
      <Metric label="Open exceptions" value={data?.metrics.open_exceptions.toString() ?? '—'} change="Need investigation" icon={AlertTriangle} tone="rose" />
    </section>
    <section className="overview-grid">
      <article className="panel spend-panel">
        <div className="panel-heading"><div><h2>Invoice spend</h2><p>Recorded invoice totals · INR</p></div><span className="period-label">Last 6 months</span></div>
        {data && data.monthly_spend.some(x => x.amount_paise) ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.monthly_spend} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke="#edf1f3" /><XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#87949a', fontSize: 11 }} dy={10} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#87949a', fontSize: 11 }} tickFormatter={v => `₹${Math.round(v / 100000) / 10}L`} />
          <Tooltip formatter={(v) => [money(Number(v)), 'Invoice spend']} contentStyle={{ border: '1px solid #e5eaec', borderRadius: 10, fontSize: 12 }} />
          <Line type="monotone" dataKey="amount_paise" stroke="#157f78" strokeWidth={2.5} dot={{ r: 3, fill: '#157f78', strokeWidth: 0 }} activeDot={{ r: 5 }} />
        </LineChart></ResponsiveContainer></div> : <Empty title="No invoice activity in this period" detail="Invoice totals will appear here when records are added." />}
        <div className="chart-foot"><span><i className="legend-dot" />Invoices recorded</span><Link to="/reports">View reports <ArrowRight size={14} /></Link></div>
      </article>
      <article className="panel attention-panel"><div className="panel-heading"><div><h2>Needs attention</h2><p>Items with a pending next step</p></div><span className="attention-count">{(data?.metrics.open_exceptions ?? 0) + (data?.metrics.pending_approvals ?? 0)}</span></div>
        <Link className="attention-item" to="/exceptions"><span className="attention-icon attention-rose"><AlertTriangle size={17} /></span><span><strong>Invoice exceptions</strong><small>Investigate unmatched or out-of-tolerance items</small></span><b>{data?.metrics.open_exceptions ?? 0}</b></Link>
        <Link className="attention-item" to="/invoices?status=PENDING_APPROVAL"><span className="attention-icon attention-amber"><Clock3 size={17} /></span><span><strong>Pending invoice approval</strong><small>Matched invoices awaiting a decision</small></span><b>{data?.metrics.pending_approvals ?? 0}</b></Link>
        <Link className="attention-item" to="/reconciliation"><span className="attention-icon attention-blue"><ArrowDownRight size={17} /></span><span><strong>Overdue balance</strong><small>Approved invoices past their due date</small></span><b className="attention-money">{data ? money(data.metrics.overdue_paise) : '—'}</b></Link>
        <Link className="panel-link" to="/reconciliation">Open reconciliation <ArrowRight size={14} /></Link>
      </article>
    </section>
    <section className="panel recent-panel"><div className="panel-heading"><div><h2>Recent invoices</h2><p>Latest records across the accounts payable queue</p></div><Link className="text-link" to="/invoices">All invoices <ArrowRight size={14} /></Link></div>
      {data?.recent_invoices.length ? <TableFrame><table><thead><tr><th>Invoice</th><th>Supplier</th><th>PO reference</th><th>Due date</th><th>Status</th><th className="align-right">Amount</th></tr></thead><tbody>{data.recent_invoices.map(inv => <tr key={inv.id}><td><Link className="record-link" to={`/invoices?focus=${inv.id}`}>{inv.number}</Link></td><td>{inv.supplier_name}</td><td>{inv.po_number ?? '—'}</td><td>{dateLabel(inv.due_date)}</td><td><Status value={inv.status} /></td><td className="align-right amount">{money(inv.total_paise)}</td></tr>)}</tbody></table></TableFrame> : <Empty title="No invoices yet" detail="Create or import an invoice to see it in the AP queue." />}
    </section>
    <div className="dashboard-footnote"><span><UsersRound size={14} /> {data?.metrics.active_suppliers ?? '—'} active suppliers</span><span><ReceiptText size={14} /> All amounts shown in Indian rupees</span><span><FileCheck2 size={14} /> Fictional demonstration records</span><Link to="/suppliers">Manage suppliers <ArrowUpRight size={13} /></Link></div>
  </>
}

function Metric({ label, value, change, icon: Icon, tone }: { label: string; value: string; change: string; icon: typeof CircleDollarSign; tone: string }) {
  return <article className="metric"><div className={`metric-icon metric-${tone}`}><Icon size={18} strokeWidth={1.8} /></div><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{change}</span></article>
}
