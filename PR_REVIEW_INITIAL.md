# PR Review: Layout Changes (#51)

**Reviewer:** Claude Code
**Date:** 2025-12-29
**Verdict:** Request changes

## Summary

Good implementation overall but has a potential XSS vulnerability in the markdown renderer that should be fixed before merging.

## Changes Overview

This PR adds a complete AI chat feature with streaming responses to the litigant portal. It includes:

- New `chat/` Django app with Ollama LLM provider
- SSE streaming for real-time AI responses
- Session management for authenticated and anonymous users
- Comprehensive test coverage
- Updated documentation (CLAUDE.md) and tooling (pre-commit consolidation)

## Feedback

### Issues (must fix)

1. **XSS vulnerability in `renderMarkdown`** (`static/js/chat.js:226-229`, `432-435`)

   The link regex doesn't sanitize URLs, allowing `javascript:` protocol attacks:

   ```javascript
   .replace(
     /\[([^\]]+)\]\(([^)]+)\)/g,
     '<a href="$2" ...>$1</a>'
   )
   ```

   If the LLM returns `[click](javascript:alert(document.cookie))`, it renders as a clickable XSS payload. Add URL validation:

   ```javascript
   .replace(
     /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,  // Only allow http/https
     '<a href="$2" ...>$1</a>'
   )
   ```

2. **Missing `rel="noopener noreferrer"`** (`static/js/chat.js:432-435`)

   The `homePage` component's `renderMarkdown` has `target="_blank"` without `rel="noopener"`, unlike `chatWindow` which has it. This is a tab-nabbing risk.

### Suggestions (nice to have)

1. **Code duplication** - `chatWindow` and `homePage` share ~80% identical code (`sendMessage`/`askQuestion`, `streamResponse`, `renderMarkdown`, `escapeHtml`, `getCsrfToken`). Consider extracting to a shared mixin or base component.

2. **Rate limiting** - No rate limiting on `/chat/send/` or `/chat/stream/` endpoints. Consider adding Django-ratelimit to prevent abuse.

3. **Session cleanup** - Anonymous sessions accumulate indefinitely. Consider a management command or celery task to clean old sessions.

### Questions

1. Is there a plan to handle Ollama being unavailable gracefully in the UI (e.g., show a "service unavailable" state)?

2. The `chat_service` is a singleton - is this intentional for caching the provider, or should it be request-scoped?

## Files Reviewed

| File                            | Notes                                |
| ------------------------------- | ------------------------------------ |
| `CLAUDE.md`                     | Comprehensive documentation          |
| `chat/views.py`                 | Good validation, proper auth checks  |
| `chat/services/chat_service.py` | Clean SSE implementation             |
| `chat/models.py`                | Good SQLite/PostgreSQL compatibility |
| `chat/providers/*.py`           | Clean abstraction pattern            |
| `chat/tests/test_views.py`      | Good coverage of security cases      |
| `static/js/chat.js`             | **XSS issue in renderMarkdown**      |
| `Dockerfile`                    | Tailwind v4.1.8 → v4.1.16            |
| `Makefile`                      | Simplified lint to pre-commit        |
