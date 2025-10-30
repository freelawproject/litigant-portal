/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './templates/**/*.html',
    './portal/templates/**/*.html',
    './frontend/src/**/*.{js,ts}',
  ],
  theme: {
    extend: {
      // Add your custom theme values here
      // Following CourtListener pattern: store branding values in config
      colors: {
        // Example: Add your brand colors
        // primary: {...},
        // secondary: {...},
      },
    },
  },
  plugins: [],
}
