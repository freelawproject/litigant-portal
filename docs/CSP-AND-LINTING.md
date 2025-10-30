# CSP and Template Linting Guide

This document explains the Content Security Policy (CSP) setup and template linting tools configured for the project.

## Content Security Policy (CSP)

### What is CSP?

Content Security Policy is a security standard that helps prevent Cross-Site Scripting (XSS), clickjacking, and other code injection attacks by restricting what resources can be loaded on your pages.

### Our CSP Configuration

The project uses **Django 5.2's built-in CSP middleware** which is configured in `config/settings.py`.

#### Development Mode (Report-Only)

In development, CSP runs in **Report-Only mode**. This means:
- ✅ Violations are **logged to the browser console**
- ✅ Nothing is blocked - site continues to work
- ✅ You can develop and test without CSP breaking things
- ⚠️ You must check browser DevTools Console for violations

**Setting**: `CONTENT_SECURITY_POLICY_REPORT_ONLY`

#### Production Mode (Enforcement)

In production, switch to enforcement mode:
- ❌ Violations are **blocked** by the browser
- 🔒 Stronger security protection
- ⚠️ Must fix all violations before deploying

**To enable**: In `config/settings.py`, uncomment:
```python
CONTENT_SECURITY_POLICY = CONTENT_SECURITY_POLICY_REPORT_ONLY
```

### CSP Rules Configured

Our policy enforces:

```python
"default-src": ["'self'"]           # Only load resources from same origin
"script-src": ["'self'"]            # No inline scripts, only external files
                                    # + "'unsafe-eval'" in dev for source maps
"style-src": ["'self'"]             # No inline styles, only external files
                                    # + "'unsafe-inline'" in dev for Vite HMR
"img-src": ["'self'", "data:", "https:"]  # Images from same origin, data URIs, HTTPS
"font-src": ["'self'"]              # Fonts from same origin
"connect-src": ["'self'", "ws://localhost:5173"]  # Allow Vite HMR in dev
"object-src": ["'none'"]            # Block plugins (Flash, etc.)
"base-uri": ["'self'"]              # Restrict <base> tag
"form-action": ["'self'"]           # Forms can only submit to same origin
"frame-ancestors": ["'none'"]       # Prevent clickjacking
```

### Development Mode CSP Relaxations

In development mode (`DEBUG = True`), the CSP is slightly relaxed to enable debugging:

- **`'unsafe-eval'` for `script-src`**: Enables source maps and Vite HMR
- **`'unsafe-inline'` for `style-src`**: Allows Vite to inject styles during development

These relaxations are **automatically removed in production** when `DEBUG = False`.

**Why this matters for debugging**:
- All JavaScript dependencies (AlpineJS, etc.) are served **unminified** in dev mode
- Source maps are generated for all built assets (`vite.config.ts` has `sourcemap: true`)
- Browser DevTools can show original TypeScript source code, not compiled JS
- You can set breakpoints in your original `.ts` files
- AlpineJS uses the unminified `module.esm.js` (3,407 lines) instead of `module.esm.min.js` (5 lines)

### What CSP Blocks

❌ **Inline JavaScript**:
```html
<!-- BAD: Will be blocked/reported -->
<button onclick="doSomething()">Click</button>
<script>alert('hello')</script>
```

✅ **External JavaScript** (CSP-compliant):
```html
<!-- GOOD: External file -->
<script src="/static/js/main.js"></script>

<!-- GOOD: Alpine directives (not inline JS) -->
<button x-on:click="toggle">Click</button>
```

❌ **Inline Styles**:
```html
<!-- BAD: Will be blocked/reported -->
<div style="color: red;">Text</div>
```

✅ **External Styles** (CSP-compliant):
```html
<!-- GOOD: External stylesheet -->
<link rel="stylesheet" href="/static/css/styles.css">

<!-- GOOD: Tailwind classes -->
<div class="text-red-500">Text</div>
```

### Checking for CSP Violations

#### During Development

1. **Start the dev server**:
   ```bash
   make dev
   ```

2. **Open browser DevTools Console** (F12 or Cmd+Option+I)

3. **Look for CSP violation reports**:
   ```
   [Report Only] Refused to execute inline script because it violates
   the following Content Security Policy directive: "script-src 'self'"
   ```

4. **Fix the violation** by moving inline code to external files

#### What to Look For

- Lines starting with `[Report Only]`
- Messages about `violates the following Content Security Policy directive`
- Blocked resources or inline scripts/styles

### Common CSP Patterns

#### Alpine.js Components (CSP-Safe ✅)

Alpine directives are **NOT inline JavaScript** - they're attributes that Alpine interprets:

```html
<!-- CSP-SAFE: These are attributes, not inline JS -->
<div x-data="dropdown">
  <button x-on:click="toggle">Toggle</button>
  <div x-show="open">Content</div>
</div>
```

The actual JavaScript is in external files:
```typescript
// frontend/src/ts/alpine/components/dropdown.ts
Alpine.data('dropdown', () => ({ /* ... */ }))
```

#### Initial Hidden State for Alpine

Sometimes you need `style="display: none;"` for Alpine's `x-show`:

```html
<div x-show="open" style="display: none;">
  <!-- This inline style is necessary for initial state -->
</div>
```

This is acceptable because:
1. It's just initial state, not dynamic styling
2. Alpine takes over after page load
3. Alternative (adding class via Alpine) is more complex

---

## Template Linting with djLint

### What is djLint?

**djLint** is a linter and formatter specifically for Django templates. It:
- Checks template syntax and best practices
- Formats HTML consistently
- Enforces accessibility standards (like alt tags)
- Formats inline CSS/JS in templates

### Running djLint

```bash
# Lint all templates
make lint
# or
djlint templates/ --lint

# Format all templates
make format
# or
djlint templates/ --reformat

# Check formatting without changes
djlint templates/ --check
```

### Configuration

djLint is configured in `pyproject.toml`:

```toml
[tool.djlint]
profile = "django"              # Use Django template syntax
indent = 2                      # 2-space indentation
max_line_length = 120          # Max line length
format_css = true              # Format inline CSS
format_js = true               # Format inline JS
ignore = "H006,H021,H030,H031" # Ignored rules (see below)
custom_blocks = "c-slot,c-vars" # Recognize Cotton components
```

### Ignored Rules

We ignore these djLint rules:

- **H006**: Missing alt attributes on images (we'll add as needed)
- **H021**: Inline styles (needed for Alpine `x-show` initial state)
- **H030/H031**: Meta tags (base template doesn't need all meta tags)

### Pre-commit Integration

djLint runs automatically on commit via pre-commit hooks:

```yaml
- repo: https://github.com/djlint/djLint
  rev: v1.36.4
  hooks:
    - id: djlint-reformat-django  # Auto-format on commit
    - id: djlint-django           # Lint on commit
```

### Common djLint Fixes

#### Endblock Naming

❌ **Before**:
```django
{% block content %}
  ...
{% endblock %}
```

✅ **After**:
```django
{% block content %}
  ...
{% endblock content %}
```

#### Consistent Indentation

djLint enforces consistent 2-space indentation throughout templates.

---

## Tool Comparison

| Tool | Files | Purpose |
|------|-------|---------|
| **Ruff** | `*.py` | Python linting + formatting |
| **mypy** | `*.py` | Python type checking |
| **ESLint** | `*.ts`, `*.js` | TypeScript/JS linting |
| **Prettier** | `*.ts`, `*.js`, `*.css` | TypeScript/JS/CSS formatting |
| **djLint** | `*.html` | Django template linting + formatting |
| **Django CSP** | Runtime | CSP violation detection in browser |

**No overlap** - each tool handles different file types!

---

## Development Workflow

### 1. Write Code Normally

Develop features as usual. CSP is in Report-Only mode so nothing breaks.

### 2. Check for Issues Regularly

```bash
# Run all linters (Python + TypeScript + Templates)
make lint

# Check formatting
make format-check
```

### 3. Check Browser Console

When testing in browser:
1. Open DevTools Console (F12)
2. Look for `[Report Only]` CSP violations
3. Fix any violations by moving inline code to external files

### 4. Format Before Committing

```bash
# Format all code
make format
```

### 5. Pre-commit Hooks

Pre-commit hooks automatically:
- Run Ruff on Python files
- Run djLint on templates
- Check for common issues

If pre-commit fails, fix the issues and commit again.

---

## Best Practices

### ✅ Do This

1. **Keep scripts in external files**
   ```html
   <script src="{% static 'js/main.js' %}"></script>
   ```

2. **Use Alpine directives (not inline handlers)**
   ```html
   <button x-on:click="toggle">Click</button>
   ```

3. **Use Tailwind classes (not inline styles)**
   ```html
   <div class="text-red-500 font-bold">Text</div>
   ```

4. **Check browser console regularly**
   - Look for CSP violations during development

5. **Run linters before committing**
   ```bash
   make lint
   make format
   ```

### ❌ Don't Do This

1. **Inline event handlers**
   ```html
   <!-- BAD -->
   <button onclick="doSomething()">Click</button>
   ```

2. **Inline scripts**
   ```html
   <!-- BAD -->
   <script>
     alert('hello');
   </script>
   ```

3. **Inline styles (except Alpine initial state)**
   ```html
   <!-- BAD (unless for Alpine x-show) -->
   <div style="color: red;">Text</div>
   ```

4. **Committing with linting errors**
   - Fix all linting issues before committing

---

## Troubleshooting

### CSP Violation: "Refused to execute inline script"

**Problem**: You have inline JavaScript in a template.

**Solution**: Move the JavaScript to an external file:
1. Create a TypeScript file in `frontend/src/ts/`
2. Import it in `main.ts`
3. Use Alpine directives instead of inline handlers

### CSP Violation: "Refused to apply inline style"

**Problem**: You have `style="..."` in HTML.

**Solution**:
- Use Tailwind classes instead: `class="text-red-500"`
- Or create a CSS class in `input.css`
- Exception: `style="display: none;"` for Alpine `x-show` is OK

### djLint Fails on Cotton Components

**Problem**: djLint doesn't recognize `<c-component>` tags.

**Solution**: Already configured! Check `pyproject.toml`:
```toml
custom_blocks = "c-slot,c-vars"
```

Add more Cotton-specific blocks here if needed.

### Pre-commit Hook is Too Slow

**Problem**: Pre-commit takes a long time.

**Solution**:
- Only changed files are checked (by default)
- Skip hooks temporarily: `git commit --no-verify` (not recommended)
- Or disable specific hooks in `.pre-commit-config.yaml`

---

## Resources

- [Django CSP Documentation](https://docs.djangoproject.com/en/5.2/ref/csp/)
- [djLint Documentation](https://djlint.com/)
- [Content Security Policy (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [AlpineJS Documentation](https://alpinejs.dev/)
