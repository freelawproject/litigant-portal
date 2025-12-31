/**
 * Chat Utilities
 * Shared functions for chat components.
 */
const chatUtils = {
  // Check if chat service is available
  async checkAvailability() {
    try {
      const response = await fetch('/chat/status/')
      if (!response.ok) return { available: false, enabled: false }
      return await response.json()
    } catch (e) {
      return { available: false, enabled: false }
    }
  },

  // Get CSRF token from form or cookie
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

  // Escape HTML for user messages
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
  renderMarkdown(text) {
    if (!text) return ''
    return (
      text
        // Strip LLM artifacts
        .replace(/\\+/g, '') // Backslash escapes (e.g., \\Address:\\ → Address:)
        .replace(/<!--.*?-->/g, '') // HTML comments
        // Escape HTML first
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

  // Parse SSE stream and call onToken for each token
  async parseStream(response, onToken, onError) {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let accumulatedContent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()

          if (data === '[DONE]') {
            return accumulatedContent
          }

          try {
            const parsed = JSON.parse(data)
            if (parsed.token) {
              accumulatedContent += parsed.token
              onToken(accumulatedContent)
            } else if (parsed.error) {
              console.error('Stream error:', parsed.error)
              if (parsed.message) {
                accumulatedContent = parsed.message
                onToken(accumulatedContent)
              }
            }
          } catch (e) {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    }

    return accumulatedContent
  },
}

/**
 * Chat Window Component
 * Alpine.js component for managing chat conversations with streaming responses.
 *
 * Usage:
 *   <div x-data="chatWindow('session-id-here')" x-init="init()">
 *     ...
 *   </div>
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('chatWindow', (initialSessionId = '') => ({
    // State
    sessionId: initialSessionId,
    dynamicMessages: [],
    inputText: '',
    isStreaming: false,
    chatAvailable: true,
    showUnavailableWarning: false,

    // Initialize component
    async init() {
      // Restore session from localStorage if not provided
      if (!this.sessionId) {
        this.sessionId = localStorage.getItem('chatSessionId') || ''
      }

      // Check if chat service is available
      const status = await chatUtils.checkAvailability()
      this.chatAvailable = status.available
      this.showUnavailableWarning = !status.available
    },

    dismissWarning() {
      this.showUnavailableWarning = false
    },

    // Send a message
    async sendMessage() {
      const content = this.inputText.trim()
      if (!content || this.isStreaming) return

      // Clear input immediately
      this.inputText = ''

      // Add user message to UI
      this.dynamicMessages.push({
        id: Date.now(),
        role: 'user',
        content: content,
      })

      // Send to server
      try {
        const formData = new FormData()
        formData.append('message', content)
        formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())

        const response = await fetch('/chat/send/', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.error || 'Failed to send message')
        }

        const data = await response.json()
        this.sessionId = data.session_id
        localStorage.setItem('chatSessionId', this.sessionId)

        // Start streaming response
        await this.streamResponse()
      } catch (error) {
        console.error('Chat error:', error)
        this.dynamicMessages.push({
          id: Date.now(),
          role: 'assistant',
          content:
            'Sorry, I encountered an error. Please try again or use the search feature.',
        })
      }
    },

    // Stream AI response via SSE
    async streamResponse() {
      this.isStreaming = true

      // Add empty assistant message that will be filled
      const messageId = Date.now()
      const messageIndex = this.dynamicMessages.length
      this.dynamicMessages.push({
        id: messageId,
        role: 'assistant',
        content: '',
      })

      try {
        const response = await fetch(`/chat/stream/${this.sessionId}/`)

        if (!response.ok) {
          throw new Error('Stream connection failed')
        }

        await chatUtils.parseStream(response, (content) => {
          this.dynamicMessages[messageIndex] = {
            id: messageId,
            role: 'assistant',
            content: content,
          }
        })
      } catch (error) {
        console.error('Stream error:', error)
        if (!this.dynamicMessages[messageIndex].content) {
          this.dynamicMessages[messageIndex] = {
            id: messageId,
            role: 'assistant',
            content:
              'Sorry, I encountered an error while generating a response.',
          }
        }
      } finally {
        this.isStreaming = false
      }
    },

    // Scroll messages container to bottom (only if user is near bottom)
    scrollToBottom(force = false) {
      this.$nextTick(() => {
        if (this.$refs.messages) {
          const el = this.$refs.messages
          const isNearBottom =
            el.scrollHeight - el.scrollTop - el.clientHeight < 150
          if (force || isNearBottom) {
            el.scrollTop = el.scrollHeight
          }
        }
      })
    },

    // Clear chat history
    clearChat() {
      this.dynamicMessages = []
      this.sessionId = ''
      localStorage.removeItem('chatSessionId')
    },

    // Delegate to shared utilities
    escapeHtml: chatUtils.escapeHtml,
    renderMarkdown: chatUtils.renderMarkdown,
  }))

  /**
   * Home Page Component
   * Chat-first experience with AI assistance.
   */
  Alpine.data('homePage', () => ({
    // State
    sessionId: '',
    messages: [],
    inputText: '',
    isStreaming: false,
    chatAvailable: true,
    showUnavailableWarning: false,

    async init() {
      // Restore session from localStorage
      this.sessionId = localStorage.getItem('chatSessionId') || ''

      // Check if chat service is available
      const status = await chatUtils.checkAvailability()
      this.chatAvailable = status.available
      this.showUnavailableWarning = !status.available
    },

    dismissWarning() {
      this.showUnavailableWarning = false
    },

    // Send a question
    async askQuestion() {
      const content = this.inputText.trim()
      if (!content || this.isStreaming) return

      this.inputText = ''

      // Add user message
      this.messages.push({
        id: Date.now(),
        role: 'user',
        content: content,
      })
      this.scrollToBottom()

      // Send to server and stream response
      try {
        const formData = new FormData()
        formData.append('message', content)
        formData.append('csrfmiddlewaretoken', chatUtils.getCsrfToken())

        const response = await fetch('/chat/send/', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          throw new Error('Failed to send message')
        }

        const data = await response.json()
        this.sessionId = data.session_id
        localStorage.setItem('chatSessionId', this.sessionId)

        await this.streamResponse()
      } catch (error) {
        console.error('Chat error:', error)
        this.messages.push({
          id: Date.now(),
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
        })
      }
    },

    // Stream AI response
    async streamResponse() {
      this.isStreaming = true

      const messageId = Date.now()
      const messageIndex = this.messages.length
      this.messages.push({
        id: messageId,
        role: 'assistant',
        content: '',
      })
      this.scrollToBottom()

      try {
        const response = await fetch(`/chat/stream/${this.sessionId}/`)
        if (!response.ok) throw new Error('Stream failed')

        await chatUtils.parseStream(response, (content) => {
          this.messages[messageIndex] = {
            id: messageId,
            role: 'assistant',
            content: content,
          }
        })
      } catch (error) {
        console.error('Stream error:', error)
        if (!this.messages[messageIndex].content) {
          this.messages[messageIndex] = {
            id: messageId,
            role: 'assistant',
            content: 'Sorry, I encountered an error.',
          }
        }
      } finally {
        this.isStreaming = false
      }
    },

    // Clear chat and start new conversation
    clearChat() {
      this.messages = []
      this.sessionId = ''
      localStorage.removeItem('chatSessionId')
    },

    // Scroll to bottom of messages
    scrollToBottom() {
      this.$nextTick(() => {
        if (this.$refs.messagesArea) {
          this.$refs.messagesArea.scrollTop =
            this.$refs.messagesArea.scrollHeight
        }
      })
    },

    // Delegate to shared utilities
    escapeHtml: chatUtils.escapeHtml,
    renderMarkdown: chatUtils.renderMarkdown,
  }))
})
