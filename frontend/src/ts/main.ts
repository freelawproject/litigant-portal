/**
 * Main TypeScript entry point
 *
 * This file initializes AlpineJS and registers all components,
 * composables, and plugins following CSP-compliant patterns.
 *
 * IMPORTANT: No inline JavaScript allowed due to Content Security Policy.
 * All Alpine components must be registered via Alpine.data() in external files.
 */

import Alpine from 'alpinejs'

// Import Alpine plugins (if any)
// import intersect from '@alpinejs/intersect'
// Alpine.plugin(intersect)

// Import Alpine components
import './alpine/components/dropdown'
// Import more components as they are created

// Import Alpine composables (shared utilities)
// import './alpine/composables/useApi'

// Make Alpine available globally for debugging in development
if (import.meta.env.DEV) {
  window.Alpine = Alpine
}

// Start Alpine
Alpine.start()

// Export Alpine for type safety
export default Alpine
