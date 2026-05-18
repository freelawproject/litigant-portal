/**
 * Theme Store - Dark Mode Management
 * Alpine.js store for managing theme (light/dark mode)
 * Persists to localStorage and syncs with system preference
 *
 * Usage:
 *   <button @click="$store.theme.toggle()">Toggle Theme</button>
 *   <span x-text="$store.theme.current"></span>
 */

document.addEventListener('alpine:init', () => {
  Alpine.store('theme', {
    // Initialize from localStorage or system preference
    current:
      localStorage.getItem('theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'),

    init() {
      // Apply initial theme
      this.apply()

      // Listen for system preference changes
      window
        .matchMedia('(prefers-color-scheme: dark)')
        .addEventListener('change', (e) => {
          if (!localStorage.getItem('theme')) {
            this.current = e.matches ? 'dark' : 'light'
            this.apply()
          }
        })
    },

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
  })

  // Initialize theme on Alpine init
  Alpine.store('theme').init()
})
