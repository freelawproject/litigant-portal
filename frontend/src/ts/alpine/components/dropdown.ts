/**
 * Dropdown Alpine Component
 *
 * Example component showing CSP-compliant Alpine pattern.
 * Following CourtListener architecture: register components via Alpine.data()
 *
 * Usage in templates:
 * <div x-data="dropdown">
 *   <button x-on:click="toggle">Toggle</button>
 *   <div x-show="open">Content</div>
 * </div>
 */

import Alpine from 'alpinejs'
import type { DropdownComponent } from '../../types/alpine'

Alpine.data('dropdown', (): DropdownComponent => ({
  open: false,

  init() {
    // Initialization logic
    console.log('Dropdown component initialized')
  },

  toggle() {
    this.open = !this.open
  },

  close() {
    this.open = false
  },

  destroy() {
    // Cleanup logic
    console.log('Dropdown component destroyed')
  },
}))
