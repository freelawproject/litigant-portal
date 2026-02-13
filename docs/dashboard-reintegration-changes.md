# Dashboard Reintegration Changes

**Branch:** `dashboard-recovery`
**Base commit:** `f696b35`
**Date:** 2026-02-13

## Overview

Moved the chat-first interface from `/` to `/chat/`, restored the dashboard (hero + topic grid) as the root view, and moved the chat API from `/chat/` to `/api/chat/`.

## Files Modified

| File                                  | Action                                                                                                                      | Rollback                                              |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `config/urls.py`                      | Changed `chat/` → `api/chat/`                                                                                               | Revert prefix back to `chat/`                         |
| `static/js/chat.js`                   | Updated 4 fetch URLs to `/api/chat/...`                                                                                     | Remove `/api` prefix from fetch URLs                  |
| `chat/tests/test_views.py`            | Updated hardcoded paths to `/api/chat/...`                                                                                  | Remove `/api` prefix from test paths                  |
| `templates/base.html`                 | Added `body_class` block, removed `overflow-hidden` from default                                                            | Restore `overflow-hidden` to body class, remove block |
| `templates/pages/home.html`           | Replaced with dashboard layout (hero + topic-grid)                                                                          | Restore chat-first content (see `chat.html`)          |
| `templates/pages/chat.html`           | Replaced with full chat interface from old `home.html`                                                                      | Restore old standalone chat page                      |
| `templates/pages/dashboard_demo.html` | Deleted                                                                                                                     | Recreate from git history (`df44766`)                 |
| `portal/views.py`                     | Added `chat_page`, updated `test_agent` template, removed `dashboard_demo`                                                  | Revert view changes                                   |
| `portal/urls.py`                      | Added `/chat/` route, removed `/dashboard-demo/`                                                                            | Revert URL patterns                                   |
| `portal/tests.py`                     | Added dashboard/chat route tests, removed 12 allauth/library tests, added 5 focused tests (footer, body_class, agent route) | Revert test changes                                   |

## Rollback

To fully revert all changes:

```bash
git revert <merge-commit-sha>
```

Or to revert individual files:

```bash
git checkout f696b35 -- <file-path>
```
