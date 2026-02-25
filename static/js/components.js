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
  // Activity timeline (header slide-out panel)
  // ===========================================================================

  Alpine.data('activityTimeline', () => ({
    menuOpen: false,
    timeline: [],

    openMenu() {
      this.timeline = JSON.parse(localStorage.getItem('caseTimeline') || '[]')
      this.menuOpen = true
    },
    closeMenu() {
      this.menuOpen = false
    },

    clearDemo() {
      localStorage.clear()
      location.reload()
    },

    get hasTimeline() {
      return this.timeline.length > 0
    },
    get noTimeline() {
      return this.timeline.length === 0
    },

    get reversedTimeline() {
      return this.timeline
        .slice()
        .reverse()
        .map((event) => ({
          ...event,
          borderClass:
            {
              upload: 'border-primary-300 bg-primary-50/50',
              summary: 'border-blue-300 bg-blue-50/50',
              change: 'border-greyscale-300 bg-greyscale-50',
            }[event.type] || 'border-greyscale-300 bg-greyscale-50',
          formattedDate: new Date(event.timestamp).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
          }),
          isUpload: event.type === 'upload',
          isSummary: event.type === 'summary',
          isChange: event.type === 'change',
        }))
    },
  }))

  // ===========================================================================
  // Timeline event card (nested inside activity timeline)
  // ===========================================================================

  Alpine.data('timelineEvent', () => ({
    expanded: false,
    toggle() {
      this.expanded = !this.expanded
    },
    get clampClass() {
      return this.expanded ? '' : 'line-clamp-2'
    },
  }))
})
