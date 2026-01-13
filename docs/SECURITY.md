# Security

## Vulnerability Disclosure

VDP: https://free.law/vulnerability-disclosure-policy/

---

## Production Security Headers

When `DEBUG=False`, Django enables these security settings:

| Setting                          | Value         | Purpose                 |
| -------------------------------- | ------------- | ----------------------- |
| `SECURE_SSL_REDIRECT`            | `True`        | Force HTTPS             |
| `SECURE_HSTS_SECONDS`            | 31536000      | HSTS for 1 year         |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True`        | Apply to subdomains     |
| `SECURE_HSTS_PRELOAD`            | `True`        | Allow preload list      |
| `SESSION_COOKIE_SECURE`          | `True`        | Cookies over HTTPS only |
| `CSRF_COOKIE_SECURE`             | `True`        | CSRF cookie HTTPS only  |
| `SECURE_CONTENT_TYPE_NOSNIFF`    | `True`        | Prevent MIME sniffing   |
| `SECURE_REFERRER_POLICY`         | `same-origin` | Control referrer        |

---

## Secrets Management

### Development

- `SECRET_KEY` auto-generated at runtime (Docker entrypoint)
- `GROQ_API_KEY` in `.env` file (gitignored)

### Production

- Uses Docker secrets mounted at `/run/secrets/`
- Never stored on disk or in environment variables visible to `docker inspect`

```bash
# Create production secrets
mkdir -p secrets
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" > secrets/django_secret_key.txt
echo "your-secure-password" > secrets/db_password.txt
chmod 600 secrets/*.txt
```

See `secrets/README.md` for details.

---

## Content Security Policy (CSP)

CSP prevents XSS attacks by controlling which resources can load.

### Stack

| Component           | Purpose                          |
| ------------------- | -------------------------------- |
| `django-csp`        | Sends CSP headers via middleware |
| Alpine.js CSP build | No `unsafe-eval` required        |
| Pre-commit check    | Blocks inline event handlers     |

### Configuration

Settings in `config/settings.py`:

```python
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'",)
# ... see settings.py for full config
```

### Testing

**Pre-commit (static analysis):**

- `csp-inline-check` hook blocks `onclick=`, `onload=`, etc.
- Run: `pre-commit run csp-inline-check --all-files`

**Browser (manual):**

1. Open DevTools → Console
2. CSP violations appear as errors
3. Check `Content-Security-Policy` header in Network tab

**Selenium (future - with Docker):**

```python
# Example: Verify no CSP violations in browser console
from selenium import webdriver

def test_no_csp_violations(live_server):
    driver = webdriver.Chrome()
    driver.get(live_server.url)

    logs = driver.get_log('browser')
    csp_errors = [l for l in logs if 'Content Security Policy' in l['message']]

    assert len(csp_errors) == 0, f"CSP violations: {csp_errors}"
    driver.quit()
```

### What's Blocked

| Blocked                   | Alternative             |
| ------------------------- | ----------------------- |
| `onclick="..."`           | `@click="..."` (Alpine) |
| `<script>inline</script>` | External JS file        |
| `javascript:` URLs        | Proper event handlers   |
| `style="..."`             | CSS classes             |
