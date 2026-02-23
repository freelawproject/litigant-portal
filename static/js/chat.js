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
 * Can be used directly via registerComponent('chat', createChat),
 * or composed into larger components by calling createChat(el) and
 * extending the returned API.
 *
 * Hooks (set on returned object):
 *   onBeforeSend(content)       - Modify message before sending. Return new content or null.
 *   onSessionCreated(sessionId) - Called when a chat session is established.
 *   onStreamComplete(message)   - Called when streaming response finishes.
 *   onCleared()                 - Called after chat history is cleared.
 *
 * Public API:
 *   sendMessage()                      - Send the current input text.
 *   clearChat()                        - Clear messages and session.
 *   pushMessage(role, content, extra)  - Programmatically add a message.
 *   update()                           - Re-render messages to DOM.
 */
function createChat(el, { bindForm = true } = {}) {
  const messagesContainer = ref(el, 'messages') || ref(el, 'messagesArea')
  const form = el.querySelector('form')
  const input =
    ref(el, 'input') ||
    el.querySelector('input[name="message"]') ||
    el.querySelector('input[name="q"]')
  const submitBtn =
    ref(el, 'submitBtn') || (form && form.querySelector('[type="submit"]'))
  const typingIndicator = ref(el, 'typing')

  // State
  const state = {
    sessionId: el.dataset.sessionId || '',
    agentName: el.dataset.agentName || '',
    messages: [],
    isStreaming: false,
    activeToolCall: null,
  }

  // Hooks
  const chat = {
    state,

    // Hook properties
    onBeforeSend: null,
    onSessionCreated: null,
    onStreamComplete: null,
    onCleared: null,

    async sendMessage(explicitContent) {
      let content = explicitContent || (input ? input.value : '').trim()
      if (!content || state.isStreaming) return

      // Hook: allow message modification before sending
      if (typeof chat.onBeforeSend === 'function') {
        const modified = await chat.onBeforeSend(content)
        if (modified) content = modified
      }

      if (input) input.value = ''
      state.isStreaming = true
      state.activeToolCall = null

      state.messages.push({
        id: Date.now(),
        role: 'user',
        content,
      })
      chat.update()

      const msgIndex = state.messages.length
      state.messages.push({
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
        if (state.sessionId) formData.append('session_id', state.sessionId)
        if (state.agentName) formData.append('agent_name', state.agentName)

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
              const msg = state.messages[msgIndex]

              switch (event.type) {
                case 'session':
                  state.sessionId = event.session_id
                  localStorage.setItem('chatSessionId', event.session_id)
                  if (typeof chat.onSessionCreated === 'function') {
                    chat.onSessionCreated(event.session_id)
                  }
                  break

                case 'content_delta':
                  state.messages[msgIndex] = {
                    ...msg,
                    content: msg.content + (event.content || ''),
                  }
                  chat.update()
                  break

                case 'tool_call':
                  state.activeToolCall = {
                    name: event.name,
                    args: event.args,
                  }
                  msg.toolCalls.push({
                    id: event.id,
                    name: event.name,
                    args: event.args,
                  })
                  chat.update()
                  break

                case 'tool_response':
                  state.activeToolCall = null
                  msg.toolResponses.push({
                    id: event.id,
                    name: event.name,
                    response: event.response,
                    data: event.data,
                  })
                  chat.update()
                  break

                case 'done':
                  if (typeof chat.onStreamComplete === 'function') {
                    chat.onStreamComplete(state.messages[msgIndex])
                  }
                  break

                case 'error':
                  console.error('Stream error:', event.error)
                  if (event.message) {
                    state.messages[msgIndex] = {
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
        state.messages[msgIndex] = {
          ...state.messages[msgIndex],
          content: 'Sorry, I encountered an error. Please try again.',
        }
      } finally {
        state.isStreaming = false
        state.activeToolCall = null
        chat.update()
      }
    },

    clearChat() {
      state.messages = []
      state.sessionId = ''
      localStorage.removeItem('chatSessionId')
      if (typeof chat.onCleared === 'function') {
        chat.onCleared()
      }
      chat.update()
    },

    pushMessage(role, content, extra = {}) {
      state.messages.push({
        id: Date.now(),
        role,
        content,
        ...extra,
      })
      chat.update()
    },

    update() {
      if (messagesContainer) {
        renderMessages(messagesContainer, state.messages)
        scrollToBottom(messagesContainer)
      }

      // Typing indicator
      if (typingIndicator) {
        typingIndicator.hidden = !state.isStreaming
      }

      // Submit button disabled state
      if (submitBtn) {
        submitBtn.disabled = state.isStreaming || !(input && input.value.trim())
      }

      // Input disabled state
      if (input) {
        input.disabled = state.isStreaming
      }
    },
  }

  function renderMessages(container, messages) {
    // Find templates
    const userTpl = container.querySelector('[data-template="message-user"]')
    const assistantTpl = container.querySelector(
      '[data-template="message-assistant"]'
    )
    if (!userTpl || !assistantTpl) return

    const activeIds = new Set()

    for (const msg of messages) {
      if (!msg.content) continue
      activeIds.add(String(msg.id))

      // Update existing message in-place (fast path for streaming deltas)
      const existing = container.querySelector(`[data-message="${msg.id}"]`)
      if (existing) {
        const bubble = existing.querySelector('[data-bind="content"]')
        if (bubble) {
          if (msg.role === 'assistant') {
            bubble.innerHTML = chatUtils.renderMarkdown(msg.content)
          } else {
            bubble.textContent = msg.content
          }
        }
        continue
      }

      // New message — clone template and insert
      const tpl = msg.role === 'user' ? userTpl : assistantTpl
      const clone = tpl.content.cloneNode(true)
      const wrapper = clone.firstElementChild || clone.children[0]
      if (wrapper) wrapper.setAttribute('data-message', msg.id)

      const bubble = clone.querySelector('[data-bind="content"]')
      if (bubble) {
        if (msg.role === 'assistant') {
          bubble.innerHTML = chatUtils.renderMarkdown(msg.content)
        } else {
          bubble.textContent = msg.content
        }
      }

      // Insert before typing indicator if present, else append
      if (typingIndicator && typingIndicator.parentNode === container) {
        container.insertBefore(clone, typingIndicator)
      } else {
        container.appendChild(clone)
      }
    }

    // Remove DOM nodes for messages no longer in state (e.g. after clearChat)
    container.querySelectorAll('[data-message]').forEach((node) => {
      if (!activeIds.has(node.getAttribute('data-message'))) node.remove()
    })
  }

  // Form submission (skipped when composed into a parent component)
  if (bindForm && form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault()
      chat.sendMessage()
    })
  }

  // Enable/disable submit on input
  if (bindForm && input && submitBtn) {
    input.addEventListener('input', () => {
      submitBtn.disabled = state.isStreaming || !input.value.trim()
    })
  }

  // Initial state
  chat.update()

  return chat
}

// Register standalone chat component
registerComponent('chat', createChat)

// =============================================================================
// Home Page Component
// =============================================================================

/**
 * Home page: chat + file upload + case management + timeline + summarization.
 * Composes createChat() for core messaging, adds everything else.
 *
 * Usage: <div data-component="homePage" data-agent-name="litigant_assistant">
 */
function createHomePage(el) {
  // Create inner chat (using the same root element, skip form binding — we handle forms here)
  const chat = createChat(el, { bindForm: false })
  const { state } = chat

  // Additional state
  const pageState = {
    chatAvailable: true,
    showUnavailableWarning: false,
    selectedFile: null,
    isUploading: false,
    extractedData: null,
    caseInfo: null,
    showConfirmation: false,
    _documentContextSent: false,
    _isClearingChat: false,
    caseTimeline: [],
  }

  // DOM refs
  const fileInput = ref(el, 'fileInput')
  const warningBanner = ref(el, 'warningBanner')
  const warningDismiss = ref(el, 'warningDismiss')
  const heroSection = ref(el, 'hero')
  const chatSection = ref(el, 'chatArea')
  const messagesArea = ref(el, 'messagesArea')
  const heroForm = ref(el, 'heroForm')
  const heroInput = ref(el, 'heroInput')
  const chatForm = ref(el, 'chatForm')
  const chatInput = ref(el, 'chatInput')
  const newConversationBtn = ref(el, 'newConversation')
  const confirmationArea = ref(el, 'confirmation')
  const confirmBtn = ref(el, 'confirmBtn')
  const clarifyBtn = ref(el, 'clarifyBtn')

  // Sidebar refs
  const sidebarEmpty = ref(el, 'sidebarEmpty')
  const sidebarInfo = ref(el, 'sidebarInfo')
  const clearCaseBtn = ref(el, 'clearCaseInfo')

  // Upload buttons
  const uploadBtns = el.querySelectorAll('[data-action="triggerUpload"]')
  const uploadIcons = el.querySelectorAll('[data-ref="uploadIcon"]')
  const spinnerIcons = el.querySelectorAll('[data-ref="spinnerIcon"]')

  // Set agent name from data attribute
  state.agentName = el.dataset.agentName || ''

  // =========================================================================
  // Initialization
  // =========================================================================

  async function init() {
    // Check chat service availability
    try {
      const response = await fetch('/api/chat/status/')
      if (response.ok) {
        const status = await response.json()
        pageState.chatAvailable = status.available
        pageState.showUnavailableWarning = !status.available
      } else {
        pageState.chatAvailable = false
        pageState.showUnavailableWarning = true
      }
    } catch {
      pageState.chatAvailable = false
      pageState.showUnavailableWarning = true
    }

    // Restore session from localStorage
    state.sessionId = localStorage.getItem('chatSessionId') || ''

    // Restore case info
    const savedCaseInfo = localStorage.getItem('caseInfo')
    if (savedCaseInfo) {
      try {
        pageState.caseInfo = JSON.parse(savedCaseInfo)
      } catch {
        localStorage.removeItem('caseInfo')
      }
    }

    // Restore timeline
    const savedTimeline = localStorage.getItem('caseTimeline')
    if (savedTimeline) {
      try {
        pageState.caseTimeline = JSON.parse(savedTimeline)
      } catch {
        localStorage.removeItem('caseTimeline')
      }
    }

    // Wire up chat hook for document context injection
    chat.onBeforeSend = augmentWithDocumentContext

    chat.update()
  }

  // =========================================================================
  // Override chat.update — single update path for all DOM syncing
  // =========================================================================

  const originalUpdate = chat.update
  chat.update = function () {
    originalUpdate.call(chat)

    const hasMessages = state.messages.length > 0

    // Hero vs chat mode
    el.classList.toggle('chat-mode', hasMessages)
    if (heroSection) heroSection.hidden = hasMessages
    if (chatSection) chatSection.hidden = !hasMessages

    // Warning banner
    if (warningBanner) warningBanner.hidden = !pageState.showUnavailableWarning

    // Confirmation buttons
    if (confirmationArea) confirmationArea.hidden = !pageState.showConfirmation

    // Upload button states
    uploadBtns.forEach((btn) => {
      btn.disabled = pageState.isUploading
    })
    uploadIcons.forEach((icon) => {
      icon.hidden = pageState.isUploading
    })
    spinnerIcons.forEach((icon) => {
      icon.hidden = !pageState.isUploading
    })

    // Sidebar
    updateSidebar()

    // Scroll the messages area
    if (messagesArea) scrollToBottom(messagesArea)
  }

  // =========================================================================
  // Sidebar
  // =========================================================================

  function updateSidebar() {
    if (sidebarEmpty) sidebarEmpty.hidden = !!pageState.caseInfo
    if (sidebarInfo) sidebarInfo.hidden = !pageState.caseInfo

    if (!pageState.caseInfo || !sidebarInfo) return

    const c = pageState.caseInfo
    const court = c.court_info || {}
    const parties = c.parties || {}

    // Helper to set text content of a data-field element
    function setText(name, value) {
      const el = sidebarInfo.querySelector(`[data-field="${name}"]`)
      if (el) el.textContent = value || ''
    }
    function setHref(name, value) {
      const el = sidebarInfo.querySelector(`[data-field="${name}"]`)
      if (el) el.href = value || ''
    }
    function showIf(name, condition) {
      const el = sidebarInfo.querySelector(`[data-section="${name}"]`)
      if (el) el.hidden = !condition
    }

    // Case type
    setText('caseType', c.case_type || 'Your Case')
    showIf('caseNumber', !!court.case_number)
    setText('caseNumber', 'Case #' + (court.case_number || ''))

    // Court info
    showIf('courtInfo', !!(court.court_name || court.county))
    setText('courtName', court.court_name || '')
    showIf('county', !!court.county)
    setText('county', court.county || '')
    showIf('address', !!court.address)
    setText('address', court.address || '')
    showIf('phone', !!court.phone)
    setText('phone', court.phone || '')
    setHref('phoneTel', 'tel:' + (court.phone || ''))
    showIf('email', !!court.email)
    setText('email', court.email || '')
    setHref('emailMailto', 'mailto:' + (court.email || ''))

    // Opposing party
    showIf('opposingParty', !!parties.opposing_party)
    setText('opposingParty', parties.opposing_party || '')
    showIf('opposingAddress', !!parties.opposing_address)
    setText('opposingAddress', parties.opposing_address || '')
    showIf('opposingPhone', !!parties.opposing_phone)
    setText('opposingPhone', parties.opposing_phone || '')
    setHref('opposingPhoneTel', 'tel:' + (parties.opposing_phone || ''))
    showIf('opposingEmail', !!parties.opposing_email)
    setText('opposingEmail', parties.opposing_email || '')
    setHref('opposingEmailMailto', 'mailto:' + (parties.opposing_email || ''))
    showIf('opposingWebsite', !!parties.opposing_website)
    setText('opposingWebsite', parties.opposing_website || '')
    setHref('opposingWebsiteLink', parties.opposing_website || '')

    // Attorney
    showIf('attorney', !!parties.attorney_name)
    setText('attorneyName', parties.attorney_name || '')
    showIf('attorneyPhone', !!parties.attorney_phone)
    setText('attorneyPhone', parties.attorney_phone || '')
    setHref('attorneyPhoneTel', 'tel:' + (parties.attorney_phone || ''))
    showIf('attorneyEmail', !!parties.attorney_email)
    setText('attorneyEmail', parties.attorney_email || '')
    setHref('attorneyEmailMailto', 'mailto:' + (parties.attorney_email || ''))

    // Deadlines
    const deadlines = c.key_dates?.filter((d) => d.is_deadline) || []
    const otherDates = c.key_dates?.filter((d) => !d.is_deadline) || []

    showIf('deadlines', deadlines.length > 0)
    const deadlinesContainer = sidebarInfo.querySelector(
      '[data-list="deadlines"]'
    )
    if (deadlinesContainer) {
      renderList(
        deadlinesContainer,
        '[data-template="deadline"]',
        deadlines,
        (clone, d) => {
          const dateEl = clone.querySelector('[data-bind="date"]')
          if (dateEl) dateEl.textContent = d.date
          const labelEl = clone.querySelector('[data-bind="label"]')
          if (labelEl) labelEl.textContent = d.label
        }
      )
    }

    showIf('otherDates', otherDates.length > 0)
    const datesContainer = sidebarInfo.querySelector('[data-list="otherDates"]')
    if (datesContainer) {
      renderList(
        datesContainer,
        '[data-template="otherDate"]',
        otherDates,
        (clone, d) => {
          const dateEl = clone.querySelector('[data-bind="date"]')
          if (dateEl) dateEl.textContent = d.date
          const labelEl = clone.querySelector('[data-bind="label"]')
          if (labelEl) labelEl.textContent = d.label
        }
      )
    }
  }

  // =========================================================================
  // Chat hooks
  // =========================================================================

  function augmentWithDocumentContext(content) {
    if (!pageState.extractedData || pageState._documentContextSent)
      return content

    const ctx = pageState.extractedData
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
    pageState._documentContextSent = true
    return prefix + content
  }

  // =========================================================================
  // File upload
  // =========================================================================

  function triggerFileInput() {
    if (fileInput) fileInput.click()
  }

  function handleFileSelect(event) {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.type !== 'application/pdf') {
      event.target.value = ''
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      event.target.value = ''
      return
    }

    pageState.selectedFile = file
    uploadPdf()
  }

  async function uploadPdf() {
    if (!pageState.selectedFile || pageState.isUploading) return

    pageState.isUploading = true
    const fileName = pageState.selectedFile.name
    chat.update()

    try {
      const formData = new FormData()
      formData.append('file', pageState.selectedFile)
      formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())

      const response = await fetch('/api/chat/upload/', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Upload failed')

      pageState.extractedData = data.extracted_data
      pageState._documentContextSent = false

      pageState.selectedFile = null
      if (fileInput) fileInput.value = ''

      // Add timeline event
      const summary =
        data.extracted_data?.summary || `${data.page_count} page document`
      addTimelineEvent('upload', `Uploaded: ${fileName}`, summary, {
        filename: fileName,
        page_count: data.page_count,
      })

      // Build and display response message
      if (data.extracted_data) {
        chat.pushMessage(
          'assistant',
          buildExtractionMessage(data.extracted_data, data.page_count)
        )
        pageState.showConfirmation = true
      } else if (data.extraction_error) {
        chat.pushMessage(
          'assistant',
          `I've received your document (${data.page_count} page${data.page_count !== 1 ? 's' : ''}), ` +
            `but I had trouble analyzing it: ${data.extraction_error}\n\n` +
            'You can still ask me questions about your situation.'
        )
      } else {
        chat.pushMessage(
          'assistant',
          `I've received your document (${data.page_count} page${data.page_count !== 1 ? 's' : ''}). ` +
            'How can I help you with it?'
        )
      }
    } catch (error) {
      console.error('Upload error:', error)
      chat.pushMessage(
        'assistant',
        `Sorry, I couldn't process your document: ${error.message}`
      )
    } finally {
      pageState.isUploading = false
      chat.update()
    }
  }

  function buildExtractionMessage(ed, pageCount) {
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
      if (ed.parties.user_name) msg += `**Against:** ${ed.parties.user_name}\n`
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
  }

  // =========================================================================
  // Case management
  // =========================================================================

  function confirmExtraction() {
    if (!pageState.extractedData) return

    if (pageState.caseInfo) {
      mergeCaseInfo(pageState.extractedData)
    } else {
      pageState.caseInfo = pageState.extractedData
    }
    localStorage.setItem('caseInfo', JSON.stringify(pageState.caseInfo))
    pageState.showConfirmation = false

    chat.pushMessage(
      'assistant',
      "Great! I've saved your case information. You can see it in the sidebar. What would you like help with?"
    )
    updateSidebar()
  }

  function mergeCaseInfo(newData) {
    if (!newData) return

    const changes = []

    if (
      newData.case_type &&
      newData.case_type !== pageState.caseInfo.case_type
    ) {
      changes.push(`Case type: ${newData.case_type}`)
      pageState.caseInfo.case_type = newData.case_type
    }

    if (newData.court_info) {
      if (!pageState.caseInfo.court_info) pageState.caseInfo.court_info = {}
      for (const [key, value] of Object.entries(newData.court_info)) {
        if (value && value !== pageState.caseInfo.court_info[key]) {
          changes.push(`Court ${key}: ${value}`)
          pageState.caseInfo.court_info[key] = value
        }
      }
    }

    if (newData.parties) {
      if (!pageState.caseInfo.parties) pageState.caseInfo.parties = {}
      for (const [key, value] of Object.entries(newData.parties)) {
        if (value && value !== pageState.caseInfo.parties[key]) {
          changes.push(`Party ${key}: ${value}`)
          pageState.caseInfo.parties[key] = value
        }
      }
    }

    if (newData.key_dates?.length > 0) {
      if (!pageState.caseInfo.key_dates) pageState.caseInfo.key_dates = []
      for (const newDate of newData.key_dates) {
        const exists = pageState.caseInfo.key_dates.some(
          (d) => d.label === newDate.label && d.date === newDate.date
        )
        if (!exists) {
          changes.push(`New date: ${newDate.label} - ${newDate.date}`)
          pageState.caseInfo.key_dates.push(newDate)
        }
      }
    }

    if (newData.summary) pageState.caseInfo.summary = newData.summary

    if (changes.length > 0) {
      addTimelineEvent('change', 'Case info updated', changes.join('; '))
    }
  }

  function requestClarification() {
    pageState.showConfirmation = false
    chat.pushMessage(
      'assistant',
      "No problem! What information needs to be corrected? You can tell me what's wrong and I'll update it, or you can upload a different document."
    )
  }

  function clearCaseInfo() {
    pageState.caseInfo = null
    pageState.extractedData = null
    pageState.caseTimeline = []
    pageState._documentContextSent = false
    localStorage.removeItem('caseInfo')
    localStorage.removeItem('caseTimeline')
    updateSidebar()
  }

  // =========================================================================
  // Summarization
  // =========================================================================

  async function generateChatSummary() {
    if (state.messages.length < 2) return null

    try {
      const formData = new FormData()
      formData.append('messages', JSON.stringify(state.messages))
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
  }

  // =========================================================================
  // Timeline
  // =========================================================================

  function addTimelineEvent(type, title, content, metadata = {}) {
    const event = {
      id: Date.now(),
      type,
      timestamp: new Date().toISOString(),
      title,
      content,
      metadata,
    }
    pageState.caseTimeline.push(event)
    localStorage.setItem('caseTimeline', JSON.stringify(pageState.caseTimeline))
  }

  // =========================================================================
  // Override: clearChat with summarization
  // =========================================================================

  chat.clearChat = async function () {
    if (pageState._isClearingChat) return
    pageState._isClearingChat = true

    try {
      if (state.messages.length >= 2) {
        const summary = await generateChatSummary()
        if (summary && !summary.toLowerCase().includes('no user questions')) {
          addTimelineEvent('summary', '', summary)
        }
      }

      state.messages = []
      state.sessionId = ''
      pageState.extractedData = null
      pageState._documentContextSent = false
      pageState.showConfirmation = false
      localStorage.removeItem('chatSessionId')
      chat.update()
    } finally {
      pageState._isClearingChat = false
    }
  }

  // =========================================================================
  // Event listeners
  // =========================================================================

  // File input
  if (fileInput) {
    fileInput.addEventListener('change', handleFileSelect)
  }

  // Upload buttons
  uploadBtns.forEach((btn) => {
    btn.addEventListener('click', triggerFileInput)
  })

  // Warning dismiss
  if (warningDismiss) {
    warningDismiss.addEventListener('click', () => {
      pageState.showUnavailableWarning = false
      if (warningBanner) warningBanner.hidden = true
    })
  }

  // Hero form
  if (heroForm) {
    heroForm.addEventListener('submit', (e) => {
      e.preventDefault()
      const content = heroInput ? heroInput.value.trim() : ''
      if (heroInput) heroInput.value = ''
      chat.sendMessage(content)
    })
  }

  // Chat form (in chat mode)
  if (chatForm) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault()
      const content = chatInput ? chatInput.value.trim() : ''
      if (chatInput) chatInput.value = ''
      chat.sendMessage(content)
    })
  }

  // New conversation
  if (newConversationBtn) {
    newConversationBtn.addEventListener('click', () => chat.clearChat())
  }

  // Confirmation buttons
  if (confirmBtn) {
    confirmBtn.addEventListener('click', confirmExtraction)
  }
  if (clarifyBtn) {
    clarifyBtn.addEventListener('click', requestClarification)
  }

  // Clear case info
  if (clearCaseBtn) {
    clearCaseBtn.addEventListener('click', clearCaseInfo)
  }

  // Run init
  init()
}

// Register home page component
registerComponent('homePage', createHomePage)
