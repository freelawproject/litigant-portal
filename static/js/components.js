/**
 * Vanilla JS UI Components
 *
 * Registered via registerComponent() from app.js.
 * Each component is a factory receiving its root DOM element.
 *
 * Loaded in base.html after app.js.
 */

// =============================================================================
// Auto-dismiss — hides element after a timeout with fade-out
// =============================================================================

registerComponent('autoDismiss', (el) => {
  const timeout = parseInt(el.dataset.timeout, 10) || 1500

  setTimeout(() => {
    el.classList.add('fade-out')
    el.addEventListener(
      'animationend',
      () => {
        el.hidden = true
      },
      { once: true }
    )
  }, timeout)
})

// =============================================================================
// User Menu — dropdown toggle with outside click + Escape + aria-expanded
// =============================================================================

registerComponent('userMenu', (el) => {
  const trigger = ref(el, 'trigger')
  const menu = ref(el, 'menu')
  if (!trigger || !menu) return

  let open = false

  function toggle() {
    open = !open
    update()
    if (open) {
      // Focus first menu item when opened
      requestAnimationFrame(() => {
        const firstItem = menu.querySelector('[role="menuitem"]')
        if (firstItem) firstItem.focus()
      })
    }
  }

  function close() {
    if (!open) return
    open = false
    update()
    trigger.focus()
  }

  function update() {
    menu.hidden = !open
    trigger.setAttribute('aria-expanded', String(open))
  }

  // Click trigger
  trigger.addEventListener('click', toggle)

  // Outside click
  document.addEventListener('click', (e) => {
    if (open && !el.contains(e.target)) close()
  })

  // Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && open) close()
  })

  // Initial state
  update()
})

// =============================================================================
// Helpers for timeline
// =============================================================================

function borderClassForType(type) {
  if (type === 'upload') return 'border-primary-300 bg-primary-50/50'
  if (type === 'summary') return 'border-blue-300 bg-blue-50/50'
  return 'border-greyscale-300 bg-greyscale-50'
}

function formatTimestamp(ts) {
  return new Date(ts).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// =============================================================================
// App Header — activity timeline dialog (replaces slide-over)
// =============================================================================

registerComponent('appHeader', (el) => {
  const dialog = ref(el, 'dialog')
  const openBtn = ref(el, 'openMenu')
  const closeBtn = ref(el, 'closeMenu')
  const clearBtn = ref(el, 'clearDemo')
  const eventsContainer = ref(el, 'events')
  const emptyState = ref(el, 'emptyState')
  const eventsList = ref(el, 'eventsList')

  if (!dialog || !openBtn) return

  function openMenu() {
    const raw = JSON.parse(localStorage.getItem('caseTimeline') || '[]')
    const timeline = [...raw].reverse().map((event) => ({
      ...event,
      borderClass: borderClassForType(event.type),
      formattedTime: formatTimestamp(event.timestamp),
    }))
    renderTimeline(timeline)
    dialog.showModal()
    requestAnimationFrame(() => {
      if (closeBtn) closeBtn.focus()
    })
    openBtn.setAttribute('aria-expanded', 'true')
  }

  function closeMenu() {
    dialog.close()
    openBtn.setAttribute('aria-expanded', 'false')
    openBtn.focus()
  }

  function renderTimeline(timeline) {
    if (!eventsContainer) return

    if (emptyState) emptyState.hidden = timeline.length > 0
    if (eventsList) eventsList.hidden = timeline.length === 0

    if (eventsList && timeline.length > 0) {
      renderList(
        eventsList,
        '[data-template="timelineEvent"]',
        timeline,
        (clone, event) => {
          // Timestamp
          const timeEl = clone.querySelector('[data-bind="time"]')
          if (timeEl) timeEl.textContent = event.formattedTime

          // Icons — show the right one based on type
          const icons = clone.querySelectorAll('[data-icon]')
          icons.forEach((icon) => {
            icon.hidden = icon.dataset.icon !== event.type
          })

          // Title
          const titleEl = clone.querySelector('[data-bind="title"]')
          if (titleEl) {
            titleEl.textContent = event.title
            titleEl.hidden = !event.title
          }

          // Content
          const contentEl = clone.querySelector('[data-bind="content"]')
          if (contentEl) contentEl.textContent = event.content

          // Border class
          const card = clone.querySelector('[data-bind="card"]')
          if (card) {
            card.className = card.className + ' ' + event.borderClass
            // Toggle expand/collapse on click
            card.addEventListener('click', () => {
              const content = card.querySelector('[data-bind="content"]')
              if (content) {
                const isCollapsed = content.classList.contains('line-clamp-2')
                if (isCollapsed) {
                  content.classList.remove('line-clamp-2')
                } else {
                  content.classList.add('line-clamp-2')
                }
              }
            })
          }
        }
      )
    }
  }

  // Event listeners
  openBtn.addEventListener('click', openMenu)
  if (closeBtn) closeBtn.addEventListener('click', closeMenu)

  // Native dialog handles Escape and backdrop click via ::backdrop
  dialog.addEventListener('click', (e) => {
    // Close on backdrop click (click on the dialog element itself, not children)
    if (e.target === dialog) closeMenu()
  })

  dialog.addEventListener('close', () => {
    openBtn.setAttribute('aria-expanded', 'false')
  })

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      localStorage.clear()
      location.reload()
    })
  }
})
