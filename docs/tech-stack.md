# Tech Stack Report

## Core Framework

- **SvelteKit** (v2.47.1) - Full-stack web framework
  - Config: `svelte.config.js`
  - Adapter: `@sveltejs/adapter-auto` (auto-detects deployment platform)
  - Preprocessor: `vitePreprocess()`

## Build Tool

- **Vite** (v7.1.10) - Fast build tool and dev server
  - Config: `vite.config.ts`
  - Integrates: UnoCSS plugin, SvelteKit plugin, devtools-json plugin

## Styling

- **UnoCSS** (v0.66.5) - Atomic CSS engine (Tailwind-compatible, CSP-friendly)
  - Config: `uno.config.ts`
  - Presets: `presetUno()`, `presetTypography()`
  - Scans: All `.svelte`, `.js`, `.ts`, `.stories.*`, `.mdx` files
  - Integration: Vite plugin in `vite.config.ts:8` and `.storybook/main.ts:19`

## TypeScript

- **TypeScript** (v5.9.3) - Type-safe JavaScript
  - Config: `tsconfig.json`
  - Strict mode enabled
  - Extends: `.svelte-kit/tsconfig.json` (auto-generated)

## Code Quality

- **ESLint** (v9.38.0) - JavaScript/TypeScript linter
  - Config: `eslint.config.js` (flat config format)
  - Plugins: `typescript-eslint`, `eslint-plugin-svelte`, `eslint-plugin-storybook`
  - Prettier integration: `eslint-config-prettier`

- **Prettier** (v3.6.2) - Code formatter
  - Config: `.prettierrc`
  - Settings: Tabs, single quotes, 100 char width
  - Plugin: `prettier-plugin-svelte`

## Testing

- **Vitest** (v4.0.5) - Unit testing framework
  - Config: `vite.config.ts:9-35` (test section)
  - Two projects: client (browser with Playwright) & server (Node.js)
  - Browser: `@vitest/browser-playwright` with Chromium

- **Playwright** (v1.56.1) - E2E testing
  - Config: `playwright.config.ts`
  - Test directory: `e2e/`
  - Server: Builds and previews on port 4173

## Component Development

- **Storybook** (v10.0.7) - Component explorer
  - Config: `.storybook/main.ts`, `.storybook/preview.ts`
  - Framework: `@storybook/sveltekit`
  - Addons: svelte-csf, chromatic, docs, a11y, vitest
  - UnoCSS: Integrated via `viteFinal` hook

## Security

- **CSP (Content Security Policy)** - Configured in `svelte.config.js:14-27`
  - Mode: `auto` (generates nonces automatically)
  - Directives: Strict, no `unsafe-inline` needed (thanks to UnoCSS)

## How They Work Together

### Development Flow

1. Vite dev server starts
2. UnoCSS scans files for utility classes
3. SvelteKit compiles .svelte files
4. TypeScript type-checks in parallel
5. Browser receives optimized bundles

### Build Flow

1. TypeScript compiles to JavaScript
2. UnoCSS generates static CSS (CSP-safe)
3. Vite bundles & optimizes
4. SvelteKit generates SSR + client code
5. Adapter prepares for deployment

### Code Quality Flow

1. Write code
2. Prettier formats on save
3. ESLint catches errors (TS + Svelte rules)
4. TypeScript validates types
5. Tests run (Vitest unit + Playwright E2E)

## Configuration File Summary

| Tool | Config File | Location |
|------|-------------|----------|
| SvelteKit | `svelte.config.js` | Root |
| Vite | `vite.config.ts` | Root |
| UnoCSS | `uno.config.ts` | Root |
| TypeScript | `tsconfig.json` | Root |
| ESLint | `eslint.config.js` | Root |
| Prettier | `.prettierrc` | Root |
| Vitest | `vite.config.ts` (test section) | Root |
| Playwright | `playwright.config.ts` | Root |
| Storybook | `.storybook/main.ts`, `.storybook/preview.ts` | `.storybook/` |

## Package Scripts

```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run preview      # Preview production build
npm run check        # TypeScript type checking
npm run check:watch  # Type checking in watch mode
npm run format       # Format code with Prettier
npm run lint         # Run Prettier check + ESLint
npm run test:unit    # Run Vitest unit tests
npm run test:e2e     # Run Playwright E2E tests
npm run test         # Run all tests
npm run storybook    # Start Storybook dev server
npm run build-storybook  # Build Storybook for production
```
