import { lazy, Suspense, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getSession } from './services/api'
import type { User } from './types'
import { Layout } from './components/Layout'
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const SuppliersPage = lazy(() => import('./pages/SuppliersPage').then(m => ({ default: m.SuppliersPage })))
const WorkflowPage = lazy(() => import('./pages/WorkflowPage').then(m => ({ default: m.WorkflowPage })))
const ReportsPage = lazy(() => import('./pages/ReportsPage').then(m => ({ default: m.ReportsPage })))

export default function App() {
  const [user, setUser] = useState<User | null>(() => getSession()?.user ?? null)
  return <Suspense fallback={<div className="loading-state">Opening workspace…</div>}><Routes><Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage onUser={setUser} />} /><Route path="*" element={user ? <Layout user={user} onUser={setUser} /> : <Navigate to="/login" replace />}>
    <Route index element={<DashboardPage />} /><Route path="suppliers" element={<SuppliersPage role={user?.role ?? 'viewer'} />} />
    <Route path="requisitions" element={<WorkflowPage kind="requisitions" role={user?.role ?? 'viewer'} />} /><Route path="purchase-orders" element={<WorkflowPage kind="purchase-orders" role={user?.role ?? 'viewer'} />} />
    <Route path="goods-receipts" element={<WorkflowPage kind="goods-receipts" role={user?.role ?? 'viewer'} />} /><Route path="invoices" element={<WorkflowPage kind="invoices" role={user?.role ?? 'viewer'} />} />
    <Route path="exceptions" element={<WorkflowPage kind="exceptions" role={user?.role ?? 'viewer'} />} /><Route path="payments" element={<WorkflowPage kind="payments" role={user?.role ?? 'viewer'} />} />
    <Route path="reconciliation" element={<WorkflowPage kind="reconciliation" role={user?.role ?? 'viewer'} />} /><Route path="reports" element={<ReportsPage />} />
  </Route></Routes></Suspense>
}
