# Vanilla JS Components

Contributor guide for the component system that replaced Alpine.js.

## Why Vanilla JS?

- **CSP-safe** — `script-src 'self'` with no `unsafe-eval`
- **Zero dependencies** — no framework to learn, update, or debug
- **Any web developer** can read and contribute
- **No framework conflicts** for court partner site embedding

### CSP Compliance

Our Content Security Policy is `script-src 'self'` — only scripts served from our own origin can execute. This blocks three things: `eval()`/`new Function()`, inline event handlers (`onclick="..."`), and inline `<script>` tags. All three require `unsafe-eval` or `unsafe-inline` directives that we intentionally omit.

Alpine.js's standard build uses `new Function()` to evaluate every template expression (e.g., `x-on:click="open = !open"` gets compiled into a function at runtime). Alpine's "CSP build" avoids this but restricts expressions to dot-path-only — no method calls, no ternaries — which was too limiting for contributors.

Vanilla JS sidesteps the problem entirely:

- All code lives in static `.js` files served from `/static/js/` — satisfies `'self'`
- No string-to-code evaluation — no `eval()`, `new Function()`, `setTimeout("string")`
- Events bound via `addEventListener()` in JS files, never inline `on*` attributes in HTML
- The `csp-inline-check` pre-commit hook catches any inline handlers that slip into templates

## Architecture

```
static/js/
├── app.js          # Registry: registerComponent, initComponents, renderList, scrollToBottom
├── theme.js        # Dark mode IIFE (runs before DOMContentLoaded)
├── components.js   # UI components: appHeader, autoDismiss, userMenu
└── chat.js         # Chat components: chat, homePage
```

Load order in `base.html`: theme → app → components → chat.

## Component Pattern

### Registration

```js
registerComponent('myWidget', (el) => {
  // el is the root DOM element with data-component="myWidget"

  // 1. Query refs
  const btn = ref(el, 'toggle')
  const panel = ref(el, 'panel')

  // 2. State (plain object)
  let open = false

  // 3. Event listeners
  btn.addEventListener('click', () => {
    open = !open
    update()
  })

  // 4. update() syncs DOM from state
  function update() {
    panel.hidden = !open
    btn.setAttribute('aria-expanded', String(open))
  }

  // 5. Initial render
  update()
})
```

### Template

```html
<div data-component="myWidget">
  <button data-ref="toggle" aria-expanded="false">Open</button>
  <div data-ref="panel" hidden>Content here</div>
</div>
```

### Lifecycle

1. `DOMContentLoaded` fires
2. `initComponents()` queries all `[data-component]` elements
3. Each element's factory runs once (skips if `_componentInit` flag set)
4. Factory owns the element for its lifetime

## Data Attributes

| Attribute               | Purpose                                        |
| ----------------------- | ---------------------------------------------- |
| `data-component="name"` | Root element — triggers factory from registry  |
| `data-ref="name"`       | Queryable child — `ref(el, 'name')` returns it |
| `data-bind="name"`      | Content target inside `<template>` clones      |
| `data-field="name"`     | Sidebar field updated by `updateSidebar()`     |
| `data-section="name"`   | Section shown/hidden based on data             |
| `data-action="name"`    | Clickable element (querySelectorAll pattern)   |
| `data-template="name"`  | `<template>` element for `renderList()`        |
| `data-icon="type"`      | Icon variant shown/hidden per item             |

## Patterns

### Show/Hide

```js
el.hidden = !shouldShow // replaces x-show + x-cloak
```

Start elements with `hidden` attribute in HTML if they should be hidden initially.

### Text Content

```js
el.textContent = value // replaces x-text
```

### HTML Content (sanitized only)

```js
el.innerHTML = chatUtils.renderMarkdown(text) // replaces x-html
```

Only use `innerHTML` with sanitized content (our markdown renderer escapes HTML first).

### Events

```js
btn.addEventListener('click', handler) // replaces x-on:click
document.addEventListener('keydown', handler) // replaces x-on:keydown.escape.window
document.addEventListener('click', (e) => {
  // replaces x-on:click.outside
  if (!el.contains(e.target)) close()
})
```

### Dynamic Lists

```js
renderList(container, '[data-template="item"]', items, (clone, item) => {
  clone.querySelector('[data-bind="title"]').textContent = item.title
  clone.querySelector('[data-bind="date"]').textContent = item.date
})
```

```html
<div data-list="items">
  <template data-template="item">
    <div>
      <span data-bind="title"></span>
      <span data-bind="date"></span>
    </div>
  </template>
</div>
```

### Scroll to Bottom

```js
scrollToBottom(el) // scrolls if near bottom
scrollToBottom(el, true) // force scroll
```

### Passing Data from Django

Use `data-*` attributes on the component root:

```html
<div
  data-component="chat"
  data-session-id="{{ session_id }}"
  data-agent-name="{{ agent_name }}"
></div>
```

```js
registerComponent('chat', (el) => {
  const sessionId = el.dataset.sessionId || ''
  const agentName = el.dataset.agentName || ''
})
```

### Composing Components

`createChat(el)` returns an API object that `createHomePage(el)` extends:

```js
function createHomePage(el) {
  const chat = createChat(el) // get chat API
  chat.onBeforeSend = myHook // wire hooks
  // ...add page-specific logic
}
```

### Native `<dialog>`

For overlays, prefer native `<dialog>` over custom modals:

```js
dialog.showModal() // opens with backdrop, Escape, focus trap
dialog.close() // closes
```

```html
<dialog data-ref="dialog" class="timeline-dialog">
  <div class="timeline-dialog-panel">...</div>
</dialog>
```

## Creating a New Component

1. Add `registerComponent('name', factory)` to `components.js` (or `chat.js` for chat-related)
2. Add `data-component="name"` to the Cotton template
3. Use `data-ref` for queryable children, `hidden` for initial state
4. Write an `update()` function that syncs all DOM from state
5. Add event listeners that modify state then call `update()`

## Testing Checklist

After changes, verify:

- [ ] Zero JS errors in browser console
- [ ] Zero CSP violations (check Network tab for blocked resources)
- [ ] Keyboard navigation works (Tab, Enter, Space, Escape)
- [ ] `aria-expanded` and other ARIA attributes update correctly
- [ ] Mobile viewport — touch targets adequate, layout correct
- [ ] `make lint` passes
- [ ] `make test` passes
