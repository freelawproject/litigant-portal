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

---

## Site password gate

`SITE_PASSWORD` puts a password wall in front of every page (`SitePasswordMiddleware`; static, media, and `/api/` are exempt). It is temporary, and it is the only thing keeping a pre-launch portal off the open web.

**A blank value disables it.** That is the local-dev default and a silent failure anywhere else, so the `litigant_portal.E001` system check errors at startup when `DEPLOYMENT_ENV` is anything other than `dev` and the password is blank or whitespace. A failing check stops the deploy rather than serving an open site.

Unrecognized `DEPLOYMENT_ENV` values count as deployed. `settings.py` keeps an unknown value as-is and only warns, so the check tests for "not dev" rather than "qa or prod" — a typo in the environment label fails closed instead of waving the gate through.

**To take the wall down deliberately**, add the id to `SILENCED_SYSTEM_CHECKS`:

```python
SILENCED_SYSTEM_CHECKS = ["litigant_portal.E001"]
```

That makes going public an explicit, reviewable change with a name attached, rather than a secret quietly going missing.

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
