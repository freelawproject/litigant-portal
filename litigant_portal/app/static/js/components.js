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
  // Site frame drawer (#988)
  // ===========================================================================

  // Below xl each site frame region is a native popover, opened by a header
  // button with no JS. This adds what the popover doesn't do on its own: it
  // moves focus into the drawer when it opens, closes it when focus leaves
  // (so Tab can't land on the page hidden behind it, WCAG 2.4.11), closes it
  // when a link inside is followed, and closes it when the window widens to
  // xl, where the region shows inline instead.
  Alpine.data('frameDrawer', () => ({
    init() {
      this.wideQuery = window.matchMedia('(width >= 80rem)')
      this.closeWhenWide = () => {
        if (this.wideQuery.matches) this.close()
      }
      this.wideQuery.addEventListener('change', this.closeWhenWide)
    },
    destroy() {
      this.wideQuery.removeEventListener('change', this.closeWhenWide)
    },
    isOpen() {
      return (
        typeof this.$root.hidePopover === 'function' &&
        this.$root.matches(':popover-open')
      )
    },
    close() {
      if (this.isOpen()) this.$root.hidePopover()
    },
    onToggle(event) {
      if (event.newState === 'open') this.$root.focus()
    },
    onFocusOut(event) {
      const next = event.relatedTarget
      if (!this.isOpen() || !next || this.$root.contains(next)) return
      // Chrome focuses this drawer's header button on mousedown, before the
      // click toggles the popover: closing here would let that click reopen
      // it. Leave the toggle to the button.
      if (next.getAttribute('popovertarget') === this.$root.id) return
      this.close()
    },
    // A followed link keeps focus inside the drawer, so focusout never fires
    // and the drawer would stay open over the page it just navigated.
    // popovertarget only works on buttons, so links need this.
    onClick(event) {
      const link = event.target.closest('a[href]')
      if (!link) return
      this.close()
      // Hiding returns focus to the button that opened the drawer. For an
      // in-page link, put it on the section instead, where the reader went.
      const href = link.getAttribute('href')
      const section = href.startsWith('#')
        ? document.getElementById(href.slice(1))
        : null
      if (!section) return
      if (!section.hasAttribute('tabindex'))
        section.setAttribute('tabindex', '-1')
      section.focus()
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
