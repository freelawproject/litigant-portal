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
  // Dev menu (header dropdown — visible in dev + QA only)
  // ===========================================================================

  Alpine.data('devMenu', () => ({
    open: false,
    toggle() {
      this.open = !this.open
    },
    close() {
      this.open = false
    },
    async resetDemo() {
      const csrfToken =
        document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        document.cookie
          .split(';')
          .find((c) => c.trim().startsWith('csrftoken='))
          ?.split('=')[1] ||
        ''
      const formData = new FormData()
      formData.append('csrfmiddlewaretoken', csrfToken)
      try {
        await fetch('/api/chat/case/clear/', { method: 'POST', body: formData })
      } catch (e) {
        console.error('Failed to reset demo:', e)
      }
      location.reload()
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
