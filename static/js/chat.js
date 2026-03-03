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

    // --- Initialization (reads config from data-* attributes) ---
    init() {
      if (this.$el.dataset.sessionId) {
        this.sessionId = this.$el.dataset.sessionId
      }
    },

    // --- Input binding (x-model unsupported in CSP build) ---
    updateInput(e) {
      this.inputText = e.target.value
    },

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
        renderedContent: chatUtils.escapeHtml(content),
        bubbleClass: 'chat-bubble-user',
        messageClass: 'chat-message-user',
        isUser: true,
        isAssistant: false,
      })
      this.scrollToBottom()

      const msgIndex = this.messages.length
      this.messages.push({
        id: Date.now() + 1,
        role: 'assistant',
        content: '',
        renderedContent: '',
        bubbleClass: 'chat-bubble-assistant',
        messageClass: 'chat-message-assistant',
        isUser: false,
        isAssistant: true,
        toolCalls: [],
        toolResponses: [],
      })

      try {
        const formData = new FormData()
        formData.append('message', content)
        formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())
        if (this.sessionId) formData.append('session_id', this.sessionId)
        if (this.agentName) formData.append('agent_name', this.agentName)

        const response = await fetch('/api/chat/stream/', {
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
                  if (typeof this.onSessionCreated === 'function') {
                    this.onSessionCreated(event.session_id)
                  }
                  break

                case 'content_delta': {
                  const updated = msg.content + (event.content || '')
                  this.messages[msgIndex] = {
                    ...msg,
                    content: updated,
                    renderedContent: chatUtils.renderMarkdown(updated),
                  }
                  break
                }

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
                  break

                case 'tool_response':
                  this.activeToolCall = null
                  msg.toolResponses.push({
                    id: event.id,
                    name: event.name,
                    response: event.response,
                    data: event.data,
                  })
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
                      renderedContent: chatUtils.escapeHtml(event.message),
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
        const errorMsg = 'Sorry, I encountered an error. Please try again.'
        this.messages[msgIndex] = {
          ...this.messages[msgIndex],
          content: errorMsg,
          renderedContent: chatUtils.escapeHtml(errorMsg),
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
      if (typeof this.onCleared === 'function') {
        this.onCleared()
      }
    },

    /**
     * Add a message to the chat programmatically.
     * Useful for upload responses, system messages, etc.
     */
    pushMessage(role, content, extra = {}) {
      const isUser = role === 'user'
      this.messages.push({
        id: Date.now(),
        role,
        content,
        renderedContent: isUser
          ? chatUtils.escapeHtml(content)
          : chatUtils.renderMarkdown(content),
        bubbleClass: isUser ? 'chat-bubble-user' : 'chat-bubble-assistant',
        messageClass: isUser ? 'chat-message-user' : 'chat-message-assistant',
        isUser,
        isAssistant: !isUser,
        ...extra,
      })
      this.scrollToBottom()
    },

    // --- Getters for CSP-safe dot-path access ---
    get hasMessages() {
      return this.messages.length > 0
    },
    get noMessages() {
      return this.messages.length === 0
    },
    get sendDisabled() {
      return this.isStreaming || !this.inputText.trim()
    },

    // --- Template compatibility aliases ---
    askQuestion() {
      return this.sendMessage()
    },
    get dynamicMessages() {
      return this.messages
    },
  }
}

// =============================================================================
// Home Page Component
// =============================================================================

/**
 * Home page: chat + file upload + case management + timeline + summarization.
 * Composes createChat() for core messaging, adds everything else directly.
 *
 * Usage: <div x-data="homePage" data-agent-name="litigant_assistant">
 */
function createHomePage() {
  return {
    // Compose chat
    ...createChat(),

    // Re-define chat getters lost during spread (spread flattens getters
    // into static values — a JS language gotcha with object spread).
    get hasMessages() {
      return this.messages.length > 0
    },
    get noMessages() {
      return this.messages.length === 0
    },
    get sendDisabled() {
      return this.isStreaming || !this.inputText.trim()
    },

    // --- Availability state ---
    chatAvailable: true,
    showUnavailableWarning: false,

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

    // --- Getters for CSP-safe dot-path access ---

    // Container class
    get containerClass() {
      return this.messages.length > 0 ? 'chat-mode' : ''
    },

    // Case header
    get caseTitle() {
      return this.caseInfo?.case_type || 'Your Case'
    },
    get caseNumber() {
      const num = this.caseInfo?.court_info?.case_number
      return num ? 'Case #' + num : ''
    },
    get hasCaseNumber() {
      return !!this.caseInfo?.court_info?.case_number
    },

    // Court info
    get showCourtSection() {
      return !!(
        this.caseInfo?.court_info?.court_name ||
        this.caseInfo?.court_info?.county
      )
    },
    get courtName() {
      return this.caseInfo?.court_info?.court_name || ''
    },
    get courtCounty() {
      return this.caseInfo?.court_info?.county || ''
    },
    get courtAddress() {
      return this.caseInfo?.court_info?.address || ''
    },
    get courtPhone() {
      return this.caseInfo?.court_info?.phone || ''
    },
    get courtEmail() {
      return this.caseInfo?.court_info?.email || ''
    },
    get courtPhoneHref() {
      return this.courtPhone ? 'tel:' + this.courtPhone : ''
    },
    get courtEmailHref() {
      return this.courtEmail ? 'mailto:' + this.courtEmail : ''
    },

    // Opposing party
    get opposingParty() {
      return this.caseInfo?.parties?.opposing_party || ''
    },
    get opposingAddress() {
      return this.caseInfo?.parties?.opposing_address || ''
    },
    get opposingPhone() {
      return this.caseInfo?.parties?.opposing_phone || ''
    },
    get opposingEmail() {
      return this.caseInfo?.parties?.opposing_email || ''
    },
    get opposingWebsite() {
      return this.caseInfo?.parties?.opposing_website || ''
    },
    get opposingPhoneHref() {
      return this.opposingPhone ? 'tel:' + this.opposingPhone : ''
    },
    get opposingEmailHref() {
      return this.opposingEmail ? 'mailto:' + this.opposingEmail : ''
    },

    // Attorney
    get attorneyName() {
      return this.caseInfo?.parties?.attorney_name || ''
    },
    get attorneyPhone() {
      return this.caseInfo?.parties?.attorney_phone || ''
    },
    get attorneyEmail() {
      return this.caseInfo?.parties?.attorney_email || ''
    },
    get attorneyPhoneHref() {
      return this.attorneyPhone ? 'tel:' + this.attorneyPhone : ''
    },
    get attorneyEmailHref() {
      return this.attorneyEmail ? 'mailto:' + this.attorneyEmail : ''
    },

    // Dates (pre-filtered)
    get deadlines() {
      return (this.caseInfo?.key_dates || []).filter((d) => d.is_deadline)
    },
    get otherDates() {
      return (this.caseInfo?.key_dates || []).filter((d) => !d.is_deadline)
    },
    get hasDeadlines() {
      return this.deadlines.length > 0
    },
    get hasOtherDates() {
      return this.otherDates.length > 0
    },

    // Negated booleans (CSP build can't evaluate `!`)
    get noCaseInfo() {
      return !this.caseInfo
    },
    get notUploading() {
      return !this.isUploading
    },

    // --- Initialization ---
    async init() {
      // Read config from data-* attributes
      this.agentName = this.$el.dataset.agentName || ''

      // Check chat service availability
      try {
        const response = await fetch('/api/chat/status/')
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

      // Restore case info and timeline from server
      try {
        const caseResponse = await fetch('/api/chat/case/')
        if (caseResponse.ok) {
          const caseData = await caseResponse.json()
          if (caseData.case_info) {
            this.caseInfo = caseData.case_info
          }
          if (caseData.timeline) {
            this.caseTimeline = caseData.timeline.map((e) => ({
              id: e.id,
              type: e.event_type,
              timestamp: e.created_at,
              title: e.title,
              content: e.content,
              metadata: e.metadata,
            }))
          }
        }
      } catch {
        // Server unavailable — start with empty state
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

        const response = await fetch('/api/chat/upload/', {
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

    async confirmExtraction() {
      if (!this.extractedData) return

      if (this.caseInfo) {
        this.mergeCaseInfo(this.extractedData)
      } else {
        this.caseInfo = this.extractedData
      }
      this.showConfirmation = false

      // Persist to server
      const formData = new FormData()
      formData.append('data', JSON.stringify(this.caseInfo))
      formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())
      try {
        await fetch('/api/chat/case/save/', { method: 'POST', body: formData })
      } catch (e) {
        console.error('Failed to save case info:', e)
      }

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

    async clearCaseInfo() {
      this.caseInfo = null
      this.extractedData = null
      this.caseTimeline = []
      this._documentContextSent = false

      // Clear server-side data
      const formData = new FormData()
      formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())
      try {
        await fetch('/api/chat/case/clear/', { method: 'POST', body: formData })
      } catch (e) {
        console.error('Failed to clear case info:', e)
      }
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

        const response = await fetch('/api/chat/summarize/', {
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

    async addTimelineEvent(type, title, content, metadata = {}) {
      // Optimistic push to in-memory state
      const event = {
        id: Date.now(),
        type,
        timestamp: new Date().toISOString(),
        title,
        content,
        metadata,
      }
      this.caseTimeline.push(event)

      // Persist to server
      const formData = new FormData()
      formData.append('event_type', type)
      formData.append('title', title)
      formData.append('content', content)
      formData.append('metadata', JSON.stringify(metadata))
      formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())
      try {
        const response = await fetch('/api/chat/case/timeline/', {
          method: 'POST',
          body: formData,
        })
        if (response.ok) {
          const data = await response.json()
          event.id = data.id
        }
      } catch (e) {
        console.error('Failed to save timeline event:', e)
      }
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
