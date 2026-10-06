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
  // Frame auto-height (Atomic Design samples)
  // ===========================================================================

  // Grows a same-origin iframe to its content, so a sample shows whole
  // instead of scrolling inside a box. The frame's min-height is the no-JS
  // size, so with JS it only ever grows. Height goes through el.style,
  // which our CSP allows. init covers a frame that loaded before Alpine.
  Alpine.data('frameAutoHeight', () => ({
    init() {
      if (this.$el.contentDocument?.readyState === 'complete') this.resize()
    },
    resize() {
      const doc = this.$el.contentDocument
      if (doc) this.$el.style.height = `${doc.documentElement.scrollHeight}px`
    },
  }))

  // ===========================================================================
  // Scroll a row to its selected item (Atomic Design levels, A11y switcher)
  // ===========================================================================

  // On a phone these rows scroll sideways, so a choice made further along
  // would load scrolled out of sight. Centres the selected item (a link
  // with aria-current="page", or the label of a checked input) within the
  // row by setting the row's own scrollLeft, so the page never scrolls.
  // Does nothing when the row doesn't overflow (md and up). Without JS the
  // row simply starts at the left.
  Alpine.data('scrollRowToSelected', () => ({
    init() {
      const row = this.$el
      if (row.scrollWidth <= row.clientWidth) return
      const selected = row.querySelector('[aria-current="page"], :checked')
      if (!selected) return
      const item = selected.closest('label') ?? selected
      const rowBox = row.getBoundingClientRect()
      const itemBox = item.getBoundingClientRect()
      row.scrollLeft +=
        itemBox.left - rowBox.left - (row.clientWidth - itemBox.width) / 2
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
