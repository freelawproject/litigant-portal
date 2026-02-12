/**
 * Chat Utilities
 */
const chatUtils = {
  getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]')
    if (input) return input.value

    const cookies = document.cookie.split(';')
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split('=')
      if (name === 'csrftoken') return value
    }
    return ''
  },

  escapeHtml(text) {
    if (!text) return ''
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
  },

  // Simple markdown to HTML renderer
  // SECURITY: HTML must be escaped BEFORE markdown transformations to prevent XSS.
  // LLM output may contain malicious content - escaping first neutralizes it.
  renderMarkdown(text) {
    if (!text) return ''
    return (
      text
        // Strip LLM artifacts
        .replace(/\\+/g, '') // Backslash escapes (e.g., \\Address:\\ → Address:)
        .replace(/<!--.*?-->/g, '') // HTML comments
        // SECURITY: Escape HTML first (before markdown) to prevent XSS
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // Bold: **text** or __text__
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/__(.+?)__/g, '<strong>$1</strong>')
        // Italic: *text* or _text_
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/_([^_]+)_/g, '<em>$1</em>')
        // Links: [text](url) - only allow http/https to prevent javascript: XSS
        .replace(
          /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
          '<a href="$2" class="text-primary-600 underline" target="_blank" rel="noopener noreferrer">$1</a>'
        )
        // Ordered lists: 1. item or 1\. item (escaped period)
        .replace(/^\d+[.\\]+\s+(.+)$/gm, '<li>$1</li>')
        // Unordered lists: * item or - item
        .replace(/^[\*\-]\s+(.+)$/gm, '<li>$1</li>')
        // Wrap consecutive <li> in <ul> (works for both ol and ul for simplicity)
        .replace(
          /(<li>.*<\/li>\n?)+/g,
          '<ul class="list-disc ml-4 my-2">$&</ul>'
        )
        // Headers: ## text
        .replace(
          /^###\s+(.+)$/gm,
          '<h4 class="font-semibold mt-3 mb-1">$1</h4>'
        )
        .replace(
          /^##\s+(.+)$/gm,
          '<h3 class="font-semibold text-lg mt-3 mb-1">$1</h3>'
        )
        // Paragraphs: double newlines
        .replace(/\n\n+/g, '</p><p class="my-2">')
        // Single newlines to <br>
        .replace(/\n/g, '<br>')
        // Wrap in paragraph
        .replace(/^(.+)$/, '<p class="my-2">$1</p>')
    )
  },
}

// =============================================================================
// Chat Component
// =============================================================================

/**
 * Creates a standalone chat component.
 *
 * Can be used directly via Alpine.data('chat'), or composed into larger
 * components via object spread:
 *
 *   Alpine.data('myPage', () => ({
 *     ...createChat(),
 *     // add your own state and methods
 *   }))
 *
 * Hooks (set these to customize behavior):
 *   onBeforeSend(content)       - Modify message before sending. Return new content or null.
 *   onSessionCreated(sessionId) - Called when a chat session is established.
 *   onStreamComplete(message)   - Called when streaming response finishes.
 *   onCleared()                 - Called after chat history is cleared.
 *
 * Public API:
 *   sendMessage()                      - Send the current inputText as a message.
 *   clearChat()                        - Clear messages and session.
 *   pushMessage(role, content, extra)  - Programmatically add a message.
 *   scrollToBottom(force)              - Scroll the message container to bottom.
 */
function createChat() {
  return {
    // --- State ---
    sessionId: '',
    agentName: '',
    messages: [],
    inputText: '',
    isStreaming: false,
    activeToolCall: null,

    // --- Hooks (override for custom behavior) ---
    onBeforeSend: null,
    onSessionCreated: null,
    onStreamComplete: null,
    onCleared: null,

    // --- Core messaging ---
    async sendMessage() {
      let content = this.inputText.trim()
      if (!content || this.isStreaming) return

      // Hook: allow message modification before sending
      if (typeof this.onBeforeSend === 'function') {
        const modified = await this.onBeforeSend(content)
        if (modified) content = modified
      }

      this.inputText = ''
      this.isStreaming = true
      this.activeToolCall = null

      this.messages.push({
        id: Date.now(),
        role: 'user',
        content,
      })
      this.scrollToBottom()

      const msgIndex = this.messages.length
      this.messages.push({
        id: Date.now() + 1,
        role: 'assistant',
        content: '',
        toolCalls: [],
        toolResponses: [],
      })

      try {
        const formData = new FormData()
        formData.append('message', content)
        formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())
        if (this.sessionId) formData.append('session_id', this.sessionId)
        if (this.agentName) formData.append('agent_name', this.agentName)

        const response = await fetch('/chat/stream/', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.error || 'Failed to send message')
        }

        // Stream SSE response
        const reader = response.body.getReader()
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
            const data = line.slice(6).trim()
            if (!data) continue

            try {
              const event = JSON.parse(data)
              const msg = this.messages[msgIndex]

              switch (event.type) {
                case 'session':
                  this.sessionId = event.session_id
                  localStorage.setItem('chatSessionId', event.session_id)
                  if (typeof this.onSessionCreated === 'function') {
                    this.onSessionCreated(event.session_id)
                  }
                  break

                case 'content_delta':
                  this.messages[msgIndex] = {
                    ...msg,
                    content: msg.content + (event.content || ''),
                  }
                  this.scrollToBottom()
                  break

                case 'tool_call':
                  this.activeToolCall = {
                    name: event.name,
                    args: event.args,
                  }
                  msg.toolCalls.push({
                    id: event.id,
                    name: event.name,
                    args: event.args,
                  })
                  this.scrollToBottom()
                  break

                case 'tool_response':
                  this.activeToolCall = null
                  msg.toolResponses.push({
                    id: event.id,
                    name: event.name,
                    response: event.response,
                    data: event.data,
                  })
                  this.scrollToBottom()
                  break

                case 'done':
                  if (typeof this.onStreamComplete === 'function') {
                    this.onStreamComplete(this.messages[msgIndex])
                  }
                  break

                case 'error':
                  console.error('Stream error:', event.error)
                  if (event.message) {
                    this.messages[msgIndex] = {
                      ...msg,
                      content: event.message,
                    }
                  }
                  break
              }
            } catch (e) {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      } catch (error) {
        console.error('Chat error:', error)
        this.messages[msgIndex] = {
          ...this.messages[msgIndex],
          content: 'Sorry, I encountered an error. Please try again.',
        }
      } finally {
        this.isStreaming = false
        this.activeToolCall = null
      }
    },

    // --- UI helpers ---
    scrollToBottom(force = false) {
      this.$nextTick(() => {
        const el = this.$refs.messages || this.$refs.messagesArea
        if (!el) return
        const isNearBottom =
          el.scrollHeight - el.scrollTop - el.clientHeight < 150
        if (force || isNearBottom) {
          el.scrollTop = el.scrollHeight
        }
      })
    },

    // --- Session management ---
    clearChat() {
      this.messages = []
      this.sessionId = ''
      localStorage.removeItem('chatSessionId')
      if (typeof this.onCleared === 'function') {
        this.onCleared()
      }
    },

    /**
     * Add a message to the chat programmatically.
     * Useful for upload responses, system messages, etc.
     */
    pushMessage(role, content, extra = {}) {
      this.messages.push({
        id: Date.now(),
        role,
        content,
        ...extra,
      })
      this.scrollToBottom()
    },

    // --- Template compatibility aliases ---
    askQuestion() {
      return this.sendMessage()
    },
    get dynamicMessages() {
      return this.messages
    },

    // Delegate to shared utilities
    escapeHtml: chatUtils.escapeHtml,
    renderMarkdown: chatUtils.renderMarkdown,
  }
}

// =============================================================================
// Home Page Component
// =============================================================================

/**
 * Home page: chat + file upload + case management + timeline + summarization.
 * Composes createChat() for core messaging, adds everything else directly.
 *
 * Usage: <div x-data="homePage" x-init="agentName = 'litigant_assistant'">
 */
function createHomePage() {
  return {
    // Compose chat
    ...createChat(),

    // --- Availability state ---
    chatAvailable: true,
    showUnavailableWarning: false,
    // Upload state
    selectedFile: null,
    isUploading: false,
    uploadError: null,
    extractedText: null,
    extractedData: null,

    // --- Upload state ---
    selectedFile: null,
    isUploading: false,
    uploadError: null,
    extractedText: null,
    extractedData: null,

    // --- Case management state ---
    caseInfo: null,
    showConfirmation: false,
    _documentContextSent: false,
    _isClearingChat: false,

    // --- Timeline state ---
    caseTimeline: [],

    // --- Initialization ---
    async init() {
      // Check chat service availability
      try {
        const response = await fetch('/chat/status/')
        if (response.ok) {
          const status = await response.json()
          this.chatAvailable = status.available
          this.showUnavailableWarning = !status.available
        } else {
          this.chatAvailable = false
          this.showUnavailableWarning = true
        }
      } catch {
        this.chatAvailable = false
        this.showUnavailableWarning = true
      }

      // Restore session from localStorage
      this.sessionId = localStorage.getItem('chatSessionId') || ''

      // Restore case info
      const savedCaseInfo = localStorage.getItem('caseInfo')
      if (savedCaseInfo) {
        try {
          this.caseInfo = JSON.parse(savedCaseInfo)
        } catch {
          localStorage.removeItem('caseInfo')
        }
      }

      // Restore timeline
      const savedTimeline = localStorage.getItem('caseTimeline')
      if (savedTimeline) {
        try {
          this.caseTimeline = JSON.parse(savedTimeline)
        } catch {
          localStorage.removeItem('caseTimeline')
        }
      }

      // Wire up chat hook for document context injection
      this.onBeforeSend = this._augmentWithDocumentContext.bind(this)
    },

    dismissWarning() {
      this.showUnavailableWarning = false
    },

    // =========================================================================
    // Chat hooks
    // =========================================================================

    /**
     * Injects document context into the first message after an upload,
     * so the LLM has case details available.
     */
    _augmentWithDocumentContext(content) {
      if (!this.extractedData || this._documentContextSent) return content

      const ctx = this.extractedData
      let prefix = '[Document Context]\n'
      if (ctx.case_type) prefix += `Case Type: ${ctx.case_type}\n`
      if (ctx.summary) prefix += `Summary: ${ctx.summary}\n`
      if (ctx.court_info?.court_name)
        prefix += `Court: ${ctx.court_info.court_name}\n`
      if (ctx.court_info?.case_number)
        prefix += `Case Number: ${ctx.court_info.case_number}\n`
      if (ctx.parties?.opposing_party)
        prefix += `Opposing Party: ${ctx.parties.opposing_party}\n`
      if (ctx.key_dates?.length > 0) {
        const deadlines = ctx.key_dates.filter((d) => d.is_deadline)
        if (deadlines.length > 0) {
          prefix += 'Deadlines:\n'
          for (const d of deadlines) {
            prefix += `- ${d.label}: ${d.date}\n`
          }
        }
      }
      prefix += '[End Document Context]\n\n'
      this._documentContextSent = true
      return prefix + content
    },

    // =========================================================================
    // File upload
    // =========================================================================

    triggerFileInput() {
      this.$refs.fileInput?.click()
    },

    handleFileSelect(event) {
      const file = event.target.files?.[0]
      if (!file) return

      if (file.type !== 'application/pdf') {
        this.uploadError = 'Please select a PDF file'
        event.target.value = ''
        return
      }

      if (file.size > 10 * 1024 * 1024) {
        this.uploadError = 'File size must be less than 10MB'
        event.target.value = ''
        return
      }

      this.selectedFile = file
      this.uploadError = null
      this.uploadPdf()
    },

    async uploadPdf() {
      if (!this.selectedFile || this.isUploading) return

      this.isUploading = true
      this.uploadError = null
      const fileName = this.selectedFile.name

      try {
        const formData = new FormData()
        formData.append('file', this.selectedFile)
        formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())

        const response = await fetch('/chat/upload/', {
          method: 'POST',
          body: formData,
        })

        const data = await response.json()
        if (!response.ok) throw new Error(data.error || 'Upload failed')

        this.extractedText = data.text_preview
        this.extractedData = data.extracted_data
        this._documentContextSent = false

        this.selectedFile = null
        if (this.$refs.fileInput) this.$refs.fileInput.value = ''

        // Add timeline event
        const summary =
          data.extracted_data?.summary || `${data.page_count} page document`
        this.addTimelineEvent('upload', `Uploaded: ${fileName}`, summary, {
          filename: fileName,
          page_count: data.page_count,
        })

        // Build and display response message
        if (data.extracted_data) {
          this.pushMessage(
            'assistant',
            this._buildExtractionMessage(data.extracted_data, data.page_count)
          )
          this.showConfirmation = true
        } else if (data.extraction_error) {
          this.pushMessage(
            'assistant',
            `I've received your document (${data.page_count} page${data.page_count !== 1 ? 's' : ''}), ` +
              `but I had trouble analyzing it: ${data.extraction_error}\n\n` +
              'You can still ask me questions about your situation.'
          )
        } else {
          this.pushMessage(
            'assistant',
            `I've received your document (${data.page_count} page${data.page_count !== 1 ? 's' : ''}). ` +
              'How can I help you with it?'
          )
        }
      } catch (error) {
        console.error('Upload error:', error)
        this.uploadError = error.message
        this.pushMessage(
          'assistant',
          `Sorry, I couldn't process your document: ${error.message}`
        )
      } finally {
        this.isUploading = false
      }
    },

    clearUploadError() {
      this.uploadError = null
    },

    _buildExtractionMessage(ed, pageCount) {
      let msg = `I've analyzed your document (${pageCount} page${pageCount !== 1 ? 's' : ''}).\n\n`

      if (ed.case_type) msg += `**Case Type:** ${ed.case_type}\n\n`
      if (ed.summary) msg += `**Summary:** ${ed.summary}\n\n`

      if (ed.court_info?.county || ed.court_info?.court_name) {
        msg += `**Court:** ${ed.court_info.court_name || ''}`
        if (ed.court_info.county) msg += ` (${ed.court_info.county})`
        if (ed.court_info.case_number)
          msg += `\n**Case Number:** ${ed.court_info.case_number}`
        msg += '\n\n'
      }

      if (ed.parties?.user_name || ed.parties?.opposing_party) {
        if (ed.parties.opposing_party)
          msg += `**Filed by:** ${ed.parties.opposing_party}\n`
        if (ed.parties.user_name)
          msg += `**Against:** ${ed.parties.user_name}\n`
        msg += '\n'
      }

      if (ed.key_dates?.length > 0) {
        const deadlines = ed.key_dates.filter((d) => d.is_deadline)
        const otherDates = ed.key_dates.filter((d) => !d.is_deadline)

        if (deadlines.length > 0) {
          msg += '**Important Deadlines:**\n'
          for (const d of deadlines) msg += `- ${d.label}: **${d.date}**\n`
          msg += '\n'
        }

        if (otherDates.length > 0) {
          msg += '**Other Dates:**\n'
          for (const d of otherDates) msg += `- ${d.label}: ${d.date}\n`
          msg += '\n'
        }
      }

      msg += 'Does this information look correct?'
      return msg
    },

    // =========================================================================
    // Case management
    // =========================================================================

    confirmExtraction() {
      if (!this.extractedData) return

      if (this.caseInfo) {
        this.mergeCaseInfo(this.extractedData)
      } else {
        this.caseInfo = this.extractedData
      }
      localStorage.setItem('caseInfo', JSON.stringify(this.caseInfo))
      this.showConfirmation = false

      this.pushMessage(
        'assistant',
        "Great! I've saved your case information. You can see it in the sidebar. What would you like help with?"
      )
    },

    mergeCaseInfo(newData) {
      if (!newData) return

      const changes = []

      if (newData.case_type && newData.case_type !== this.caseInfo.case_type) {
        changes.push(`Case type: ${newData.case_type}`)
        this.caseInfo.case_type = newData.case_type
      }

      if (newData.court_info) {
        if (!this.caseInfo.court_info) this.caseInfo.court_info = {}
        for (const [key, value] of Object.entries(newData.court_info)) {
          if (value && value !== this.caseInfo.court_info[key]) {
            changes.push(`Court ${key}: ${value}`)
            this.caseInfo.court_info[key] = value
          }
        }
      }

      if (newData.parties) {
        if (!this.caseInfo.parties) this.caseInfo.parties = {}
        for (const [key, value] of Object.entries(newData.parties)) {
          if (value && value !== this.caseInfo.parties[key]) {
            changes.push(`Party ${key}: ${value}`)
            this.caseInfo.parties[key] = value
          }
        }
      }

      if (newData.key_dates?.length > 0) {
        if (!this.caseInfo.key_dates) this.caseInfo.key_dates = []
        for (const newDate of newData.key_dates) {
          const exists = this.caseInfo.key_dates.some(
            (d) => d.label === newDate.label && d.date === newDate.date
          )
          if (!exists) {
            changes.push(`New date: ${newDate.label} - ${newDate.date}`)
            this.caseInfo.key_dates.push(newDate)
          }
        }
      }

      if (newData.summary) this.caseInfo.summary = newData.summary

      if (changes.length > 0) {
        this.addTimelineEvent('change', 'Case info updated', changes.join('; '))
      }
    },

    requestClarification() {
      this.showConfirmation = false
      this.pushMessage(
        'assistant',
        "No problem! What information needs to be corrected? You can tell me what's wrong and I'll update it, or you can upload a different document."
      )
    },

    clearCaseInfo() {
      this.caseInfo = null
      this.extractedData = null
      this.caseTimeline = []
      this._documentContextSent = false
      localStorage.removeItem('caseInfo')
      localStorage.removeItem('caseTimeline')
    },

    // =========================================================================
    // Summarization
    // =========================================================================

    async generateChatSummary() {
      if (this.messages.length < 2) return null

      try {
        const formData = new FormData()
        formData.append('messages', JSON.stringify(this.messages))
        formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())

        const response = await fetch('/chat/summarize/', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) return null
        const data = await response.json()
        return data.summary || null
      } catch (e) {
        console.error('Failed to generate summary:', e)
        return null
      }
    },

    // =========================================================================
    // Timeline
    // =========================================================================

    addTimelineEvent(type, title, content, metadata = {}) {
      const event = {
        id: Date.now(),
        type, // 'upload' | 'summary' | 'change'
        timestamp: new Date().toISOString(),
        title,
        content,
        metadata,
      }
      this.caseTimeline.push(event)
      localStorage.setItem('caseTimeline', JSON.stringify(this.caseTimeline))
    },

    // =========================================================================
    // Override: clearChat with summarization
    // =========================================================================

    async clearChat() {
      if (this._isClearingChat) return
      this._isClearingChat = true

      try {
        if (this.messages.length >= 2) {
          const summary = await this.generateChatSummary()
          if (summary && !summary.toLowerCase().includes('no user questions')) {
            this.addTimelineEvent('summary', '', summary)
          }
        }

        this.messages = []
        this.sessionId = ''
        this.extractedData = null
        this._documentContextSent = false
        localStorage.removeItem('chatSessionId')
      } finally {
        this._isClearingChat = false
      }
    },
  }
}

// =============================================================================
// Alpine Registration
// =============================================================================

document.addEventListener('alpine:init', () => {
  Alpine.data('chat', () => createChat())
  Alpine.data('homePage', () => createHomePage())
})
