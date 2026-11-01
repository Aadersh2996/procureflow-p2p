import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { Empty, ErrorNotice, FieldInput, Form, Modal, Status, TableFrame } from './Shared'

describe('shared interface components', () => {
  it('renders a success status with a readable label', () => {
    render(<Status value="APPROVED" />)
    expect(screen.getByText('Approved')).toHaveClass('status-positive')
  })
  it('marks a financial exception as a negative status', () => {
    render(<Status value="PRICE_VARIANCE" />)
    expect(screen.getByText('Price Variance')).toHaveClass('status-negative')
  })
  it('exposes request failures to assistive technology', () => {
    render(<ErrorNotice message="Payment is above the remaining balance" />)
    expect(screen.getByRole('alert')).toHaveTextContent('remaining balance')
  })
  it('renders an accessible empty state', () => {
    render(<Empty title="No invoices" detail="Record an invoice to continue." />)
    expect(screen.getByText('No invoices')).toBeVisible()
    expect(screen.getByText('Record an invoice to continue.')).toBeVisible()
  })
  it('labels required fields and displays options', () => {
    render(<FieldInput label="GST rate" name="tax_rate_bps" options={[{ value: 1800, label: '18%' }]} />)
    expect(screen.getByLabelText('GST rate')).toHaveValue('1800')
    expect(screen.getByLabelText('GST rate')).toBeRequired()
  })
  it('allows optional inputs and applies numeric bounds', () => {
    render(<FieldInput label="Quantity" name="quantity" required={false} type="number" min="0.001" step="0.001" />)
    expect(screen.getByLabelText('Quantity')).not.toBeRequired()
    expect(screen.getByLabelText('Quantity')).toHaveAttribute('min', '0.001')
  })
  it('renders form errors and a disabled busy action', () => {
    render(<Form busy onSubmit={e => e.preventDefault()}><FieldInput label="Supplier name" name="name" /><ErrorNotice message="Fix the supplier name" /></Form>)
    expect(screen.getByRole('alert')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()
  })
  it('submits the form through the browser event', () => {
    const submit = vi.fn(e => e.preventDefault())
    render(<Form onSubmit={submit}><FieldInput label="Supplier name" name="name" /></Form>)
    fireEvent.submit(screen.getByRole('button', { name: 'Save record' }).closest('form')!)
    expect(submit).toHaveBeenCalledOnce()
  })
  it('shows a dialog and closes on the close button', () => {
    const close = vi.fn()
    render(<Modal title="Register supplier" close={close}><p>Supplier details</p></Modal>)
    expect(screen.getByRole('dialog', { name: 'Register supplier' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }))
    expect(close).toHaveBeenCalledOnce()
  })
  it('keeps transaction tables semantic', () => {
    render(<TableFrame><table><thead><tr><th>Invoice</th></tr></thead><tbody><tr><td>INV-001</td></tr></tbody></table></TableFrame>)
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByRole('columnheader', { name: 'Invoice' })).toBeVisible()
  })
})
