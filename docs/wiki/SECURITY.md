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

The allauth and admin limits run on allauth's limiter, which uses sliding windows: a blocked visitor waits until their oldest counted failure is older than the window (1 minute for the IP limit, 5 minutes for the account limit). The site gate runs on django-ratelimit, which uses fixed windows: a blocked visitor waits until the current minute's window ends.

### Which address a per-IP limit counts

Every per-IP limit, on both limiters, counts the address that `get_client_ip` in `litigant_portal/app/client_ip.py` returns. Behind CloudFront and the load balancer `REMOTE_ADDR` is a proxy address, so the helper reads the `CloudFront-Viewer-Address` header, which CloudFront sets to the visitor's `IP:port`. `X-Forwarded-For` is never read. django-ratelimit reaches the helper through `RATELIMIT_IP_META_KEY`, and allauth through `ACCOUNT_ADAPTER`.

The header is read only when `TRUST_CLOUDFRONT_VIEWER_ADDRESS=true`. It is off by default, so local dev and any instance without CloudFront ignore the header and count `REMOTE_ADDR`, and a client cannot pick its own bucket by sending one.

When the setting is on and the header is missing or is not a valid address, the helper logs a warning and returns `REMOTE_ADDR`. That warning in the logs means the limits are counting the proxy again.

Infra must keep three things true on every environment behind CloudFront:

- **`TRUST_CLOUDFRONT_VIEWER_ADDRESS=true` is set.** Without it every visitor shares the proxy's bucket.
- **CloudFront forwards `CloudFront-Viewer-Address` to the origin.** It is only sent when the origin request policy includes it. Without it every visitor shares the proxy's bucket, and one busy visitor can lock everyone out.
- **The load balancer accepts traffic only from CloudFront.** CloudFront overwrites the header on every request. A visitor who can reach the app without CloudFront can send their own value and get a fresh bucket each time.

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
