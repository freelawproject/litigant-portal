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
    attachments: [],
    hasAtts: false,
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
function makeMessage(role, content, attachments) {
  const isUser = role === 'user'
  const atts = attachments || []
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
    attachments: atts,
    hasAtts: atts.length > 0,
    rowClass: isUser ? 'items-end' : 'items-start',
    bubbleClass: isUser
      ? 'bg-primary-600 text-white'
      : 'bg-greyscale-100 text-greyscale-900',
  }
}

// Chip data for an attachment shown on a sent user message.
function messageAttachment(att) {
  return {
    id: att.id,
    name: att.name,
    isImage: !!att.is_image,
    notImage: !att.is_image,
    url: att.url || '',
    sizeLabel: formatSize(att.size),
    tileClass: fileStyle(att.content_type || '').tileClass,
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
  return makeMessage(
    item.kind,
    item.content,
    (item.attachments || []).map(messageAttachment)
  )
}

const MAX_INPUT_HEIGHT = 160

// Title shown for threads that don't have a generated description yet.
const NEW_CHAT_TITLE = 'New chat'

// --- Attachments -------------------------------------------------------------

// Mirrors the backend's allowed types (services/assistant.py) so obviously bad
// files are rejected before a round trip. The server remains the authority.
const UPLOAD_EXTENSIONS = [
  '.pdf',
  '.doc',
  '.docx',
  '.xls',
  '.xlsx',
  '.txt',
  '.md',
  '.csv',
  '.rtf',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
]
const MAX_UPLOAD_SIZE = 20 * 1024 * 1024 // 20 MB

const DROPZONE_IDLE =
  'border-greyscale-300 bg-greyscale-25 hover:border-primary-400 hover:bg-primary-25'
const DROPZONE_ACTIVE = 'border-primary-500 bg-primary-50'

function formatSize(bytes) {
  if (typeof bytes !== 'number' || isNaN(bytes)) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return Math.round(bytes / 1024) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

// Badge text + tinted tile classes for non-image files, keyed by content type.
const FILE_STYLES = [
  [/pdf/, 'PDF', 'bg-red-50 text-red-600'],
  [/msword|wordprocessing/, 'DOC', 'bg-blue-50 text-blue-600'],
  [/ms-excel|spreadsheet/, 'XLS', 'bg-green-50 text-green-700'],
  [/csv/, 'CSV', 'bg-green-50 text-green-700'],
  [/markdown/, 'MD', 'bg-greyscale-100 text-greyscale-600'],
  [/rtf/, 'RTF', 'bg-greyscale-100 text-greyscale-600'],
  [/text/, 'TXT', 'bg-greyscale-100 text-greyscale-600'],
]

function fileStyle(contentType) {
  for (const [pattern, badge, tileClass] of FILE_STYLES) {
    if (pattern.test(contentType)) return { badge, tileClass }
  }
  return { badge: 'FILE', tileClass: 'bg-greyscale-100 text-greyscale-600' }
}

function uploadCardClass(selected) {
  return selected
    ? 'border-primary-500 ring-2 ring-primary-500/50 shadow-sm'
    : 'border-greyscale-200 hover:border-greyscale-300 hover:shadow-md'
}

// The per-card delete control: a small X at rest that expands into a
// red "Confirm delete" pill; clicking anywhere else collapses it.
function uploadDeleteClass(armed) {
  return (
    'absolute top-1.5 right-1.5 z-10 inline-flex items-center justify-center ' +
    'h-5 rounded-full border shadow cursor-pointer transition-all duration-150 ' +
    (armed
      ? 'px-2 bg-red-600 border-red-600 text-white'
      : 'w-5 bg-white/90 border-greyscale-200 text-greyscale-400 hover:text-red-600 hover:border-red-300')
  )
}

const DELETE_TITLE = 'Delete file'
const DELETE_ARMED_TITLE = 'Permanently delete this file'

// Precompute everything the CSP-safe template needs to render an upload card.
function decorateUpload(upload, selected) {
  return {
    ...upload,
    ...fileStyle(upload.content_type),
    isImage: upload.is_image,
    notImage: !upload.is_image,
    sizeLabel: formatSize(upload.size),
    metaLabel: formatSize(upload.size) + ' · ' + timeSince(upload.created_at),
    selected,
    cardClass: uploadCardClass(selected),
    deleteArmed: false,
    deleteIdle: true,
    deleteClass: uploadDeleteClass(false),
    deleteTitle: DELETE_TITLE,
  }
}

document.addEventListener('alpine:init', () => {
  // A single component managing every part of the chat: the history sidebar
  // and the center conversation (messages, input, streaming). The stream URL
  // is agent-specific, so the template passes it in via data-stream-url
  // (the CSP build can't evaluate x-data arguments).
  Alpine.data('chatApp', () => ({
    // Mount point of the agent's API (e.g. "/api/agents/assistant/") — the
    // component itself is agent-agnostic.
    base: '',
    // History sidebar
    threads: [],
    showEmpty: false,
    // Conversation
    messages: [],
    conversationEmpty: true,
    input: '',
    threadId: null,
    threadTitle: '',
    streaming: false,
    sendDisabled: true,
    menuOpen: false,
    confirmingDelete: false,
    thinkingVisible: false,
    // The in-flight stream context, if any. It owns the message array it
    // writes into, so switching threads mid-stream just detaches the view
    // while the stream keeps filling its own buffer in the background.
    activeStream: null,
    // Sidebar status per thread id: 'streaming' | 'unseen' (finished in
    // the background and not yet viewed).
    threadStatus: {},
    // Agent state for the active thread (pulled on load + as messages stream).
    stateData: {},
    stateJson: '',
    hasState: false,
    noState: true,
    // Attach-files modal + attachments riding on the next message.
    attachOpen: false,
    uploads: [],
    hasUploads: false,
    uploadsEmpty: false,
    pendingUploads: [],
    hasPending: false,
    pendingSeq: 0,
    uploadError: '',
    hasUploadError: false,
    dragDepth: 0,
    dropzoneClass: DROPZONE_IDLE,
    attachments: [],
    hasAttachments: false,
    uploadCountLabel: '',
    selectedLabel: '',
    attachLabel: 'Attach',
    attachDisabled: true,

    init() {
      this.base = this.$root.dataset.agentBase
      this.loadThreads()
    },

    // --- History ---

    async loadThreads() {
      try {
        const res = await fetch(this.base + 'threads/', {
          headers: { Accept: 'application/json' },
        })
        const data = await res.json()
        this.threads = (data.threads || []).map((thread) => ({
          ...thread,
          title: thread.description || NEW_CHAT_TITLE,
          relativeTime: timeSince(thread.last_at),
          rowClass: threadRowClass(thread.id, this.threadId),
          dotClass: this.threadDotClass(thread.id),
        }))
        // Pick up a freshly generated description for the active thread.
        const active = this.threads.find((t) => t.id === this.threadId)
        if (active) this.threadTitle = active.title
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

    // --- Stream/thread status ---

    // Whether the conversation view is showing this stream's thread.
    attached(stream) {
      return this.messages === stream.messages
    },

    threadDotClass(threadId) {
      const status = this.threadStatus[threadId]
      if (status === 'streaming') return 'bg-yellow-400 animate-pulse'
      if (status === 'unseen') return 'bg-green-500'
      return 'bg-greyscale-300'
    },

    setThreadStatus(threadId, status) {
      if (!threadId) return
      if (status) this.threadStatus[threadId] = status
      else delete this.threadStatus[threadId]
      this.threads.forEach((t) => {
        t.dotClass = this.threadDotClass(t.id)
      })
    },

    // --- Conversation ---

    newChat() {
      this.threadId = null
      this.threadTitle = ''
      // A fresh array detaches the view from any in-flight stream, which
      // keeps writing into its own buffer.
      this.messages = []
      this.conversationEmpty = true
      this.setState({})
      this.clearInput()
      this.clearAttachments()
      this.markActive()
      this.updateThinking()
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
          this.base + 'threads/' + this.threadId + '/delete/',
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

    // Load a thread's messages into the center conversation. If a stream
    // is running for that thread, re-attach to its live buffer instead.
    async openThread(threadId) {
      // Viewing the thread acknowledges a background-finished stream; an
      // in-progress stream keeps its yellow dot.
      if (this.threadStatus[threadId] === 'unseen') {
        this.setThreadStatus(threadId, null)
      }

      const live = this.activeStream
      if (live && live.threadId === threadId) {
        const row = this.threads.find((t) => t.id === threadId)
        this.threadId = threadId
        this.threadTitle = (row && row.title) || NEW_CHAT_TITLE
        this.messages = live.messages
        this.conversationEmpty = false
        this.clearInput()
        this.clearAttachments()
        this.markActive()
        this.updateThinking()
        this.scrollToBottom()
        return
      }

      try {
        const res = await fetch(this.base + 'threads/' + threadId + '/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.threadId = data.id
        this.threadTitle = data.description || NEW_CHAT_TITLE
        this.messages = (data.items || []).map(buildItem)
        this.setState(data.state)
        this.conversationEmpty = this.messages.length === 0
        this.clearInput()
        this.clearAttachments()
        this.markActive()
        this.updateThinking()
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

    // Send a message (optionally continuing a thread) and stream the reply
    // into the stream's own buffer — the view shows it only while attached.
    async sendMessage(message, threadId) {
      // Attachments ride on this message; the composer chips clear.
      const attachments = this.attachments
      this.clearAttachments()

      const stream = {
        threadId: threadId || null,
        messages: this.messages,
        // Index of the assistant text part receiving content, if any.
        openIndex: null,
      }
      this.activeStream = stream
      stream.messages.push(makeMessage('user', message, attachments))
      this.conversationEmpty = false
      this.streaming = true
      this.setThreadStatus(stream.threadId, 'streaming')
      this.refreshSendState()
      this.updateThinking()
      this.scrollToBottom()

      try {
        const body = new FormData()
        body.append('message', message)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        if (threadId) body.append('thread_id', threadId)
        attachments.forEach((a) => body.append('attachment_ids', a.id))

        const res = await fetch(this.base + 'stream/', {
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
              this.handleEvent(stream, JSON.parse(payload))
            } catch (e) {
              // Ignore parse errors for partial chunks.
            }
          }
        }
      } catch (e) {
        console.error('Chat stream failed:', e)
        this.appendAssistant(
          stream,
          'Sorry, something went wrong. Please try again.'
        )
      } finally {
        this.streaming = false
        // Viewed streams end quietly; backgrounded ones flag their row
        // green until the user opens the thread.
        this.setThreadStatus(
          stream.threadId,
          this.attached(stream) ? null : 'unseen'
        )
        this.activeStream = null
        this.updateThinking()
        this.refreshSendState()
        this.loadThreads()
      }
    },

    handleEvent(stream, event) {
      if (event.type === 'thread') {
        stream.threadId = event.thread_id
        this.setThreadStatus(stream.threadId, 'streaming')
        if (this.attached(stream)) {
          this.threadId = event.thread_id
          // Placeholder until the generated description arrives.
          if (!this.threadTitle) this.threadTitle = NEW_CHAT_TITLE
          this.markActive()
        }
        // Surface the new thread's row (and its dot) right away.
        this.loadThreads()
      } else if (event.type === 'content_delta') {
        this.appendContent(stream, event.content || '')
      } else if (event.type === 'tool_call') {
        // A new tool starts a fresh text run after it.
        stream.openIndex = null
        stream.messages.push(makeToolFromCall(event))
      } else if (event.type === 'tool_response') {
        this.applyToolResponse(stream, event)
      } else if (event.type === 'description') {
        if (this.attached(stream)) this.threadTitle = event.description
      } else if (event.type === 'state') {
        if (this.attached(stream)) this.setState(event.state)
      } else if (event.type === 'error') {
        this.appendAssistant(stream, event.error || 'Something went wrong.')
      }
      if (this.attached(stream)) {
        this.updateThinking()
        this.scrollToBottom()
      }
    },

    // Append streamed content to the open assistant part (creating it lazily).
    appendContent(stream, text) {
      if (stream.openIndex === null) {
        stream.messages.push(makeMessage('assistant', ''))
        stream.openIndex = stream.messages.length - 1
      }
      const msg = stream.messages[stream.openIndex]
      const content = msg.content + text
      stream.messages[stream.openIndex] = {
        ...msg,
        content,
        html: renderMarkdown(content),
      }
    },

    // Append a complete assistant message (e.g. an error) and close the run.
    appendAssistant(stream, content) {
      stream.messages.push(makeMessage('assistant', content))
      stream.openIndex = null
    },

    // Fill a pending tool part with its result once the tool finishes.
    applyToolResponse(stream, event) {
      const index = stream.messages.findIndex(
        (m) => m.isTool && m.toolId === event.id
      )
      if (index === -1) return
      const part = { ...stream.messages[index] }
      part.resultMode = event.render_mode
      part.resultHtml = event.render_html || ''
      part.renderDataJson = prettyJson(event.render_data)
      part.status = 'done'
      stream.messages[index] = computeToolFlags(part)
    },

    // Pull in agent state (on load and as the stream reports changes).
    setState(state) {
      this.stateData = state || {}
      this.stateJson = prettyJson(this.stateData)
      this.hasState = !!state && Object.keys(state).length > 0
      this.noState = !this.hasState
    },

    // Show the standalone thinking row while waiting, unless a tool spinner or
    // streaming text is already the most recent thing on screen. Only the
    // stream attached to the visible thread shows it.
    updateThinking() {
      if (
        !this.streaming ||
        !this.activeStream ||
        !this.attached(this.activeStream)
      ) {
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

    // --- Attachments ---

    async openAttach() {
      this.attachOpen = true
      this.setUploadError('')
      await this.loadUploads()
    },

    closeAttach() {
      this.attachOpen = false
      this.dragDepth = 0
      this.dropzoneClass = DROPZONE_IDLE
      this.disarmUploadDelete()
    },

    // Fetch the identity's uploads; anything already attached shows selected.
    async loadUploads() {
      try {
        const res = await fetch(this.base + 'uploads/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        const attached = new Set(this.attachments.map((a) => a.id))
        this.uploads = (data.uploads || []).map((u) =>
          decorateUpload(u, attached.has(u.id))
        )
      } catch (e) {
        console.error('Failed to load uploads:', e)
      }
      this.refreshAttachState()
    },

    // Recompute the CSP-safe labels/flags the modal binds to.
    refreshAttachState() {
      this.hasUploads = this.uploads.length > 0
      this.hasPending = this.pendingUploads.length > 0
      this.uploadsEmpty = !this.hasUploads && !this.hasPending
      this.uploadCountLabel =
        this.uploads.length === 1 ? '1 file' : this.uploads.length + ' files'
      const count = this.uploads.filter((u) => u.selected).length
      this.selectedLabel =
        count === 0
          ? 'No files selected'
          : count === 1
            ? '1 file selected'
            : count + ' files selected'
      this.attachLabel = count > 1 ? 'Attach ' + count + ' files' : 'Attach'
      // With nothing selected, Attach still works as "detach all" if there
      // are chips on the composer; otherwise it's a no-op, so disable it.
      this.attachDisabled = count === 0 && this.attachments.length === 0
    },

    setUploadError(message) {
      this.uploadError = message
      this.hasUploadError = !!message
    },

    browseFiles() {
      this.$refs.fileInput.click()
    },

    handleFileInput(e) {
      this.uploadFiles(e.target.files)
      e.target.value = ''
    },

    // Drag state uses a depth counter — dragleave fires on every child hop.
    dragEnter() {
      this.dragDepth++
      this.dropzoneClass = DROPZONE_ACTIVE
    },

    dragOver() {},

    dragLeave() {
      this.dragDepth = Math.max(0, this.dragDepth - 1)
      if (this.dragDepth === 0) this.dropzoneClass = DROPZONE_IDLE
    },

    handleDrop(e) {
      this.dragDepth = 0
      this.dropzoneClass = DROPZONE_IDLE
      if (e.dataTransfer) this.uploadFiles(e.dataTransfer.files)
    },

    // Upload files concurrently; each success lands in the grid pre-selected.
    async uploadFiles(fileList) {
      const files = Array.from(fileList || [])
      if (!files.length) return
      this.setUploadError('')
      const errors = []

      await Promise.all(
        files.map(async (file) => {
          const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
          if (!UPLOAD_EXTENSIONS.includes(ext)) {
            errors.push(file.name + ': unsupported file type')
            return
          }
          if (file.size > MAX_UPLOAD_SIZE) {
            errors.push(file.name + ': too large (max 20 MB)')
            return
          }

          const pending = {
            id: 'pending-' + ++this.pendingSeq,
            name: file.name,
          }
          this.pendingUploads.push(pending)
          this.refreshAttachState()

          try {
            const body = new FormData()
            body.append('file', file)
            body.append('csrfmiddlewaretoken', this.csrfToken())
            const res = await fetch(this.base + 'uploads/create/', {
              method: 'POST',
              body,
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.error || 'upload failed')
            this.uploads.unshift(decorateUpload(data.upload, true))
          } catch (err) {
            errors.push(file.name + ': ' + err.message)
          } finally {
            this.pendingUploads = this.pendingUploads.filter(
              (p) => p.id !== pending.id
            )
            this.refreshAttachState()
          }
        })
      )

      this.setUploadError(errors.join(' · '))
    },

    // Toggle a card's selection — the upload id rides on the element.
    toggleUpload(e) {
      this.disarmUploadDelete()
      const id = e.currentTarget.dataset.uploadId
      const upload = this.uploads.find((u) => u.id === id)
      if (!upload) return
      upload.selected = !upload.selected
      upload.cardClass = uploadCardClass(upload.selected)
      this.refreshAttachState()
    },

    // Permanent delete: first click arms the button, second click commits.
    deleteUpload(e) {
      const id = e.currentTarget.dataset.uploadId
      const upload = this.uploads.find((u) => u.id === id)
      if (!upload) return
      if (!upload.deleteArmed) {
        this.disarmUploadDelete()
        upload.deleteArmed = true
        upload.deleteIdle = false
        upload.deleteClass = uploadDeleteClass(true)
        upload.deleteTitle = DELETE_ARMED_TITLE
        return
      }
      this.confirmUploadDelete(upload)
    },

    disarmUploadDelete() {
      this.uploads.forEach((u) => {
        if (u.deleteArmed) {
          u.deleteArmed = false
          u.deleteIdle = true
          u.deleteClass = uploadDeleteClass(false)
          u.deleteTitle = DELETE_TITLE
        }
      })
    },

    async confirmUploadDelete(upload) {
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          this.base + 'uploads/' + upload.id + '/delete/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.uploads = this.uploads.filter((u) => u.id !== upload.id)
        this.attachments = this.attachments.filter((a) => a.id !== upload.id)
        this.hasAttachments = this.attachments.length > 0
        this.refreshAttachState()
      } catch (e) {
        console.error('Failed to delete upload:', e)
        this.disarmUploadDelete()
      }
    },

    // Commit the selection to the composer as chips on the next message.
    confirmAttach() {
      this.attachments = this.uploads
        .filter((u) => u.selected)
        .map((u) => ({ ...u }))
      this.hasAttachments = this.attachments.length > 0
      this.closeAttach()
    },

    // Remove a composer chip — the upload id rides on the button.
    removeAttachment(e) {
      const id = e.currentTarget.dataset.uploadId
      this.attachments = this.attachments.filter((a) => a.id !== id)
      this.hasAttachments = this.attachments.length > 0
    },

    clearAttachments() {
      this.attachments = []
      this.hasAttachments = false
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
      this.app = Alpine.$data(this.$root.closest('[x-data="chatApp"]'))
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
        const res = await fetch(
          this.app.base + 'threads/' + threadId + '/usage/',
          { headers: { Accept: 'application/json' } }
        )
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
