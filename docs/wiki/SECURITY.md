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

Secrets are set in the `.env` file and exported to the environment. See `.env.example` for examples.

`SECRET_KEY` is required when `DEBUG` is off: settings raise `ImproperlyConfigured` at startup instead of falling back to a random key per worker.

---

## Login Rate Limits

| Login                  | Limit                                                                     | Over the limit         |
| ---------------------- | ------------------------------------------------------------------------- | ---------------------- |
| allauth (`/accounts/`) | allauth default: 10 failures/min per IP, 5 failures per 5 min per account | allauth's own response |
| Django admin           | 10 failures/min per IP, 5 failures per 5 min per account                  | 429, "try again" page  |
| Site password gate     | 10/min per IP                                                             | 429, gate page message |

The admin and site gate limits use fixed windows, so a blocked visitor waits until the current window ends: up to 1 minute for an IP limit, up to 5 minutes for an account limit.

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

Settings in `litigant_portal/settings.py`:

```python
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", *ASSET_ORIGINS)
CSP_STYLE_SRC = ("'self'", *ASSET_ORIGINS)
# ... see settings.py for full config
```

`ASSET_ORIGINS` is the S3/CDN origin the public storage serves from in production (empty in local dev, where everything is same-origin). No third-party CDNs — all frontend assets are local files or served from our own storage.

### Testing

**Pre-commit (static analysis):**

- `csp-inline-check` hook blocks `onclick=`, `onload=`, etc.
- Run: `pre-commit run csp-inline-check --all-files`

**Browser (manual):**

1. Open DevTools → Console
2. CSP violations appear as errors
3. Check `Content-Security-Policy` header in Network tab

### What's Blocked

| Blocked                   | Alternative                 |
| ------------------------- | --------------------------- |
| `onclick="..."`           | `x-on:click="..."` (Alpine) |
| `<script>inline</script>` | External JS file            |
| `javascript:` URLs        | Proper event handlers       |
| `style="..."`             | CSS classes                 |
