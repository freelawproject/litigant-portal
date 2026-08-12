/**
 * Alpine.js CSP-safe components
 *
 * All components use Alpine.data() with named registrations.
 * Directive values are dot-paths only (no expressions, ternaries, or inline JS).
 */
document.addEventListener('alpine:init', () => {
  // ===========================================================================
  // Auto-dismiss (toast notifications)
  // ===========================================================================

  Alpine.data('autoDismiss', () => ({
    show: true,
    dismiss() {
      this.show = false
    },
  }))

  // ===========================================================================
  // User menu dropdown
  // ===========================================================================

  Alpine.data('userMenu', () => ({
    open: false,
    toggle() {
      this.open = !this.open
    },
    close() {
      this.open = false
    },
  }))

  // ===========================================================================
  // Action plan page (print button)
  // ===========================================================================

  Alpine.data('actionPlanPage', () => ({
    printPage() {
      window.print()
    },
  }))
})
