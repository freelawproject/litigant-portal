/** @type {import('tailwindcss').Config} */
export default {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  darkMode: 'class', // Enable class-based dark mode
  theme: {
    extend: {
      colors: {
        // Primary (Chicago Blue)
        primary: {
          50: '#e6f5fb',
          100: '#b3e1f4',
          200: '#80cded',
          300: '#4db9e6',
          400: '#41b6e6',
          500: '#1a9fd9',
          600: '#1482b3',
          700: '#0f658c',
          800: '#094866',
          900: '#042b40',
        },
        // Secondary (Red)
        secondary: {
          50: '#fde8ea',
          100: '#fbb8be',
          200: '#f98892',
          300: '#f75866',
          400: '#ea1c2c',
          500: '#d11823',
          600: '#a6131c',
          700: '#7c0e15',
          800: '#51090e',
          900: '#270507',
        },
        // Accent (Yellow)
        accent: {
          300: '#ffd966',
          400: '#ffc72c',
          500: '#e6b328',
        },
      },
      fontFamily: {
        antonio: ['Antonio', 'sans-serif'],
        roboto: ['Roboto', 'sans-serif'],
        'roboto-serif': ['Roboto Serif', 'serif'],
      },
      fontSize: {
        // Title sizes
        'title-1': ['2.5rem', { lineHeight: '1.2', fontWeight: '700' }],
        'title-2': ['2rem', { lineHeight: '1.25', fontWeight: '700' }],
        'title-3': ['1.75rem', { lineHeight: '1.3', fontWeight: '600' }],
        'title-4': ['1.5rem', { lineHeight: '1.3', fontWeight: '600' }],
        'title-5': ['1.25rem', { lineHeight: '1.4', fontWeight: '600' }],
        'title-6': ['1.125rem', { lineHeight: '1.4', fontWeight: '600' }],
        'title-7': ['1rem', { lineHeight: '1.5', fontWeight: '600' }],
        'title-8': ['0.875rem', { lineHeight: '1.5', fontWeight: '600' }],
      },
      spacing: {
        // 4px base unit spacing system
        xs: '0.25rem', // 4px
        sm: '0.5rem', // 8px
        md: '1rem', // 16px
        lg: '1.5rem', // 24px
        xl: '2rem', // 32px
        '2xl': '3rem', // 48px
        '3xl': '4rem', // 64px
      },
    },
    screens: {
      sm: '640px', // Small tablets
      md: '768px', // Tablets
      lg: '1024px', // Desktops
      xl: '1280px', // Large desktops
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
