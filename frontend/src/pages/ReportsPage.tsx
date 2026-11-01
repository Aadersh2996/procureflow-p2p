import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Download, FileSpreadsheet, LineChart, PackageCheck, ReceiptText, RotateCw } from 'lucide-react'
import { PageTitle } from '../components/PageTitle'
import { ErrorNotice } from '../components/Shared'
import { downloadCsv, money, request } from '../services/api'

type Operations = { supplier_expenditure: { supplier: string; total_paise: number }[]; invoice_status: Record<string, number>; pending_approvals: number; outstanding_paise: number; overdue_invoices: { invoice_number: string; supplier: string; due_date: string; balance_paise: number }[]; invoice_count: number }
const reports = [
  { name: 'Supplier register', detail: 'Supplier master records and registration status', file: 'suppliers', icon: FileSpreadsheet },
  { name: 'Purchase orders', detail: 'Supplier commitments, terms, and order line values', file: 'purchase-orders', icon: PackageCheck },
  { name: 'Invoice register', detail: 'Invoices, matching outcomes, tax, and balances', file: 'invoices', icon: ReceiptText },
  { name: 'Matching exceptions', detail: 'Open and resolved discrepancies with notes', file: 'exceptions', icon: RotateCw },
  { name: 'Payment register', detail: 'Recorded payment references and amounts', file: 'payments', icon: FileSpreadsheet },
  { name: 'Reconciliation', detail: 'Invoice totals, cumulative payments, and open balances', file: 'reconciliation', icon: LineChart },
]
export function ReportsPage() {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [exportError, setExportError] = useState('')
  const query = new URLSearchParams()
  if (start) query.set('start', start)
  if (end) query.set('end', end)
  const suffix = query.size ? `?${query}` : ''
  const summary = useQuery({ queryKey: ['operations-report', start, end], queryFn: () => request<Operations>(`/reports/operations${suffix}`) })
  async function exportFile(file: string) { setExportError(''); try { await downloadCsv(`/export/${file}.csv`, `${file}.csv`) } catch (error) { setExportError(error instanceof Error ? error.message : 'CSV export failed.') } }
  return <><PageTitle title="Reports & exports" subtitle="Download current records and operational summaries from the live workspace." />
    {exportError && <ErrorNotice message={exportError} />}
    {summary.isError && <><ErrorNotice message={summary.error instanceof Error ? summary.error.message : 'The operational summary could not be loaded.'} /><button className="button button-secondary button-small" onClick={() => summary.refetch()}>Retry loading summary</button></>}
    <section className="panel report-filters" aria-label="Report date range"><label>From<input type="date" max={end || undefined} value={start} onChange={event => setStart(event.target.value)} /></label><label>Through<input type="date" min={start || undefined} value={end} onChange={event => setEnd(event.target.value)} /></label><button className="button button-text" onClick={() => { setStart(''); setEnd('') }}>Clear dates</button></section>
    <section className="report-summary"><article><small>Invoices in report</small><strong>{summary.data?.invoice_count ?? '—'}</strong></article><article><small>Outstanding approved balance</small><strong>{summary.data ? money(summary.data.outstanding_paise) : '—'}</strong></article><article><small>Pending approvals</small><strong>{summary.data?.pending_approvals ?? '—'}</strong></article><article><small>Overdue invoices</small><strong>{summary.data?.overdue_invoices.length ?? '—'}</strong></article></section>
    <section className="report-grid">{reports.map(report => { const Icon = report.icon; return <article className="report-row" key={report.file}><span className="report-icon"><Icon size={18} /></span><div><strong>{report.name}</strong><small>{report.detail}</small></div><button className="button button-secondary button-small" onClick={() => { void exportFile(report.file) }}><Download size={14} /> CSV</button></article> })}</section>
    <div className="report-columns"><article className="panel report-list"><div className="panel-heading"><div><h2>Supplier expenditure</h2><p>Sum of persisted invoice totals</p></div></div>{summary.isError ? null : summary.data?.supplier_expenditure.length ? summary.data.supplier_expenditure.slice(0, 6).map(x => <div className="report-metric-row" key={x.supplier}><span>{x.supplier}</span><strong>{money(x.total_paise)}</strong></div>) : <div className="report-empty">No supplier expenditure recorded.</div>}</article><article className="panel report-list"><div className="panel-heading"><div><h2>Invoice status</h2><p>Current record counts from the database</p></div></div>{!summary.isError && Object.entries(summary.data?.invoice_status ?? {}).map(([key, count]) => <div className="report-metric-row" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{count}</strong></div>)}</article></div>
    <div className="report-note"><strong>Data format</strong><span>Amounts in exports are integer paise. Divide by 100 to convert to Indian rupees. Dates use ISO format.</span></div>
    <div className="report-note"><strong>Security model</strong><span>Report data and exports require a signed local demo session. Role permissions control transaction actions.</span></div>
  </>
}
