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

  // ===========================================================================
  // Action plan page (print button)
  // ===========================================================================

  Alpine.data('actionPlanPage', () => ({
    printPage() {
      window.print()
    },
  }))

  // ===========================================================================
  // Admin users list (search + pagination)
  // ===========================================================================

  Alpine.data('adminUsers', () => ({
    query: '',
    page: 1,
    users: [],
    total: 0,
    pageCount: 1,
    pageSize: 25,
    hasNext: false,
    hasPrev: false,
    loading: false,
    loaded: false,
    searchTimer: null,

    init() {
      this.fetch()
    },

    onQueryInput(e) {
      this.query = e.target.value
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => {
        this.page = 1
        this.fetch()
      }, 250)
    },

    async fetch() {
      this.loading = true
      try {
        const url = this.$el.dataset.url || '/admin/users/data/'
        const params = new URLSearchParams({
          q: this.query,
          page: String(this.page),
        })
        const response = await fetch(`${url}?${params.toString()}`, {
          credentials: 'same-origin',
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) {
          console.error('Users fetch failed:', response.status)
          return
        }
        const data = await response.json()
        this.users = (data.users || []).map((u) => ({
          ...u,
          dateJoinedFormatted: u.date_joined
            ? new Date(u.date_joined).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })
            : '—',
          lastLoginFormatted: u.last_login
            ? new Date(u.last_login).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })
            : 'Never',
          isSuperuser: u.is_superuser === true,
          isStaffOnly: u.is_staff === true && u.is_superuser !== true,
          isInactive: u.is_active === false,
        }))
        this.total = data.total
        this.page = data.page
        this.pageCount = data.page_count
        this.pageSize = data.page_size || this.pageSize
        this.hasNext = data.has_next
        this.hasPrev = data.has_prev
      } catch (e) {
        console.error('Failed to load users:', e)
      } finally {
        this.loading = false
        this.loaded = true
      }
    },

    nextPage() {
      if (this.hasNext) {
        this.page += 1
        this.fetch()
      }
    },

    prevPage() {
      if (this.hasPrev) {
        this.page -= 1
        this.fetch()
      }
    },

    get isEmpty() {
      return this.loaded && !this.loading && this.users.length === 0
    },
    get hasResults() {
      return this.users.length > 0
    },
    get prevDisabled() {
      return !this.hasPrev || this.loading
    },
    get nextDisabled() {
      return !this.hasNext || this.loading
    },
    get summaryText() {
      if (this.total === 0) return 'No users'
      const start = (this.page - 1) * this.pageSize + 1
      const end = Math.min(start + this.users.length - 1, this.total)
      return `Showing ${start}–${end} of ${this.total}`
    },
    get pageLabel() {
      return `Page ${this.page} of ${this.pageCount}`
    },
  }))
})
