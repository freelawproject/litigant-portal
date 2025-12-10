# Change Log

## Current

### Unreleased

- **Completed:** Build simplification
  - Removed Node.js dependency entirely
  - Tailwind CSS via Homebrew standalone CLI (`brew install tailwindcss`)
  - Alpine.js via CDN
  - Migrated to Tailwind v4 CSS-based configuration (@theme blocks)
  - Removed `tailwind.config.js` in favor of `static/css/main.css` theme tokens

- **Completed:** Component library overhaul
  - Removed `django-pattern-library` (custom page is sufficient)
  - Removed Storybook from project plan
  - Created custom `/components/` page with CourtListener-style layout
  - A11y testing via browser DevTools (Lighthouse, axe extension)

- **Completed:** Formatting and linting toolchain
  - Added Prettier for JS/JSON/MD/YAML (no semicolons)
  - Added djlint for Django template linting/formatting
  - Updated pre-commit config with prettier and djlint hooks
  - Added `make format` and `make lint` targets
  - Fixed all templates to use named endblocks (Django best practice)
  - Fixed mypy type errors in CSP settings

- **Completed:** Mobile-first landing page (Issue #28)
  - Added atomic design structure: atoms → molecules → organisms
  - New atom: `search_input` (search input with icon)
  - New molecules: `logo`, `search_bar`, `topic_card`
  - New organisms: `mobile_header`, `hero`, `topic_grid`, `mobile_footer`
  - Updated `home.html` to use new landing page components
  - 6 topic categories: Housing, Family, Small Claims, Consumer, Expungement, Traffic
  - Responsive grid: 1 col mobile → 2 col tablet → 3 col desktop
  - Component library updated with all new components

- **Pending:**
  - Wire up search functionality (currently placeholder)
  - Add logo image (user to provide `static/images/logo.svg`)
  - Fix djlint pre-commit hook (multiprocessing permission issue in sandbox)
    - Solution: Use local hooks instead of repo hooks

## Past

### 0.0.1 - Initial release

- Django foundation (5.2.7, Python 3.13)
- Django Cotton component system
- Tailwind CSS + AlpineJS frontend
- Core atoms: Button, Input, Link, Select, Icon
- Component library page (/components/)
- Style guide page (/style-guide/)
