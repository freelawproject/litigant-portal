// Format an ISO timestamp as a coarse "time since", e.g. "5 minutes ago".
function timeSince(input) {
  const then = new Date(input).getTime()
  if (isNaN(then)) return ''

  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000))
  const units = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ]

  for (const [name, secs] of units) {
    const value = Math.floor(seconds / secs)
    if (value >= 1) {
      return value + ' ' + name + (value === 1 ? '' : 's') + ' ago'
    }
  }
  return 'just now'
}

window.timeSince = timeSince

// --- Minimal, safe markdown renderer ---------------------------------------
// Everything is HTML-escaped before any markup is added, so LLM output can
// never inject HTML. Links are restricted to http(s)/mailto schemes.

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderInline(text) {
  // Split on inline code spans so their contents are never treated as markdown.
  const parts = escapeHtml(text).split(/(`[^`]+`)/)
  return parts
    .map((part) => {
      if (part.length > 1 && part[0] === '`' && part[part.length - 1] === '`') {
        return '<code>' + part.slice(1, -1) + '</code>'
      }
      return part
        .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, label, url) => {
          const safe = /^(https?:|mailto:)/i.test(url) ? url : '#'
          return (
            '<a href="' +
            safe +
            '" target="_blank" rel="noopener noreferrer" class="text-primary-700 underline hover:no-underline">' +
            label +
            '</a>'
          )
        })
        .replace(
          /\*\*([^*]+)\*\*/g,
          '<strong class="font-semibold">$1</strong>'
        )
        .replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>')
    })
    .join('')
}

function renderMarkdown(md) {
  if (!md) return ''
  const lines = md.split('\n')
  const out = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block.
    if (/^\s*```/.test(line)) {
      const code = []
      i++
      while (i < lines.length && !/^\s*```/.test(lines[i])) {
        code.push(lines[i])
        i++
      }
      i++ // closing fence
      out.push(
        '<pre class="my-2 p-3 rounded-lg bg-greyscale-50 border border-greyscale-200 overflow-x-auto"><code>' +
          escapeHtml(code.join('\n')) +
          '</code></pre>'
      )
      continue
    }

    // Heading (# .. ######) → emphasized line.
    const h = /^(#{1,6})\s+(.*)$/.exec(line)
    if (h) {
      out.push(
        '<p class="font-semibold mt-2 mb-1 first:mt-0">' +
          renderInline(h[2]) +
          '</p>'
      )
      i++
      continue
    }

    // Blockquote.
    if (/^\s*>\s?/.test(line)) {
      const quote = []
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ''))
        i++
      }
      out.push(
        '<blockquote class="border-l-2 border-greyscale-300 pl-3 my-2 text-base text-greyscale-600">' +
          renderInline(quote.join(' ')) +
          '</blockquote>'
      )
      continue
    }

    // Unordered list.
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(
          '<li>' + renderInline(lines[i].replace(/^\s*[-*]\s+/, '')) + '</li>'
        )
        i++
      }
      out.push(
        '<ul class="list-disc pl-5 my-2 space-y-0.5">' +
          items.join('') +
          '</ul>'
      )
      continue
    }

    // Ordered list.
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(
          '<li>' + renderInline(lines[i].replace(/^\s*\d+\.\s+/, '')) + '</li>'
        )
        i++
      }
      out.push(
        '<ol class="list-decimal pl-5 my-2 space-y-0.5">' +
          items.join('') +
          '</ol>'
      )
      continue
    }

    // Blank line.
    if (/^\s*$/.test(line)) {
      i++
      continue
    }

    // Paragraph — gather until a blank line or a block starter.
    const para = []
    while (
      i < lines.length &&
      !/^\s*$/.test(lines[i]) &&
      !/^\s*```/.test(lines[i]) &&
      !/^#{1,6}\s/.test(lines[i]) &&
      !/^\s*>\s?/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])
    ) {
      para.push(lines[i])
      i++
    }
    out.push(
      '<p class="my-1.5 first:mt-0 last:mb-0 leading-relaxed">' +
        renderInline(para.join('\n')).replace(/\n/g, '<br>') +
        '</p>'
    )
  }

  return out.join('')
}

// Active-row accent for the history sidebar — a red border when selected,
// a reserved transparent border otherwise (so there's no layout shift).
function threadRowClass(threadId, activeId) {
  return threadId === activeId
    ? 'border-primary-500'
    : 'border-transparent hover:bg-greyscale-100'
}

function blankMessage() {
  return {
    id: 0,
    content: '',
    html: '',
    isUser: false,
    isAssistant: false,
    isTool: false,
    notTool: true,
    copied: false,
    notCopied: true,
    rowClass: '',
    bubbleClass: '',
    name: '',
    pending: false,
    argsJson: '',
    callHtml: '',
    renderDataJson: '',
    resultHtml: '',
    showCallCustom: false,
    showCallDefault: false,
    showResultCustom: false,
    showResultDefault: false,
  }
}

// Build a message with precomputed style classes + rendered markdown (CSP-safe
// — the template binds dot-paths only, no expressions).
let messageSeq = 0
function makeMessage(role, content) {
  const isUser = role === 'user'
  return {
    ...blankMessage(),
    id: ++messageSeq,
    role,
    content,
    html: isUser ? '' : renderMarkdown(content),
    isUser,
    isAssistant: !isUser,
    thinking: false,
    notThinking: true,
    copied: false,
    notCopied: true,
    isTool: false,
    notTool: true,
    rowClass: isUser ? 'items-end' : 'items-start',
    bubbleClass: isUser
      ? 'bg-primary-600 text-white'
      : 'bg-greyscale-100 text-greyscale-900',
  }
}

// Pretty-print a value for a "slick JSON box". Empty/undefined -> ''.
function prettyJson(value) {
  if (value === null || value === undefined) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch (e) {
    return String(value)
  }
}

// Precompute the CSP-safe visibility booleans for a tool part. The default
// JSON boxes persist; a custom call card (spinner) shows only while in flight.
function computeToolFlags(t) {
  const calling = t.status === 'calling'
  const done = t.status === 'done'
  t.isTool = true
  t.notTool = false
  t.isUser = false
  t.isAssistant = false
  t.pending = calling
  t.showCallCustom = t.callMode === 'custom' && calling
  t.showCallDefault = t.callMode === 'default'
  t.showResultCustom = done && t.resultMode === 'custom'
  t.showResultDefault = done && t.resultMode === 'default'
  return t
}

// A tool part from a live `tool_call` event (result fills in later).
function makeToolFromCall(event) {
  return computeToolFlags({
    ...blankMessage(),
    id: ++messageSeq,
    toolId: event.id,
    name: event.name,
    argsJson: prettyJson(event.args || {}),
    callMode: event.render_mode,
    callHtml: event.render_html || '',
    resultMode: 'pending',
    resultHtml: '',
    renderDataJson: '',
    status: 'calling',
    rowClass: 'items-start',
  })
}

// A completed tool part from a reloaded thread's render item.
function makeToolFromItem(item) {
  return computeToolFlags({
    ...blankMessage(),
    id: ++messageSeq,
    toolId: item.id,
    name: item.name,
    argsJson: prettyJson(item.args || {}),
    callMode: item.call_render_mode,
    callHtml: item.call_render_html || '',
    resultMode: item.result_render_mode,
    resultHtml: item.result_render_html || '',
    renderDataJson: prettyJson(item.render_data),
    status: 'done',
    rowClass: 'items-start',
  })
}

// Build a render item (from the reload endpoint) into a message/tool part.
function buildItem(item) {
  if (item.kind === 'tool') return makeToolFromItem(item)
  return makeMessage(item.kind, item.content)
}

const MAX_INPUT_HEIGHT = 160

document.addEventListener('alpine:init', () => {
  // A single component managing every part of the chat: the history sidebar
  // and the center conversation (messages, input, streaming).
  Alpine.data('chatApp', () => ({
    // History sidebar
    threads: [],
    showEmpty: false,
    // Conversation
    messages: [],
    conversationEmpty: true,
    input: '',
    threadId: null,
    streaming: false,
    sendDisabled: true,
    menuOpen: false,
    confirmingDelete: false,
    thinkingVisible: false,
    // Index of the assistant text part currently receiving content, if any.
    openAssistantIndex: null,
    // Agent state for the active thread (pulled on load + as messages stream).
    stateData: {},
    stateJson: '',
    hasState: false,
    noState: true,

    init() {
      this.loadThreads()
    },

    // --- History ---

    async loadThreads() {
      try {
        const res = await fetch('/api/chat/threads/', {
          headers: { Accept: 'application/json' },
        })
        const data = await res.json()
        this.threads = (data.threads || []).map((thread) => ({
          ...thread,
          relativeTime: timeSince(thread.last_at),
          rowClass: threadRowClass(thread.id, this.threadId),
        }))
      } catch (e) {
        console.error('Failed to load chat history:', e)
      }
      this.showEmpty = this.threads.length === 0
    },

    // Recompute which history row reads as active.
    markActive() {
      this.threads.forEach((t) => {
        t.rowClass = threadRowClass(t.id, this.threadId)
      })
    },

    // --- Conversation ---

    newChat() {
      this.threadId = null
      this.messages = []
      this.conversationEmpty = true
      this.openAssistantIndex = null
      this.thinkingVisible = false
      this.setState({})
      this.clearInput()
      this.markActive()
    },

    toggleMenu() {
      this.menuOpen = !this.menuOpen
    },

    closeMenu() {
      this.menuOpen = false
    },

    // Open the delete-confirmation modal for the active thread.
    deleteThread() {
      if (!this.threadId) return
      this.closeMenu()
      this.confirmingDelete = true
    },

    cancelDelete() {
      this.confirmingDelete = false
    },

    // Confirmed delete — remove the thread and reset to a fresh conversation.
    async confirmDelete() {
      if (!this.threadId) return
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/chat/threads/' + this.threadId + '/delete/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.confirmingDelete = false
        this.newChat()
        this.loadThreads()
      } catch (e) {
        console.error('Failed to delete thread:', e)
      }
    },

    // Click handler for a history row — the thread id rides on the element.
    selectThread(e) {
      this.openThread(e.currentTarget.dataset.threadId)
    },

    // Load a thread's messages into the center conversation.
    async openThread(threadId) {
      if (this.streaming) return
      try {
        const res = await fetch('/api/chat/threads/' + threadId + '/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.threadId = data.id
        this.messages = (data.items || []).map(buildItem)
        this.setState(data.state)
        this.conversationEmpty = this.messages.length === 0
        this.openAssistantIndex = null
        this.clearInput()
        this.markActive()
        this.scrollToBottom()
      } catch (e) {
        console.error('Failed to load thread:', e)
      }
    },

    // --- Input ---

    updateInput(e) {
      this.input = e.target.value
      this.autoResize(e.target)
      this.refreshSendState()
    },

    // The send button is disabled while streaming or when the input is empty.
    refreshSendState() {
      this.sendDisabled = this.streaming || !this.input.trim()
    },

    handleKeydown(e) {
      // Enter sends; Shift+Enter inserts a newline.
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        this.send()
      }
    },

    autoResize(el) {
      if (!el) return
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, MAX_INPUT_HEIGHT) + 'px'
    },

    clearInput() {
      this.input = ''
      this.refreshSendState()
      this.$nextTick(() => this.autoResize(this.$refs.input))
    },

    send() {
      const message = this.input.trim()
      if (!message || this.streaming) return
      this.clearInput()
      this.sendMessage(message, this.threadId)
    },

    // Send a message (optionally continuing a thread) and stream the reply.
    async sendMessage(message, threadId) {
      this.messages.push(makeMessage('user', message))
      this.conversationEmpty = false
      this.streaming = true
      this.openAssistantIndex = null
      this.refreshSendState()
      this.updateThinking()
      this.scrollToBottom()

      try {
        const body = new FormData()
        body.append('message', message)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        if (threadId) body.append('thread_id', threadId)

        const res = await fetch('/api/chat/chat-stream/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const payload = line.slice(6).trim()
            if (!payload) continue
            try {
              this.handleEvent(JSON.parse(payload))
            } catch (e) {
              // Ignore parse errors for partial chunks.
            }
          }
        }
      } catch (e) {
        console.error('Chat stream failed:', e)
        this.appendAssistant('Sorry, something went wrong. Please try again.')
      } finally {
        this.streaming = false
        this.openAssistantIndex = null
        this.updateThinking()
        this.refreshSendState()
        this.loadThreads()
      }
    },

    handleEvent(event) {
      if (event.type === 'thread') {
        this.threadId = event.thread_id
        this.markActive()
      } else if (event.type === 'content_delta') {
        this.appendContent(event.content || '')
      } else if (event.type === 'tool_call') {
        // A new tool starts a fresh text run after it.
        this.openAssistantIndex = null
        this.messages.push(makeToolFromCall(event))
      } else if (event.type === 'tool_response') {
        this.applyToolResponse(event)
      } else if (event.type === 'state') {
        this.setState(event.state)
      } else if (event.type === 'error') {
        this.appendAssistant(event.error || 'Something went wrong.')
      }
      this.updateThinking()
      this.scrollToBottom()
    },

    // Append streamed content to the open assistant part (creating it lazily).
    appendContent(text) {
      if (this.openAssistantIndex === null) {
        this.messages.push(makeMessage('assistant', ''))
        this.openAssistantIndex = this.messages.length - 1
      }
      const index = this.openAssistantIndex
      const msg = this.messages[index]
      const content = msg.content + text
      this.messages[index] = {
        ...msg,
        content,
        html: renderMarkdown(content),
      }
    },

    // Append a complete assistant message (e.g. an error) and close the run.
    appendAssistant(content) {
      this.messages.push(makeMessage('assistant', content))
      this.openAssistantIndex = null
    },

    // Fill a pending tool part with its result once the tool finishes.
    applyToolResponse(event) {
      const index = this.messages.findIndex(
        (m) => m.isTool && m.toolId === event.id
      )
      if (index === -1) return
      const part = { ...this.messages[index] }
      part.resultMode = event.render_mode
      part.resultHtml = event.render_html || ''
      part.renderDataJson = prettyJson(event.render_data)
      part.status = 'done'
      this.messages[index] = computeToolFlags(part)
    },

    // Pull in agent state (on load and as the stream reports changes).
    setState(state) {
      this.stateData = state || {}
      this.stateJson = prettyJson(this.stateData)
      this.hasState = !!state && Object.keys(state).length > 0
      this.noState = !this.hasState
    },

    // Show the standalone thinking row while waiting, unless a tool spinner or
    // streaming text is already the most recent thing on screen.
    updateThinking() {
      if (!this.streaming) {
        this.thinkingVisible = false
        return
      }
      const last = this.messages[this.messages.length - 1]
      if (last && last.isTool && last.status === 'calling') {
        this.thinkingVisible = false
        return
      }
      if (last && last.isAssistant && last.content) {
        this.thinkingVisible = false
        return
      }
      this.thinkingVisible = true
    },

    // Copy a message's text — the message id rides on the button.
    copyMessage(e) {
      const id = Number(e.currentTarget.dataset.messageId)
      const message = this.messages.find((m) => m.id === id)
      if (!message) return
      if (navigator.clipboard) navigator.clipboard.writeText(message.content)
      message.copied = true
      message.notCopied = false
      setTimeout(() => {
        message.copied = false
        message.notCopied = true
      }, 1500)
    },

    csrfToken() {
      const input = document.querySelector('[name=csrfmiddlewaretoken]')
      return input ? input.value : ''
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const el = this.$refs.messagesArea
        if (el) el.scrollTop = el.scrollHeight
      })
    },
  }))

  // Superuser-only token/cost readout for the active thread. Rendered only for
  // superusers (so non-superusers never instantiate it or hit the endpoint).
  // Assumes it lives inside a chatApp component — it reads the thread id from
  // the parent and refreshes when the thread changes or a turn finishes.
  Alpine.data('chatUsage', () => ({
    totalTokens: '0',
    totalCost: '$0.00',
    app: null,

    init() {
      this.app = this.$root.closest('[x-data="chatApp"]')._x_dataStack[0]
      this.$watch('app.threadId', () => this.refresh())
      this.$watch('app.streaming', (streaming) => {
        if (!streaming) this.refresh()
      })
      this.refresh()
    },

    async refresh() {
      const threadId = this.app && this.app.threadId
      if (!threadId) {
        this.totalTokens = '0'
        this.totalCost = '$0.00'
        return
      }
      try {
        const res = await fetch('/api/chat/threads/' + threadId + '/usage/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) return
        const data = await res.json()
        this.totalTokens = (data.total_tokens || 0).toLocaleString()
        this.totalCost = '$' + (data.total_cost || 0).toFixed(4)
      } catch (e) {
        console.error('Failed to load chat usage:', e)
      }
    },
  }))
})
