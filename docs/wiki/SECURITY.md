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

## Dependency and Code Scanning

| Check      | What it reads                                   | When it runs                  | What it blocks                |
| ---------- | ----------------------------------------------- | ----------------------------- | ----------------------------- |
| `audit`    | The packages the image installs, from `uv.lock` | Every PR, every deploy, daily | The deploy                    |
| CodeQL     | Our own Python and JavaScript                   | Every PR, and on a schedule   | Nothing. It reports on the PR |
| Dependabot | All `uv.lock` files, actions, pre-commit hooks  | On each advisory, and monthly | Nothing. It opens a PR        |

Run the audit locally with `make audit`. It is the same script CI runs (`scripts/audit_deps.sh`).

The audit does not see the Debian packages in the image or the JavaScript files we vendor.

### When the audit fails

A failure means a package we ship has a published advisory. It can appear on a PR that did not touch dependencies, because advisories are published every day.

1. **Upgrade the package.** `uv lock --upgrade-package <name>`. If a parent package holds it back, add a floor to the "Security minimums" block in `pyproject.toml` and run `uv lock`.
2. **If there is no fixed version, or the upgrade cannot land today, ignore that one advisory.** Add its ID to `IGNORED` in `scripts/audit_deps.sh` with a comment: the date, your name, why it is safe for us, and a review date.
3. **Remove the entry** when the fixed version is in `uv.lock`.

An ignore entry goes through a normal PR and needs the normal one approval. For an urgent fix, put the entry in the same PR as the fix.

The ignore list is the only override. Do not add a skip label, mark the job `continue-on-error`, or remove `audit` from a deploy job's `needs`. Each of those turns the gate off for every advisory and records no reason.

---

## Content Security Policy (CSP)

CSP prevents XSS attacks by controlling which resources can load.

### Stack

| Component                         | Purpose                                |
| --------------------------------- | -------------------------------------- |
| `ContentSecurityPolicyMiddleware` | Sends the CSP header (Django built-in) |
| `/api/csp-report/`                | Logs violation reports from browsers   |
| Alpine.js CSP build               | No `unsafe-eval` required              |
| Pre-commit check                  | Blocks inline event handlers           |

### Configuration

Settings in `litigant_portal/settings.py`:

```python
_csp_policy = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, *ASSET_ORIGINS],
    "style-src": [CSP.SELF, *ASSET_ORIGINS],
    # ... see settings.py for full config
    "report-uri": ["/api/csp-report/"],
}
if CSP_ENFORCED:
    SECURE_CSP = _csp_policy
else:
    SECURE_CSP_REPORT_ONLY = _csp_policy
```

The policy is report-only by default: the browser sends `Content-Security-Policy-Report-Only`, logs violations, and blocks nothing. Set `CSP_ENFORCED=true` in an instance's environment to send the enforcing `Content-Security-Policy` header instead.

`ASSET_ORIGINS` is the S3/CDN origin the public storage serves from when `USE_S3` is on (empty with local storage, where everything is same-origin). No third-party CDNs — all frontend assets are local files or served from our own storage.

### Testing

**Pre-commit (static analysis):**

- `csp-inline-check` hook blocks `onclick=`, `onload=`, etc.
- Run: `pre-commit run csp-inline-check --all-files`

**Browser (manual):**

1. Open DevTools → Console
2. CSP violations appear as errors (as warnings while report-only)
3. Check the `Content-Security-Policy-Report-Only` header (or `Content-Security-Policy` when enforced) in the Network tab

**Violation reports (server logs):**

Browsers POST each violation to `/api/csp-report/`, which writes one `CSP violation` line through `lp_logger` to stdout. It keeps only what's needed to fix the policy: the directive, the blocked origin (or `inline`, `eval`, `data`, `blob`), the page path, and the source file and line. Query strings, referrers, and code samples are dropped. Read them with `docker compose logs django` locally, or the pod logs on an instance.

### What's Blocked

| Blocked                   | Alternative                 |
| ------------------------- | --------------------------- |
| `onclick="..."`           | `x-on:click="..."` (Alpine) |
| `<script>inline</script>` | External JS file            |
| `javascript:` URLs        | Proper event handlers       |
| `style="..."`             | CSS classes                 |
