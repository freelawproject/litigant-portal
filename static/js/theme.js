/**
 * Theme - Dark Mode Management
 *
 * IIFE that applies theme immediately (before DOMContentLoaded) to prevent
 * flash of wrong theme. Exposes window.theme for programmatic access.
 *
 * Usage:
 *   window.theme.toggle()
 *   window.theme.current // 'light' or 'dark'
 */
;(function () {
  const theme = {
    current:
      localStorage.getItem('theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'),

    toggle() {
      this.current = this.current === 'light' ? 'dark' : 'light'
      this.apply()
      localStorage.setItem('theme', this.current)
    },

    setLight() {
      this.current = 'light'
      this.apply()
      localStorage.setItem('theme', 'light')
    },

    setDark() {
      this.current = 'dark'
      this.apply()
      localStorage.setItem('theme', 'dark')
    },

    apply() {
      if (this.current === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },

    get isDark() {
      return this.current === 'dark'
    },

    get isLight() {
      return this.current === 'light'
    },
  }

  // Apply immediately to prevent flash
  theme.apply()

  // Listen for system preference changes
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', (e) => {
      if (!localStorage.getItem('theme')) {
        theme.current = e.matches ? 'dark' : 'light'
        theme.apply()
      }
    })

  window.theme = theme
})()
