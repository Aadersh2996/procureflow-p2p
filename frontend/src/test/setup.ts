import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks() })

if (typeof HTMLDialogElement !== 'undefined') {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.open = false; this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
}
