/**
 * TypeScript type definitions for Alpine components
 *
 * Define interfaces for your Alpine components here
 */

import type { AlpineInstance } from './alpinejs'

/**
 * Base interface for Alpine component data
 * Extend this for your specific components
 */
export interface AlpineComponent {
  init?(): void
  destroy?(): void
}

/**
 * Example: Dropdown component interface
 */
export interface DropdownComponent extends AlpineComponent {
  open: boolean
  toggle(): void
  close(): void
}

declare global {
  interface Window {
    Alpine: AlpineInstance
  }
}
