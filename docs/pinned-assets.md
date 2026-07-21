# Pinned Frontend Assets

All frontend assets are local files, not CDN (org standard). Update these in sync when upgrading:

| Tool         | Version            | Location                                                                                 |
| ------------ | ------------------ | ---------------------------------------------------------------------------------------- |
| Tailwind CSS | v4.1.16 (CLI)      | `docker/django/Dockerfile` (`TAILWIND_VERSION` arg)                                      |
| Alpine.js    | 3.14.9 (CSP build) | `litigant_portal/app/static/js/alpine.js`, `litigant_portal/app/static/js/alpine.min.js` |
| Chat model   | openai/gpt-4o-mini | `CHAT_MODEL` env var (docker-compose.yml, .env) — local-dev default; deployed sites resolve their model from admin site config |

## Updating Alpine.js (CSP build)

Both files ship in the repo — the non-minified build is auto-selected when `DEBUG=True`:

```bash
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.js" -o litigant_portal/app/static/js/alpine.js
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js" -o litigant_portal/app/static/js/alpine.min.js
```

## Updating Tailwind

Bump the `TAILWIND_VERSION` arg in `docker/django/Dockerfile`, rebuild the image (`make docker-build`), and rebuild CSS (`make css`).
