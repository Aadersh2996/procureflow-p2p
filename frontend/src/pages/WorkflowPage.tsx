import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CircleDot, FilePlus2, RefreshCw, Search, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { ErrorNotice, Field, FieldInput, Form, Modal, Status, TableFrame } from '../components/Shared'
import { request, send, money, dateLabel } from '../services/api'
import type { Exception, Invoice, Payment, PurchaseOrder, Receipt, Reconciliation, Requisition, Role, Supplier } from '../types'
import { PageTitle } from '../components/PageTitle'

type Kind = 'requisitions' | 'purchase-orders' | 'goods-receipts' | 'invoices' | 'exceptions' | 'payments' | 'reconciliation'
type WorkflowRecord = Requisition | PurchaseOrder | Receipt | Invoice | Exception | Payment | Reconciliation
const EMPTY_RECORDS: WorkflowRecord[] = []
const TODAY = new Date()
const TODAY_ISO = TODAY.toISOString().slice(0, 10)
const DUE_DATE_ISO = new Date(TODAY.getTime() + 30 * 86400000).toISOString().slice(0, 10)
const copy: Record<Kind, { title: string; subtitle: string; endpoint: string; create?: string }> = {
  requisitions: { title: 'Requisitions', subtitle: 'Capture business needs and route them for approval before a purchase order is raised.', endpoint: '/requisitions', create: 'New requisition' },
  'purchase-orders': { title: 'Purchase orders', subtitle: 'Manage supplier commitments and monitor open, received, and completed orders.', endpoint: '/purchase-orders', create: 'Create purchase order' },
  'goods-receipts': { title: 'Goods receipts', subtitle: 'Record delivered quantities against purchase order lines and capture accepted quantities.', endpoint: '/goods-receipts', create: 'Record receipt' },
  invoices: { title: 'Invoices', subtitle: 'Review supplier invoices, matching results, approvals, and open balances.', endpoint: '/invoices', create: 'Record invoice' },
  exceptions: { title: 'Invoice exceptions', subtitle: 'Investigate matching discrepancies and retain a resolution trail.', endpoint: '/exceptions' },
  payments: { title: 'Payments', subtitle: 'Review disbursements recorded against approved supplier invoices.', endpoint: '/payments', create: 'Record payment' },
  reconciliation: { title: 'Reconciliation', subtitle: 'Tie invoice totals to recorded payments and identify each open balance.', endpoint: '/reports/reconciliation' },
}
const createRoles: Partial<Record<Kind, Role[]>> = {
  requisitions: ['requester', 'procurement'], 'purchase-orders': ['procurement'], 'goods-receipts': ['receiving'], invoices: ['ap'], payments: ['ap'],
}

export function WorkflowPage({ kind, role }: { kind: Kind; role: Role }) {
  const config = copy[kind]; const cache = useQueryClient(); const [searchParams] = useSearchParams()
  const [search, setSearch] = useState(''); const [modal, setModal] = useState(false); const [selected, setSelected] = useState<Invoice | Exception | null>(null); const [invoiceEditing, setInvoiceEditing] = useState(false); const [error, setError] = useState('');
  const query = useQuery({ queryKey: [kind], queryFn: () => request<WorkflowRecord[]>(config.endpoint + (kind === 'invoices' && searchParams.has('status') ? `?status=${encodeURIComponent(searchParams.get('status')!)}` : '')) })
  const suppliers = useQuery({ queryKey: ['suppliers'], queryFn: () => request<Supplier[]>('/suppliers') })
  const orders = useQuery({ queryKey: ['purchase-orders'], queryFn: () => request<PurchaseOrder[]>('/purchase-orders') })
  const requisitions = useQuery({ queryKey: ['requisitions'], queryFn: () => request<Requisition[]>('/requisitions') })
  const invoices = useQuery({ queryKey: ['invoices'], queryFn: () => request<Invoice[]>('/invoices') })
  const all = query.data ?? EMPTY_RECORDS
  const isAdmin = role === 'admin'
  const canCreate = isAdmin || (createRoles[kind]?.includes(role) ?? false)
  const canApprove = isAdmin || role === 'approver'
  const canMatch = isAdmin || role === 'ap' || role === 'approver'
  const canResolve = canMatch
  const canCorrect = isAdmin || role === 'ap'
  const formQueries = kind === 'purchase-orders' ? [suppliers, requisitions] : kind === 'goods-receipts' ? [orders] : kind === 'invoices' ? [suppliers, orders] : kind === 'payments' ? [invoices] : []
  const formQueryError = canCreate ? formQueries.find(x => x.isError) : undefined
  const rows = useMemo(() => all.filter(row => JSON.stringify(row).toLowerCase().includes(search.toLowerCase())), [all, search])
  const create = useMutation({ mutationFn: (body: unknown) => send(config.endpoint, body), onSuccess: () => { cache.invalidateQueries(); setModal(false); setError('') }, onError: e => setError(e.message) })
  const action = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => body === undefined ? request(path, { method: 'POST' }) : send(path, body), onSuccess: () => { cache.invalidateQueries(); setSelected(null); setError('') }, onError: e => setError(e.message) })
  const correction = useMutation({ mutationFn: ({ id, body }: { id: number; body: unknown }) => send(`/invoices/${id}`, body, 'PATCH'), onSuccess: () => { cache.invalidateQueries(); setSelected(null); setInvoiceEditing(false); setError('') }, onError: e => setError(e.message) })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const v = Object.fromEntries(form.entries());
    const line = { description: String(v.description ?? ''), quantity: String(v.quantity ?? '1'), unit_price_paise: Math.round(Number(v.unit_price_rupees ?? 0) * 100), tax_rate_bps: Number(v.tax_rate_bps ?? 1800), purchase_order_line_id: v.purchase_order_line_id ? Number(v.purchase_order_line_id) : undefined }
    if (kind === 'requisitions') create.mutate({ requester: v.requester, department: v.department, description: v.need_description, lines: [line] })
    if (kind === 'purchase-orders') create.mutate({ supplier_id: Number(v.supplier_id), requisition_id: v.requisition_id ? Number(v.requisition_id) : null, expected_on: v.expected_on || null, lines: [line] })
    if (kind === 'goods-receipts') create.mutate({ purchase_order_id: Number(v.purchase_order_id), received_by: v.received_by, received_on: v.received_on, lines: [{ purchase_order_line_id: Number(v.purchase_order_line_id), received_quantity: String(v.received_quantity), accepted_quantity: String(v.accepted_quantity) }] })
    if (kind === 'invoices') create.mutate({ number: v.number, supplier_id: Number(v.supplier_id), purchase_order_id: v.purchase_order_id ? Number(v.purchase_order_id) : null,
      invoice_date: v.invoice_date, due_date: v.due_date, matching_mode: v.matching_mode, reported_tax_paise: String(v.tax_rupees ?? '').trim() === '' ? undefined : Math.round(Number(v.tax_rupees) * 100), lines: [line] })
    if (kind === 'payments') create.mutate({ invoice_id: Number(v.invoice_id), amount_paise: Math.round(Number(v.amount_rupees) * 100), paid_on: v.paid_on, method: v.method, note: v.note })
  }
  function submitInvoiceCorrection(event: FormEvent<HTMLFormElement>, invoice: Invoice) {
    event.preventDefault(); const v = Object.fromEntries(new FormData(event.currentTarget).entries())
    const line = { description: String(v.description), quantity: String(v.quantity), unit_price_paise: Math.round(Number(v.unit_price_rupees) * 100),
      tax_rate_bps: Number(v.tax_rate_bps), purchase_order_line_id: v.purchase_order_line_id ? Number(v.purchase_order_line_id) : null }
    correction.mutate({ id: invoice.id, body: { purchase_order_id: v.purchase_order_id ? Number(v.purchase_order_id) : null, invoice_date: v.invoice_date,
      due_date: v.due_date, matching_mode: v.matching_mode, reported_tax_paise: String(v.tax_rupees ?? '').trim() === '' ? null : Math.round(Number(v.tax_rupees) * 100), lines: [line] } })
  }

  function renderRows() {
    if (kind === 'requisitions') return (rows as Requisition[]).map(r => <tr key={r.id}><td className="record-link">{r.number}</td><td>{r.requester}<small className="sub-cell">{r.department}</small></td><td>{r.description}</td><td>{dateLabel(r.requested_at)}</td><td><Status value={r.status} /></td><td className="align-right">{r.status === 'SUBMITTED' && canApprove && <><button className="button button-text" onClick={() => action.mutate({ path: `/requisitions/${r.id}/decision`, body: { decision: 'APPROVED' } })}>Approve</button><button className="button button-text text-danger" onClick={() => action.mutate({ path: `/requisitions/${r.id}/decision`, body: { decision: 'REJECTED' } })}>Reject</button></>}</td></tr>)
    if (kind === 'purchase-orders') return (rows as PurchaseOrder[]).map(p => <tr key={p.id}><td className="record-link">{p.number}</td><td>{p.supplier_name}</td><td>{p.requisition_id ? `REQ #${p.requisition_id}` : '—'}</td><td>{p.expected_on ? dateLabel(p.expected_on) : '—'}</td><td><Status value={p.status} /></td><td className="align-right amount">{money(p.subtotal_paise)}</td><td className="align-right">{p.status === 'DRAFT' && canApprove && <button className="button button-text" onClick={() => action.mutate({ path: `/purchase-orders/${p.id}/approve` })}>Release order</button>}</td></tr>)
    if (kind === 'goods-receipts') return (rows as Receipt[]).map(r => <tr key={r.id}><td className="record-link">{r.number}</td><td>{r.po_number}</td><td>{dateLabel(r.received_on)}</td><td>{r.received_by}</td><td>{r.lines.map(l => `${(l.received_quantity_milli / 1000).toFixed(3)} received · ${(l.accepted_quantity_milli / 1000).toFixed(3)} accepted`).join(', ')}</td><td><Status value={r.status} /></td></tr>)
    if (kind === 'invoices') return (rows as Invoice[]).map(i => <tr key={i.id}><td><button className="record-link plain-link" onClick={() => setSelected(i)}>{i.number}</button><small className="sub-cell">{i.matching_mode.replace('_', ' ')} match</small></td><td>{i.supplier_name}</td><td>{i.po_number ?? 'No PO'}</td><td>{dateLabel(i.due_date)}</td><td><Status value={i.match_outcome} /></td><td><Status value={i.status} /></td><td className="align-right amount">{money(i.total_paise)}</td><td className="align-right action-cell">{canMatch && i.status !== 'PAID' && i.status !== 'REJECTED' && <><button className="icon-button" aria-label={`Run match for ${i.number}`} title="Run match" onClick={() => action.mutate({ path: `/invoices/${i.id}/match` })}><RefreshCw size={15} /></button>{canApprove && i.status === 'PENDING_APPROVAL' && <button className="button button-text" onClick={() => action.mutate({ path: `/invoices/${i.id}/decision`, body: { decision: 'APPROVED' } })}>Approve</button>}</>}</td></tr>)
    if (kind === 'exceptions') return (rows as Exception[]).map(x => <tr key={x.id}><td className="record-link">{x.invoice_number}</td><td><span className="category-tag">{x.category.replaceAll('_', ' ')}</span></td><td className="description-cell">{x.description}</td><td><Status value={x.status} /></td><td className="align-right">{x.status === 'OPEN' && canResolve && <button className="button button-text" onClick={() => setSelected(x)}>Resolve</button>}</td></tr>)
    if (kind === 'payments') return (rows as Payment[]).map(p => <tr key={p.id}><td className="record-link">{p.reference}</td><td>{p.invoice_number}</td><td>{p.supplier_name}</td><td>{dateLabel(p.paid_on)}</td><td>{p.method}</td><td className="align-right amount">{money(p.amount_paise)}</td></tr>)
    return (rows as Reconciliation[]).map(r => <tr key={r.invoice_id}><td className="record-link">{r.invoice_number}</td><td>{r.supplier}</td><td>{dateLabel(r.due_date)}</td><td><Status value={r.status} /></td><td className="align-right amount">{money(r.invoice_total_paise)}</td><td className="align-right amount">{money(r.paid_paise)}</td><td className={`align-right amount ${r.open_balance_paise ? 'balance-open' : ''}`}>{money(r.open_balance_paise)}</td></tr>)
  }

  const headings: Record<Kind, string[]> = {
    requisitions: ['Requisition', 'Requested by', 'Business need', 'Submitted', 'Status', ''],
    'purchase-orders': ['Purchase order', 'Supplier', 'Source request', 'Expected', 'Status', 'Order value', ''],
    'goods-receipts': ['Receipt', 'PO reference', 'Received', 'Recorded by', 'Accepted quantities', 'Status'],
    invoices: ['Invoice', 'Supplier', 'PO reference', 'Due date', 'Match outcome', 'Workflow', 'Invoice total', ''],
    exceptions: ['Invoice', 'Category', 'Issue', 'Status', ''], payments: ['Payment reference', 'Invoice', 'Supplier', 'Paid on', 'Method', 'Amount'],
    reconciliation: ['Invoice', 'Supplier', 'Due date', 'Workflow', 'Invoice total', 'Paid', 'Open balance'],
  }
  return <>
    <PageTitle title={config.title} subtitle={config.subtitle} action={config.create && canCreate && <button className="button button-primary" disabled={formQueries.some(x => x.isLoading || x.isError)} onClick={() => { setError(''); setModal(true) }}><FilePlus2 size={16} /> {config.create}</button>} />
    {error && <ErrorNotice message={error} />}
    {formQueryError && <><ErrorNotice message={formQueryError.error instanceof Error ? formQueryError.error.message : 'Form data could not be loaded.'} /><button className="button button-secondary button-small" onClick={() => { for (const item of formQueries) void item.refetch() }}>Retry loading form data</button></>}
    <section className="panel list-panel"><div className="list-toolbar"><label className="search-box"><Search size={16} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder={`Search ${config.title.toLowerCase()}`} aria-label={`Search ${config.title}`} /></label><span className="result-count">{rows.length} records</span></div>
      {query.isLoading ? <div className="loading-state">Loading {config.title.toLowerCase()}…</div> : query.isError ? <ErrorNotice message={query.error instanceof Error ? query.error.message : 'Records could not be loaded.'} /> : <TableFrame><table><thead><tr>{headings[kind].map((x, i) => <th key={`${x}${i}`} className={i === headings[kind].length - 1 ? 'align-right' : ''}>{x}</th>)}</tr></thead><tbody>{renderRows()}</tbody></table>{rows.length === 0 && <div className="empty-inline"><CircleDot size={19} /><span>No records found. {config.create && canCreate ? 'Use the action above to get started.' : 'Check back after the related workflow is used.'}</span></div>}</TableFrame>}
      {query.isError && <button className="button button-secondary button-small" onClick={() => query.refetch()}>Retry loading records</button>}
      <div className="panel-foot">Showing live records from the local procurement database.</div>
    </section>
    {modal && <Modal title={config.create ?? 'Create record'} close={() => setModal(false)} wide={kind === 'invoices'}><Form onSubmit={submit} busy={create.isPending} submitLabel={config.create ?? 'Save record'}>
      {kind === 'requisitions' && <><FieldInput label="Requested by" name="requester" defaultValue="Aarav Mehta" /><FieldInput label="Department" name="department" options={['Finance', 'Operations', 'Information Technology', 'Facilities', 'Human Resources'].map(x => ({ value: x, label: x }))} /><FieldInput label="Business need" name="need_description" /><LineFields /></>}
      {kind === 'purchase-orders' && <><FieldInput label="Supplier" name="supplier_id" options={(suppliers.data ?? []).filter(x => x.active).map(s => ({ value: s.id, label: `${s.name} · ${s.code}` }))} /><FieldInput label="Approved requisition" name="requisition_id" required={false} options={[{ value: '', label: 'Direct purchase order' }, ...(requisitions.data ?? []).filter(x => x.status === 'APPROVED').map(x => ({ value: x.id, label: `${x.number} · ${x.department}` }))]} /><FieldInput label="Expected delivery" name="expected_on" required={false} type="date" /><LineFields /></>}
      {kind === 'goods-receipts' && <><FieldInput label="Received by" name="received_by" defaultValue="Receiving team" /><FieldInput label="Receipt date" name="received_on" type="date" defaultValue={TODAY_ISO} /><ReceiptLineSelector orders={orders.data ?? []} /></>}
      {kind === 'invoices' && <><InvoiceSourceSelector suppliers={suppliers.data ?? []} orders={orders.data ?? []} /><FieldInput label="Supplier invoice number" name="number" /><FieldInput label="Matching method" name="matching_mode" options={[{ value: 'THREE_WAY', label: 'Three way · PO, receipt, invoice' }, { value: 'TWO_WAY', label: 'Two way · PO and invoice' }]} /><div className="form-row"><FieldInput label="Invoice date" name="invoice_date" type="date" defaultValue={TODAY_ISO} /><FieldInput label="Due date" name="due_date" type="date" defaultValue={DUE_DATE_ISO} /></div><div className="form-row"><FieldInput label="Line description" name="description" /><FieldInput label="Quantity" name="quantity" type="number" min="0.001" step="0.001" defaultValue="1" /></div><div className="form-row"><FieldInput label="Unit price (₹)" name="unit_price_rupees" type="number" min="0.01" step="0.01" /><FieldInput label="GST rate" name="tax_rate_bps" options={[{ value: 0, label: '0%' }, { value: 500, label: '5%' }, { value: 1200, label: '12%' }, { value: 1800, label: '18%' }, { value: 2800, label: '28%' }]} /></div><FieldInput label="Invoice GST amount (₹)" name="tax_rupees" type="number" min="0" step="0.01" required={false} /></>}
      {kind === 'payments' && <><FieldInput label="Approved invoice" name="invoice_id" options={(invoices.data ?? []).filter(x => ['APPROVED', 'PARTIALLY_PAID'].includes(x.status) && x.balance_paise > 0).map(x => ({ value: x.id, label: `${x.number} · ${x.supplier_name} · balance ${money(x.balance_paise)}` }))} /><FieldInput label="Payment amount (₹)" name="amount_rupees" type="number" min="0.01" step="0.01" /><FieldInput label="Paid on" name="paid_on" type="date" defaultValue={TODAY_ISO} /><FieldInput label="Payment method" name="method" options={['NEFT', 'RTGS', 'IMPS', 'UPI', 'Cheque'].map(x => ({ value: x, label: x }))} /><FieldInput label="Note" name="note" required={false} /></>}
      {error && <ErrorNotice message={error} />}
    </Form></Modal>}
    {isInvoice(selected) && <Modal title={invoiceEditing ? `Correct ${selected.number}` : `Invoice ${selected.number}`} close={() => { setSelected(null); setInvoiceEditing(false) }} wide>{invoiceEditing ? <InvoiceCorrectionForm invoice={selected} orders={orders.data ?? []} busy={correction.isPending} error={correction.error?.message ?? ''} onSubmit={e => submitInvoiceCorrection(e, selected)} /> : <div className="invoice-detail"><div className="detail-grid"><Detail label="Supplier" value={selected.supplier_name} /><Detail label="Purchase order" value={selected.po_number ?? 'No PO linked'} /><Detail label="Match result" value={selected.match_outcome} /><Detail label="Workflow" value={selected.status} /><Detail label="Invoice total" value={money(selected.total_paise)} /><Detail label="Open balance" value={money(selected.balance_paise)} /></div><h3>Invoice lines</h3><div className="detail-line-list">{selected.lines.map((l,i) => <div key={l.id ?? i}><span>{l.description}<small>{(l.quantity_milli/1000).toFixed(3)} units × {money(l.unit_price_paise)}</small></span><b>{money((l.subtotal_paise ?? 0)+(l.tax_paise ?? 0))}</b></div>)}</div>
        <div className="detail-actions">{canCorrect && ['EXCEPTION', 'PENDING_APPROVAL'].includes(selected.status) && <button className="button button-secondary" onClick={() => setInvoiceEditing(true)}>Correct details</button>}{canMatch && <button className="button button-secondary" onClick={() => action.mutate({ path: `/invoices/${selected.id}/match` })}><RefreshCw size={15} /> Run matching</button>}{canApprove && selected.status === 'PENDING_APPROVAL' && <><button className="button button-secondary" onClick={() => action.mutate({ path: `/invoices/${selected.id}/decision`, body: { decision: 'REJECTED', comment: 'Rejected during review' } })}><X size={15} /> Reject</button><button className="button button-primary" onClick={() => action.mutate({ path: `/invoices/${selected.id}/decision`, body: { decision: 'APPROVED', comment: 'Approved after review' } })}><Check size={15} /> Approve invoice</button></>}</div>{error && <ErrorNotice message={error} />}</div>}</Modal>}
    {selected && kind === 'exceptions' && <Modal title={`Resolve ${'category' in selected ? selected.category.replaceAll('_', ' ').toLowerCase() : 'exception'}`} close={() => setSelected(null)}><Form onSubmit={e => { e.preventDefault(); const val = new FormData(e.currentTarget).get('resolution'); action.mutate({ path: `/exceptions/${selected.id}/resolve`, body: { resolution: val } }) }} busy={action.isPending} submitLabel="Record resolution"><p className="modal-description">{(selected as Exception).description}</p><Field label="Resolution note"><textarea name="resolution" required minLength={3} rows={4} placeholder="Explain what was checked and how the exception was resolved." /></Field>{error && <ErrorNotice message={error} />}</Form></Modal>}
  </>
}

function LineFields() { return <><div className="form-divider">Order line</div><FieldInput label="Item or service description" name="description" /><div className="form-row"><FieldInput label="Quantity" name="quantity" type="number" min="0.001" step="0.001" defaultValue="1" /><FieldInput label="Unit price (₹)" name="unit_price_rupees" type="number" min="0.01" step="0.01" /></div><FieldInput label="GST rate" name="tax_rate_bps" options={[{ value: 0, label: '0%' }, { value: 500, label: '5%' }, { value: 1200, label: '12%' }, { value: 1800, label: '18%' }, { value: 2800, label: '28%' }]} /></> }
function InvoiceCorrectionForm({ invoice, orders, busy, error, onSubmit }: { invoice: Invoice; orders: PurchaseOrder[]; busy: boolean; error: string; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const eligibleOrders = orders.filter(x => x.supplier_id === invoice.supplier_id && x.status !== 'DRAFT')
  const [poId, setPoId] = useState(invoice.purchase_order_id ?? 0)
  const order = eligibleOrders.find(x => x.id === poId)
  const [lineId, setLineId] = useState(invoice.lines[0]?.purchase_order_line_id ?? order?.lines[0]?.id ?? 0)
  const activeLineId = order && order.lines.some(x => x.id === lineId) ? lineId : order?.lines[0]?.id ?? 0
  const line = invoice.lines[0]
  return <Form onSubmit={onSubmit} busy={busy} submitLabel="Correct and re-match">
    <p className="modal-description">Correct the source invoice values, then the system recalculates tax and runs matching again.</p>
    <Field label="Purchase order"><select name="purchase_order_id" value={poId || ''} onChange={e => { const value = Number(e.target.value); setPoId(value); setLineId(eligibleOrders.find(x => x.id === value)?.lines[0]?.id ?? 0) }}><option value="">No purchase order</option>{eligibleOrders.map(x => <option key={x.id} value={x.id}>{x.number} · {x.status}</option>)}</select></Field>
    {order && <Field label="Purchase order line"><select name="purchase_order_line_id" value={activeLineId || ''} onChange={e => setLineId(Number(e.target.value))}>{order.lines.map(x => <option key={x.id} value={x.id}>{x.description} · {money(x.unit_price_paise)} per unit</option>)}</select></Field>}
    <FieldInput label="Matching method" name="matching_mode" defaultValue={invoice.matching_mode} options={[{ value: 'THREE_WAY', label: 'Three way · PO, receipt, invoice' }, { value: 'TWO_WAY', label: 'Two way · PO and invoice' }]} />
    <div className="form-row"><FieldInput label="Invoice date" name="invoice_date" type="date" defaultValue={invoice.invoice_date} /><FieldInput label="Due date" name="due_date" type="date" defaultValue={invoice.due_date} /></div>
    <FieldInput label="Invoice line description" name="description" defaultValue={line?.description ?? ''} />
    <div className="form-row"><FieldInput label="Quantity" name="quantity" type="number" min="0.001" step="0.001" defaultValue={line ? (line.quantity_milli / 1000).toFixed(3) : '1'} /><FieldInput label="Unit price (₹)" name="unit_price_rupees" type="number" min="0.01" step="0.01" defaultValue={line ? (line.unit_price_paise / 100).toFixed(2) : ''} /></div>
    <div className="form-row"><FieldInput label="GST rate" name="tax_rate_bps" defaultValue={line?.tax_rate_bps ?? 1800} options={[{ value: 0, label: '0%' }, { value: 500, label: '5%' }, { value: 1200, label: '12%' }, { value: 1800, label: '18%' }, { value: 2800, label: '28%' }]} /><FieldInput label="Reported GST amount (₹)" name="tax_rupees" type="number" min="0" step="0.01" required={false} hint="Leave blank to recalculate GST from the line rate." /></div>
    {error && <ErrorNotice message={error} />}
  </Form>
}
function InvoiceSourceSelector({ suppliers, orders }: { suppliers: Supplier[]; orders: PurchaseOrder[] }) {
  const activeSuppliers = suppliers.filter(x => x.active)
  const [supplierId, setSupplierId] = useState(activeSuppliers[0]?.id ?? 0)
  const currentSupplierId = activeSuppliers.some(x => x.id === supplierId) ? supplierId : activeSuppliers[0]?.id ?? 0
  const matchingOrders = orders.filter(x => x.supplier_id === currentSupplierId && x.status !== 'DRAFT')
  const [poId, setPoId] = useState(matchingOrders[0]?.id ?? 0)
  const currentPoId = matchingOrders.some(x => x.id === poId) ? poId : matchingOrders[0]?.id ?? 0
  const currentOrder = matchingOrders.find(x => x.id === currentPoId)
  function changeSupplier(value: number) { setSupplierId(value); setPoId(orders.find(x => x.supplier_id === value && x.status !== 'DRAFT')?.id ?? 0) }
  return <><Field label="Supplier"><select name="supplier_id" required value={currentSupplierId} onChange={e => changeSupplier(Number(e.target.value))}>{activeSuppliers.map(s => <option key={s.id} value={s.id}>{s.name} · {s.code}</option>)}</select></Field>
    <Field label="Purchase order"><select name="purchase_order_id" value={currentPoId || ''} onChange={e => setPoId(Number(e.target.value))}><option value="">No purchase order</option>{matchingOrders.map(x => <option key={x.id} value={x.id}>{x.number}</option>)}</select></Field>
    {currentOrder && <Field label="Purchase order line"><select name="purchase_order_line_id" required>{currentOrder.lines.map(l => <option key={l.id} value={l.id}>{l.description} · {money(l.unit_price_paise)} per unit</option>)}</select></Field>}
  </>
}

function ReceiptLineSelector({ orders }: { orders: PurchaseOrder[] }) { const [poId, setPoId] = useState(orders.find(o => ['OPEN','PARTIALLY_RECEIVED'].includes(o.status))?.id ?? 0); const order = orders.find(o => o.id === poId); return <><Field label="Purchase order"><select name="purchase_order_id" required value={poId} onChange={e => setPoId(Number(e.target.value))}>{orders.filter(o => ['OPEN','PARTIALLY_RECEIVED'].includes(o.status)).map(o => <option key={o.id} value={o.id}>{o.number} · {o.supplier_name}</option>)}</select></Field><Field label="Purchase order line"><select name="purchase_order_line_id" required>{order?.lines.map(l => <option key={l.id} value={l.id}>{l.description} · ordered {(l.quantity_milli/1000).toFixed(3)}</option>)}</select></Field><div className="form-row"><FieldInput label="Quantity received" name="received_quantity" type="number" min="0.001" step="0.001" /><FieldInput label="Quantity accepted" name="accepted_quantity" type="number" min="0" step="0.001" /></div></> }
function Detail({ label, value }: { label: string; value: string }) { return <div className="detail-field"><small>{label}</small><strong>{value}</strong></div> }
function isInvoice(value: Invoice | Exception | null): value is Invoice { return value !== null && 'number' in value && 'lines' in value }
