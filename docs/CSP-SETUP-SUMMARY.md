# CSP and Template Linting Setup Summary

## What Was Added

### 1. Django's Built-in CSP Middleware ✅

**Added to `config/settings.py`:**

- `ContentSecurityPolicyMiddleware` in MIDDLEWARE
- `CONTENT_SECURITY_POLICY_REPORT_ONLY` configuration (Report-Only mode for development)
- Comments explaining how to switch to enforcement mode for production

**What it does:**
- Monitors Content Security Policy violations in development
- Logs violations to browser DevTools Console
- Doesn't block anything (Report-Only mode) - just reports issues
- Can be switched to enforcement mode for production

**How to use:**
1. Start dev server: `make dev`
2. Open browser and go to http://localhost:8000
3. Open DevTools Console (F12 or Cmd+Option+I)
4. Look for `[Report Only]` messages about CSP violations
5. Fix violations by moving inline code to external files

---

### 2. djLint - Django Template Linter ✅

**Installed:** `djlint` via `uv pip install djlint`

**Configured in:**
- `pyproject.toml` - djLint settings
- `.pre-commit-config.yaml` - Runs on git commit
- `Makefile` - Added to lint/format commands

**What it does:**
- Lints Django/Jinja templates for syntax and best practices
- Formats templates consistently (2-space indentation)
- Checks for accessibility issues
- Recognizes Cotton components (`c-slot`, `c-vars`)

**How to use:**
```bash
# Lint templates
make lint                  # Includes template linting
djlint templates/ --lint   # Just templates

# Format templates
make format                # Includes template formatting
djlint templates/ --reformat  # Just templates
```

---

## Configuration Details

### CSP Policy (Report-Only Mode)

```python
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],          # No inline scripts
        "style-src": ["'self'"],           # No inline styles
        "img-src": ["'self'", "data:", "https:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'", "ws://localhost:5173"],  # Vite HMR
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
        "upgrade-insecure-requests": True,
    }
}
```

### djLint Configuration

```toml
[tool.djlint]
profile = "django"
indent = 2
max_line_length = 120
format_css = true
format_js = true
ignore = "H006,H021,H030,H031"  # See reasons in config
custom_blocks = "c-slot,c-vars"  # Cotton components
```

---

## Files Modified

### Configuration Files

- ✅ `config/settings.py` - Added CSP middleware and configuration
- ✅ `pyproject.toml` - Added djLint configuration
- ✅ `.pre-commit-config.yaml` - Added djLint pre-commit hooks
- ✅ `Makefile` - Updated lint/format commands to include templates

### Templates Fixed

- ✅ `templates/base.html` - Added endblock names
- ✅ `templates/index.html` - Added endblock names
- ✅ `templates/cotton/dropdown.html` - No changes needed (already compliant)

### Documentation

- ✅ `docs/CSP-AND-LINTING.md` - Comprehensive guide (NEW)
- ✅ `docs/DEVELOPMENT.md` - Added CSP and djLint sections
- ✅ `README.md` - Added link to CSP guide

---

## What This Prevents

### CSP Catches These Security Issues:

❌ **Inline JavaScript** (XSS vector):
```html
<button onclick="doSomething()">Bad</button>
<script>alert('XSS')</script>
```

❌ **Inline Styles** (style injection):
```html
<div style="color: red;">Bad</div>
```

❌ **External Script Sources** (untrusted CDNs):
```html
<script src="https://evil.com/malware.js"></script>
```

### djLint Catches These Template Issues:

❌ **Missing endblock names**:
```django
{% block content %}...{% endblock %}  <!-- Missing name -->
```

❌ **Inconsistent indentation**
❌ **Unclosed tags**
❌ **Missing accessibility attributes** (can be configured)

---

## Testing the Setup

### Test CSP Monitoring

1. Start the dev server:
   ```bash
   make dev
   ```

2. Visit http://localhost:8000 and open DevTools Console

3. You should see the page load normally (Report-Only mode)

4. Try adding an inline script to a template:
   ```html
   <script>alert('test')</script>
   ```

5. Refresh the page - you should see a CSP violation in the console:
   ```
   [Report Only] Refused to execute inline script because it violates
   the following Content Security Policy directive: "script-src 'self'"
   ```

6. Remove the test script

### Test djLint

1. Check templates:
   ```bash
   djlint templates/ --lint
   ```

2. Should output:
   ```
   Linted 3 files, found 0 errors.
   ```

3. Try breaking a template (remove endblock name):
   ```django
   {% block content %}...{% endblock %}
   ```

4. Run djlint again - should report error

5. Revert change

---

## Integration with Existing Tools

No conflicts! Each tool has a specific role:

| Tool | Files | Purpose |
|------|-------|---------|
| **Ruff** | `*.py` | Python linting + formatting |
| **mypy** | `*.py` | Python type checking |
| **ESLint** | `*.ts`, `*.js` | TypeScript/JS linting |
| **Prettier** | `*.ts`, `*.js`, `*.css` | TS/JS/CSS formatting |
| **djLint** | `*.html` | Template linting + formatting |
| **Django CSP** | Runtime | CSP violation detection |

---

## Production Deployment

Before deploying to production:

1. **Test thoroughly** with CSP Report-Only mode

2. **Fix all CSP violations** found during testing

3. **Switch to enforcement mode** in `config/settings.py`:
   ```python
   # Comment out REPORT_ONLY:
   # CONTENT_SECURITY_POLICY_REPORT_ONLY = { ... }

   # Enable enforcement:
   CONTENT_SECURITY_POLICY = {
       "DIRECTIVES": {
           # ... same directives ...
       }
   }
   ```

4. **Test again** - CSP will now BLOCK violations instead of just reporting

5. **Monitor** for any violations in production logs

---

## Quick Reference

### Check for CSP Violations
- Open browser DevTools → Console
- Look for `[Report Only]` messages
- Fix by moving inline code to external files

### Lint and Format
```bash
make lint      # Lint everything (Python + TS + Templates)
make format    # Format everything
```

### Pre-commit Hooks
- Run automatically on `git commit`
- Include djLint for templates
- Will prevent commit if linting fails

### Documentation
- [Full CSP & Linting Guide](./CSP-AND-LINTING.md)
- [Development Guide](./DEVELOPMENT.md)

---

## Benefits

✅ **Security**: CSP prevents XSS attacks by blocking inline scripts
✅ **Consistency**: djLint ensures all templates follow same style
✅ **Early Detection**: Catch issues during development, not production
✅ **Automation**: Pre-commit hooks enforce standards automatically
✅ **Documentation**: Clear guidance on CSP-compliant patterns

---

**Setup Status**: ✅ Complete and tested

All tools configured, documented, and ready to use!
