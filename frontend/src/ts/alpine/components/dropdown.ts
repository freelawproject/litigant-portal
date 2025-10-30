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

/**
 * Selectable Dropdown Alpine Component
 *
 * A dropdown that tracks selected value and displays it in the button.
 *
 * Usage in templates:
 * <div x-data="selectableDropdown({ options: ['Option 1', 'Option 2'], selected: 'Option 1' })">
 *   <button x-on:click="toggle" x-text="selected"></button>
 *   <div x-show="open">
 *     <template x-for="option in options">
 *       <button x-on:click="select(option)" x-text="option"></button>
 *     </template>
 *   </div>
 * </div>
 */
export interface SelectableDropdownComponent extends AlpineComponent {
  open: boolean
  selected: string
  options: string[]
  toggle(): void
  close(): void
  select(value: string): void
}

interface AlpineComponent {
  init?(): void
  destroy?(): void
}

Alpine.data(
  'selectableDropdown',
  ({
    options = [],
    selected = '',
  }: {
    options?: string[]
    selected?: string
  }): SelectableDropdownComponent => ({
    open: false,
    selected: selected || (options.length > 0 ? options[0] : ''),
    options,

    init() {
      console.log('Selectable dropdown initialized with:', this.options)
    },

    toggle() {
      this.open = !this.open
    },

    close() {
      this.open = false
    },

    select(value: string) {
      this.selected = value
      this.close()
      console.log('Selected:', value)
    },

    destroy() {
      console.log('Selectable dropdown destroyed')
    },
  }),
)
