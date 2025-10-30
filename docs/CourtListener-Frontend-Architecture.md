# CourtListener New Frontend Architecture Summary

**Reference:** https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture

## Overview
CourtListener is redesigning its frontend incrementally using three modern tools to replace older technologies. The rollout uses a waffle flag (`use_new_design`) to gradually transition pages without breaking the existing site.

### Technology Replacements
| Previous | New |
|----------|-----|
| Bootstrap, custom CSS | TailwindCSS |
| DTL includes | Django Cotton |
| jQuery | AlpineJS |

---

## TailwindCSS Implementation

**Key Requirements:**
- Store branding values in `tailwind.config.js`
- Add custom styles to `input.css` (minimally)
- Include template paths in the `content` configuration
- Classes must be statically defined—"If you do something like `text-greyscale-${condition ? '800' : '400'}`, it will NOT be recognized by tailwind"

**Third-Party CSS:**
Libraries requiring stylesheets go in `/assets/static-global/css/third_party`. If used globally, import at the top of `input.css` for minification. Otherwise, use conditional `<link>` tags in specific templates.

---

## Django Cotton Components

**Structure:**
- Save components in `templates/cotton/` with snake_case filenames (e.g., `my_component.html`)
- Reference using kebab-case with `c-` prefix: `<c-my-component />`

**Component Declaration:**
```html
<c-vars title />

<div>
    <h2>{{ title }}</h2>
</div>
```

**Dynamic Attributes:**
Prepend `:` for non-string data:
```html
<c-my-component :some-list="['first', 'second']" />
```

**Slots:**
- Default slot: `{{ slot }}`
- Named slots: `{{ slot_name }}` in component, `<c-slot name="slot_name">content</c-slot>` when calling

**Requirements:**
All components must be added to the Component Library with four sections: Demo, Props, Slots, and Code.

---

## AlpineJS Interactivity

**Critical Constraint:**
"Virtually all Alpine docs use inline JavaScript for examples, so most of them will NOT be applicable to our codebase" due to strict Content Security Policy. No inline JavaScript allowed.

**Setup Pattern:**
```javascript
document.addEventListener('alpine:init', () => {
    Alpine.data('dropdown', () => ({
        open: false,
        toggle() {
            this.open = !this.open
        },
    }));
});
```

```html
<div x-data="dropdown">
    <button x-on:click="toggle">Toggle</button>
    <div x-show="open">...</div>
</div>
```

**Script Types:**
1. **Plugins** (`alpine/plugins/`) - Alpine-provided extensions
2. **Components** (`alpine/components/`) - Script per Cotton component
3. **Composables** (`alpine/composables/`) - Reusable logic utilities

**Injection:**
Use `{% require_script %}` template tag. Plugins should omit file extensions and include `defer=True`:
```html
{% require_script "js/alpine/plugins/intersect@3.14.8" defer=True %}
```

**Conventions:**
- Always use `x-` prefix: `x-on:click`, `x-bind:attr`, not `@click` or `:attr`
- Expose DOM sections with `x-data`
- Access Alpine objects via plain keys, not inline expressions

**Unsupported Features:**
`x-model` and `x-modelable` require `unsafe-eval`, prohibited by CSP. Use `data-` attributes and events instead.

---

## Legacy Template Integration

When modifying old templates that have new versions, include this notice:
```html
{% comment %}
║ This template has a new version behind use_new_design waffle flag.
║ Update the new version at: cl/simple_pages/templates/v2_[path]/[name].html
{% endcomment %}
```

New templates extend `new_base.html` instead of `base.html`.

---

## Strict Prohibitions

New templates **MUST NOT** use:
- jQuery
- Bootstrap
- Font Awesome
- React
- DTL includes
