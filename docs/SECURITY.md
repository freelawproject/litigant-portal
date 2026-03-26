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

Secrets are read in `config/settings.py` using the `_read_secret()` helper, which follows the `_FILE` convention:

1. Check for `<VAR>_FILE` env var → read the file at that path
2. Fall back to `<VAR>` env var directly

This pattern works with Docker Compose secrets, Kubernetes secret volume mounts, and plain env vars.

### Supported secrets

| Secret           | `_FILE` variant        | Notes                                     |
| ---------------- | ---------------------- | ----------------------------------------- |
| `SECRET_KEY`     | `SECRET_KEY_FILE`      | Auto-generated in DEBUG mode if unset     |
| `OPENAI_API_KEY` | `OPENAI_API_KEY_FILE`  | Populated into `os.environ` for LiteLLM   |

### Development

- `SECRET_KEY` is auto-generated at startup when `DEBUG=true` and no key is provided (no entrypoint magic — handled in `settings.py`)
- `OPENAI_API_KEY` set in `.env` file (gitignored)
- Developers who want a stable key across container restarts can add `SECRET_KEY=some-stable-value` to `.env`

### Production

- `SECRET_KEY_FILE` points to a Docker secret mounted at `/run/secrets/django_secret_key`
- The secret is read directly in `settings.py` — never exported to the process environment
- Not visible via `/proc/<pid>/environ`, `docker inspect`, or child processes

```bash
# Create production secrets
mkdir -p secrets
python3 -c 'import secrets; print(secrets.token_urlsafe(50))' > secrets/django_secret_key.txt
chmod 600 secrets/*.txt
```

### Kubernetes

The `_FILE` convention maps directly to K8s secret volume mounts:

```yaml
volumeMounts:
  - name: django-secrets
    mountPath: /run/secrets/django_secret_key
    subPath: django_secret_key
    readOnly: true
```

Set `SECRET_KEY_FILE=/run/secrets/django_secret_key` — no code changes needed when migrating from Docker Compose to K8s.

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
