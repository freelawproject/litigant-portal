/**
 * POC (#946): the docassemble interview in a slide-in panel on the Topic
 * Flow page, instead of a new tab.
 *
 * The packet form still POSTs to topic_flow_interview, which creates the
 * prefilled session and redirects. With JS on, the form targets the panel's
 * iframe instead of _blank, so that redirect lands in the panel. The panel
 * is a native <dialog>: showModal() gives focus containment, Escape to close,
 * and an inert page behind it without any custom focus trap.
 *
 * Closing only hides the dialog, so the iframe keeps its document and a
 * half-filled interview is still there when the litigant comes back.
 */
document.addEventListener('alpine:init', () => {
  // A horizontal swipe longer than this (px) counts as a gesture, not a tap.
  const SWIPE_DISTANCE = 60

  Alpine.data('embeddedInterview', () => ({
    started: false,
    isOpen: false,
    touchStartX: null,

    get formTarget() {
      return 'da-interview-frame'
    },
    get isStarted() {
      return this.started
    },
    get isNotStarted() {
      return !this.started
    },
    get showsEdgeTab() {
      return this.started && !this.isOpen
    },

    // The form's submit handler: let the POST go to the iframe, then open.
    start() {
      this.started = true
      this.open()
    },
    open() {
      this.$refs.panel.showModal()
      this.isOpen = true
    },
    close() {
      this.$refs.panel.close()
    },
    // Fires however the dialog closed (button, Escape, swipe).
    closed() {
      this.isOpen = false
    },

    touchStart(event) {
      this.touchStartX = event.changedTouches[0].clientX
    },
    swipeDistance(event) {
      if (this.touchStartX === null) return 0
      const distance = event.changedTouches[0].clientX - this.touchStartX
      this.touchStartX = null
      return distance
    },
    // Swipe right on the panel header: back to reading the guide.
    panelTouchEnd(event) {
      if (this.swipeDistance(event) > SWIPE_DISTANCE) this.close()
    },
    // Swipe left on the edge tab: back into the interview.
    edgeTouchEnd(event) {
      if (this.swipeDistance(event) < -SWIPE_DISTANCE) this.open()
    },
  }))
})
