# Change Log

## Current

### Unreleased

- **In Progress:** Storybook integration with django-pattern-library
  - Added `django-pattern-library` 1.5.0
  - Created pattern wrapper templates (`templates/patterns/`)
  - Button atom patterns working (Primary, Secondary, Disabled)
  - See [STORYBOOK_INTEGRATION.md](./STORYBOOK_INTEGRATION.md)

- **Completed:** Formatting and linting toolchain
  - Added Prettier for JS/JSON/MD/YAML (no semicolons)
  - Added djlint for Django template linting/formatting
  - Updated pre-commit config with prettier and djlint hooks
  - Added `make format` and `make lint` targets
  - Fixed all templates to use named endblocks (Django best practice)
  - Fixed mypy type errors in CSP settings

- **Pending:**
  - Fix djlint pre-commit hook (multiprocessing permission issue in sandbox)
    - Solution: Use local hooks instead of repo hooks
  - Remaining atom patterns (Input, Link, Select, Icon)
  - Storybook setup (Phase 2)

## Past

### 0.0.1 - Initial release

- Django foundation (5.2.7, Python 3.13)
- Django Cotton component system
- Tailwind CSS + AlpineJS frontend
- Core atoms: Button, Input, Link, Select, Icon
- Component library page (/components/)
- Style guide page (/style-guide/)
