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
    isLoading: false,
    timeline: [],

    async openMenu() {
      this.menuOpen = true
      this.isLoading = true
      try {
        const response = await fetch('/api/chat/case/')
        if (response.ok) {
          const data = await response.json()
          this.timeline = (data.timeline || []).map((e) => ({
            id: e.id,
            type: e.event_type,
            timestamp: e.created_at,
            title: e.title,
            content: e.content,
            metadata: e.metadata,
          }))
        }
      } catch (e) {
        console.error('Failed to load timeline:', e)
      } finally {
        this.isLoading = false
      }
    },
    closeMenu() {
      this.menuOpen = false
    },

    async clearDemo() {
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
        console.error('Failed to clear demo:', e)
      }
      location.reload()
    },

    get isLoadingTimeline() {
      return this.isLoading
    },
    get notLoadingTimeline() {
      return !this.isLoading
    },
    get hasTimeline() {
      return !this.isLoading && this.timeline.length > 0
    },
    get noTimeline() {
      return !this.isLoading && this.timeline.length === 0
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
