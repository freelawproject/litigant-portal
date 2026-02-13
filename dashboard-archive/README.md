# Dashboard Archive

Recovered dashboard home page layout from before the chat-first redesign.

**Source commit:** `40ab76c` — `refactor(layout): consolidate to single responsive base` (Dec 15, 2025)

**Removed in:** `e3a72a5` — `feat(layout): single-page chat-first design` (Dec 24, 2025)

## Screenshot

The dashboard had a hero section ("How can we help you today?"), search bar, and a 6-card "Browse by Topic" grid with a full footer.

## Structure

```
dashboard-archive/
├── README.md
├── css/
│   └── dashboard-components.css   # Original CSS (annotated diffs vs current)
└── templates/
    ├── base.html                  # Original base layout (min-h-screen, not chat-mode)
    ├── dashboard.html             # Page template assembling hero + topic grid
    └── cotton/
        ├── atoms/
        │   └── search_input.html  # Search input with magnifying glass icon
        ├── molecules/
        │   ├── search_bar.html    # Search form (input + button)
        │   └── topic_card.html    # Topic card (icon + title + description + arrow)
        └── organisms/
            ├── footer.html        # Full footer (nav links + divider + powered-by)
            ├── header.html        # Simple header (logo + hamburger, no timeline)
            ├── hero.html          # Hero section (heading + subheading + search bar)
            └── topic_grid.html    # 6-topic grid (3x2 on desktop)
```

## Key CSS Differences (dashboard era vs current chat-first)

| Class                  | Dashboard (original)      | Current (chat-first)                     |
| ---------------------- | ------------------------- | ---------------------------------------- |
| `.hero`                | `py-12 md:py-16 lg:py-20` | `padding-top: 12vh; padding-bottom: 4vh` |
| `.hero-subheading`     | `mb-8`                    | `mb-4`                                   |
| `.topic-grid-section`  | `py-10 md:py-12`          | `py-4 md:py-6` + transition              |
| `.topic-grid-heading`  | `mb-6`                    | `mb-4`                                   |
| `.mobile-header-inner` | `py-3`                    | `py-2`                                   |
| `.mobile-footer`       | `py-8`                    | `py-2`                                   |
| `body` (base.html)     | `min-h-screen`            | `h-dvh overflow-hidden`                  |

## CSS Classes Removed in Chat-First Redesign

The `dashboard-components.css` file includes these classes that were removed from `main.css`:

- **Alerts:** `.alert`, `.alert-warning`, `.alert-danger`, `.alert-info`, `.alert-success`
- **Buttons:** `.btn`, `.btn-primary`, `.btn-outline`, `.btn-dark`, `.btn-ghost`, `.btn-danger`, `.btn-xl`, `.btn-sm`
- **Inputs:** `.input`, `.input-error`, `.input-success`
- **Links:** `.link`, `.link-default`, `.link-primary`, `.link-secondary`, `.link-unstyled`
- **Selects:** `.select-wrapper`, `.select`, `.select-icon`
- **Logo:** `.logo-sm`, `.logo-lg` text size variants
- **Utilities:** `.scrollbar-thin`

Note: These were removed because the atoms (button.html, input.html, link.html) now inline their styles directly in the templates.

## Components Still Intact in Live Codebase

These files still exist in `templates/cotton/` and are unchanged from the dashboard era:

- `molecules/topic_card.html` — identical
- `organisms/topic_grid.html` — identical
- `molecules/search_bar.html` — identical
- `atoms/search_input.html` — identical

These were modified but still exist:

- `organisms/hero.html` — inlines the form instead of using `<c-molecules.search-bar>`
- `organisms/header.html` — added user menu, activity timeline slide-out
- `organisms/footer.html` — simplified to single compact line

## Wiring It Up (Future)

To restore the dashboard as the root route:

1. Copy the archived components back (or adjust the live ones)
2. Merge the CSS overrides from `dashboard-components.css` into `src/css/main.css`
3. Update `base.html` body class from `h-dvh overflow-hidden` to `min-h-screen`
4. Create a view + URL route for `dashboard.html`
5. Move the current chat-first `home.html` to a `/chat/` route
