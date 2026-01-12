# AI Chat Architecture: Research & Comparison

## Current Implementation

**Stack:** Django `StreamingHttpResponse` + SSE + Alpine.js (~200 lines JS)

```
POST /chat/send/     → Creates message, returns session_id
GET /chat/stream/    → SSE stream via StreamingHttpResponse
```

**How it works:**

- Alpine.js intercepts form submit, POSTs message
- Django returns `StreamingHttpResponse` with `text/event-stream`
- Alpine.js reads stream with Fetch API, updates UI progressively
- No WebSockets, no Django Channels - just standard HTTP

---

## Alternative 1: Django Channels + WebSockets

**What it is:** Full WebSocket support via Django Channels (ASGI extension)

### Requires

- `channels` + `channels_redis` packages
- Redis server for channel layer
- ASGI server (Uvicorn/Daphne instead of Gunicorn)
- Custom `WebsocketConsumer` classes
- Convert from WSGI to ASGI application

### Pros

- **Bidirectional:** Server can push anytime (typing indicators, presence)
- **Mature ecosystem:** Well-documented, production-tested
- **Stay in Django:** Uses Django ORM, auth, templates
- **Room support:** Built-in group messaging for multi-user chat

### Cons

- **Significant complexity:** 3-4x more infrastructure (Redis, ASGI, consumers)
- **Overkill for this use case:** Only need server→client (SSE handles this)
- **Operational burden:** Redis adds another service to monitor
- **Blocking I/O concerns:** Need `AsyncWebsocketConsumer` for concurrent users
- **Connection state management:** Must handle reconnects, timeouts

### Verdict

**Not recommended.** This chat is request→response with streamed reply. WebSockets add complexity without benefit. WebSockets shine for truly bidirectional features (collaborative editing, presence, typing indicators).

---

## Alternative 2: FastAPI as Microservice

**What it is:** Separate FastAPI service handling chat/streaming, Django handles everything else

### Requires

- FastAPI application (separate codebase or embedded)
- Shared database access or API calls between services
- CORS configuration
- Deployment of two services

### Pros

- **Native async:** Built for async/await, excellent streaming performance
- **High throughput:** Handles thousands of concurrent streams efficiently
- **Type safety:** Pydantic models, OpenAPI docs automatic
- **Modern Python:** Cleaner async code than Django

### Cons

- **Two applications to maintain:** Separate deployments, configs, logs
- **Auth sharing complexity:** JWT/session sharing between Django and FastAPI
- **Database coordination:** Either duplicate models or API calls
- **Overkill for this scale:** Adds operational complexity for marginal gains
- **Team learning curve:** Different patterns, different framework

### Verdict

**Not recommended for current scale.** FastAPI excels at high-throughput async services, but this chat doesn't need thousands of concurrent streams. The complexity of running two services outweighs benefits. Consider FastAPI if later needing a dedicated AI/ML microservice with heavy concurrent load.

---

## Alternative 3: HTMX + SSE (Minimal/No Custom JS)

**What it is:** Replace Alpine.js with HTMX's SSE extension for streaming

### Requires

- HTMX library (~14kb gzipped)
- HTMX SSE extension
- Server-side HTML rendering of streamed content

### How it works

```html
<div
  hx-ext="sse"
  sse-connect="/chat/stream/{{ session_id }}/"
  sse-swap="message"
>
  <!-- HTMX auto-swaps incoming HTML -->
</div>
```

### Pros

- **Minimal JavaScript:** Declarative HTML attributes, no custom JS
- **Django template friendly:** Server renders HTML, client just swaps
- **Simpler mental model:** HTML-centric, less JS debugging
- **Hypermedia approach:** Aligns with Django's server-rendered philosophy

### Cons

- **Still uses JavaScript:** HTMX is JavaScript, just abstracted
- **Token-by-token streaming harder:** HTMX swaps expect complete HTML chunks
- **Markdown rendering:** Must happen server-side (needed anyway for CSP)
- **Less control:** Alpine.js gives finer UI state control (loading spinners, animations)
- **Extension dependency:** SSE moved to extension in HTMX 2.0

### Implementation challenges

1. Current streaming sends raw tokens: `{"token": "word"}`
2. HTMX expects HTML chunks to swap
3. Would need to either:
   - Buffer tokens server-side, send rendered HTML chunks
   - Use HTMX's `beforeSwap` for custom handling (back to writing JS)

### Verdict

**Marginal benefit.** Would replace ~200 lines of well-structured Alpine.js with HTMX, but still need JavaScript for the streaming UX. HTMX shines for form submissions and partial page updates, less so for token-by-token streaming.

---

## Alternative 4: Keep SSE, Server-Side Markdown

**What it is:** Current architecture with one key improvement

### Change

Move markdown rendering from client (`x-html` + Alpine.js) to server (Python):

```python
# In stream_response
import markdown
rendered_html = markdown.markdown(accumulated_text)
yield f'data: {{"html": "{escape(rendered_html)}"}}\n\n'
```

### Benefits

- **CSP-safe:** Can use Alpine.js CSP build
- **Same architecture:** No infrastructure changes
- **Simpler client:** `x-text` instead of `x-html` for most content
- **Security:** Server controls what HTML is rendered

### Verdict

**Recommended improvement to current approach.**

---

## Recommendation Summary

| Approach               | Complexity | Benefit        | Recommendation |
| ---------------------- | ---------- | -------------- | -------------- |
| Current (SSE + Alpine) | Low        | Works well     | **Keep**       |
| Django Channels        | High       | Overkill       | Skip           |
| FastAPI microservice   | High       | Wrong scale    | Skip           |
| HTMX SSE               | Medium     | Marginal       | Optional       |
| Server-side markdown   | Low        | CSP + Security | **Do this**    |

### Recommendation

**Keep the current SSE + Alpine.js architecture.** It's:

- Simple and working
- Standard HTTP (easy to debug, deploy, cache)
- No additional infrastructure (no Redis, no ASGI conversion)
- Matches 2025 trends (SSE is having a "comeback")

**One improvement worth doing:** Move markdown rendering server-side to enable CSP build of Alpine.js.

---

## Implementation Notes: Server-Side Markdown for CSP

When ready to switch to Alpine.js CSP build, here's the implementation plan:

### Why This Matters

- Current: `x-html` with client-side `renderMarkdown()` requires Alpine standard build
- CSP build: No `x-html` allowed (evaluates strings as HTML)
- Solution: Render markdown server-side, send HTML, use safe DOM insertion

### Files to Modify

| File                                          | Change                                               |
| --------------------------------------------- | ---------------------------------------------------- |
| `chat/services/chat_service.py`               | Add markdown rendering in `stream_response()`        |
| `static/js/chat.js`                           | Remove `renderMarkdown()`, receive pre-rendered HTML |
| `static/js/alpine.min.js`                     | Replace with CSP build                               |
| `templates/cotton/organisms/chat_window.html` | Update binding                                       |

### Step 1: Add Python Markdown Rendering

```bash
uv add markdown bleach
```

**chat/services/chat_service.py:**

```python
import markdown
import bleach

# Allowlist for security (same restrictions as client)
ALLOWED_TAGS = ['p', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'h3', 'h4', 'br']
ALLOWED_ATTRS = {'a': ['href', 'class', 'target', 'rel']}

def render_markdown_safe(text: str) -> str:
    """Render markdown to HTML with security restrictions."""
    # Strip LLM artifacts (same as client)
    text = re.sub(r'\\+', '', text)  # Backslash escapes
    text = re.sub(r'<!--.*?-->', '', text)  # HTML comments

    # Render markdown
    html = markdown.markdown(text, extensions=['nl2br'])

    # Sanitize HTML (only allow safe tags/attrs)
    html = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True
    )

    # Validate links (https only)
    html = re.sub(
        r'href="(?!https://)[^"]*"',
        'href="#"',
        html
    )

    return html
```

### Step 2: Modify Stream Response

**chat/services/chat_service.py** - in `event_stream()`:

```python
def event_stream() -> Iterator[str]:
    full_response: list[str] = []

    try:
        provider = get_provider()
        messages = self.build_message_history(session)
        context = None

        for token in provider.stream_response(messages, context):
            full_response.append(token)
            accumulated = "".join(full_response)

            # Render markdown server-side
            rendered_html = render_markdown_safe(accumulated)

            # Send rendered HTML instead of raw token
            data = json.dumps({"html": rendered_html})
            yield f"data: {data}\n\n"

        # Save raw content (not HTML) to database
        Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content="".join(full_response),  # Raw markdown
        )
        yield "data: [DONE]\n\n"
    # ... error handling unchanged
```

### Step 3: Simplify Client-Side JS

**static/js/chat.js:**

```javascript
const chatUtils = {
  // ... keep escapeHtml, getCsrfToken, checkAvailability

  // REMOVE renderMarkdown() entirely

  // Modify parseStream to handle HTML
  async parseStream(response, onHtml, onError) {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          if (data === '[DONE]') return

          try {
            const parsed = JSON.parse(data)
            if (parsed.html) {
              onHtml(parsed.html) // Pre-rendered HTML
            } else if (parsed.error && parsed.message) {
              onHtml(parsed.message)
            }
          } catch (e) {}
        }
      }
    }
  },
}
```

### Step 4: Update Template Binding

**templates/cotton/organisms/chat_window.html:**

Option A - innerHTML (simpler, still CSP-safe since HTML comes from server):

```html
<div x-ref="messageContent"></div>

<!-- In Alpine component, after receiving HTML: -->
this.$refs.messageContent.innerHTML = html
```

Option B - Use a web component or sanitized insertion method

### Step 5: Replace Alpine.js with CSP Build

```bash
# Download CSP build
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js" \
  -o static/js/alpine.min.js
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.js" \
  -o static/js/alpine.js
```

### Testing Checklist

- [ ] Markdown renders: bold, italic, lists, headers, links
- [ ] Links only allow `https://` (no `javascript:`)
- [ ] XSS payloads in LLM response are sanitized
- [ ] Streaming still feels responsive (re-rendering full markdown each token)
- [ ] Error messages still display
- [ ] Existing chat history displays correctly

### Performance Consideration

Re-rendering full markdown on each token is slightly more CPU on server, but:

- `markdown` library is fast for short content
- Typical response is <2KB, renders in <1ms
- Acceptable tradeoff for CSP security

### Alternative: Hybrid Approach

If performance becomes an issue, send both:

```python
data = json.dumps({
    "token": token,           # For accumulation
    "html": rendered_html     # For display
})
```

Client accumulates tokens for history, uses `html` for display.

---

## Sources

- [Django WebSockets with ChatGPT, Channels & HTMX](https://www.saaspegasus.com/guides/django-websockets-chatgpt-channels-htmx/)
- [SSE's Glorious Comeback: Why 2025 is the Year of Server-Sent Events](https://portalzine.de/sses-glorious-comeback-why-2025-is-the-year-of-server-sent-events/)
- [Django Channels SSE with HTMX](https://www.techblog.moebius.space/posts/2024-04-20-sse-with-django-channels-and-htmx/)
- [FastAPI vs Django for AI Applications](https://medium.com/@arpit.singhal57/django-vs-fastapi-for-building-generative-ai-applications-65b2bd31bf76)
- [FastAPI vs Django in 2025](https://capsquery.com/blog/fastapi-vs-django-in-2025-which-is-best-for-ai-driven-web-apps/)
