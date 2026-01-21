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

  renderMarkdown(text) {
    if (!text) return ''
    return text
      .replace(/\\+/g, '')
      .replace(/<!--.*?-->/g, '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/_([^_]+)_/g, '<em>$1</em>')
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
        '<a href="$2" class="text-primary-600 underline" target="_blank" rel="noopener noreferrer">$1</a>'
      )
      .replace(/^\d+[.\\]+\s+(.+)$/gm, '<li>$1</li>')
      .replace(/^[\*\-]\s+(.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>\n?)+/g, '<ul class="list-disc ml-4 my-2">$&</ul>')
      .replace(/^###\s+(.+)$/gm, '<h4 class="font-semibold mt-3 mb-1">$1</h4>')
      .replace(
        /^##\s+(.+)$/gm,
        '<h3 class="font-semibold text-lg mt-3 mb-1">$1</h3>'
      )
      .replace(/\n\n+/g, '</p><p class="my-2">')
      .replace(/\n/g, '<br>')
      .replace(/^(.+)$/, '<p class="my-2">$1</p>')
  },

  async parseStream(response, callbacks = {}) {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    const state = {
      sessionId: null,
      content: '',
      toolCalls: [],
      toolResponses: [],
    }

    const {
      onSession = () => {},
      onContentDelta = () => {},
      onToolCall = () => {},
      onToolResponse = () => {},
      onDone = () => {},
      onError = () => {},
    } = callbacks

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

          switch (event.type) {
            case 'session':
              state.sessionId = event.session_id
              onSession(event.session_id)
              break

            case 'content_delta':
              state.content += event.content || ''
              onContentDelta(state.content, event.content)
              break

            case 'tool_call':
              state.toolCalls.push({
                id: event.id,
                name: event.name,
                args: event.args,
              })
              onToolCall(event)
              break

            case 'tool_response':
              state.toolResponses.push({
                id: event.id,
                name: event.name,
                response: event.response,
                data: event.data,
              })
              onToolResponse(event)
              break

            case 'done':
              onDone(state)
              return state

            case 'error':
              onError(event.error, event.message)
              if (event.message) {
                state.content = event.message
                onContentDelta(state.content, event.message)
              }
              break
          }
        } catch (e) {
          // Ignore parse errors for incomplete chunks
        }
      }
    }

    return state
  },
}

/**
 * Chat Component
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('chat', () => ({
    sessionId: '',
    agentName: '',
    messages: [],
    inputText: '',
    isStreaming: false,
    chatAvailable: true,
    showUnavailableWarning: false,
    activeToolCall: null,

    async init() {
      this.sessionId = ''
      const status = await this.checkAvailability()
      this.chatAvailable = status.available
      this.showUnavailableWarning = !status.available
    },

    async checkAvailability() {
      try {
        const response = await fetch('/chat/status/')
        if (!response.ok) return { available: false, enabled: false }
        return await response.json()
      } catch (e) {
        return { available: false, enabled: false }
      }
    },

    dismissWarning() {
      this.showUnavailableWarning = false
    },

    async send() {
      const content = this.inputText.trim()
      if (!content || this.isStreaming) return

      this.inputText = ''
      this.isStreaming = true
      this.activeToolCall = null

      this.messages.push({
        id: Date.now(),
        role: 'user',
        content: content,
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
        if (this.sessionId) {
          formData.append('session_id', this.sessionId)
        }
        if (this.agentName) {
          formData.append('agent_name', this.agentName)
        }

        const response = await fetch('/chat/stream/', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.error || 'Failed to send message')
        }

        await chatUtils.parseStream(response, {
          onSession: (sessionId) => {
            this.sessionId = sessionId
            localStorage.setItem('chatSessionId', sessionId)
          },

          onContentDelta: (accumulated) => {
            this.messages[msgIndex] = {
              ...this.messages[msgIndex],
              content: accumulated,
            }
            this.scrollToBottom()
          },

          onToolCall: (event) => {
            this.activeToolCall = { name: event.name, args: event.args }
            this.messages[msgIndex].toolCalls.push({
              id: event.id,
              name: event.name,
              args: event.args,
            })
            this.scrollToBottom()
          },

          onToolResponse: (event) => {
            this.activeToolCall = null
            this.messages[msgIndex].toolResponses.push({
              id: event.id,
              name: event.name,
              response: event.response,
              data: event.data,
            })
            this.scrollToBottom()
          },

          onDone: (state) => {
            this.messages[msgIndex] = {
              ...this.messages[msgIndex],
              content: state.content,
              toolCalls: state.toolCalls,
              toolResponses: state.toolResponses,
            }
          },

          onError: (error, message) => {
            console.error('Stream error:', error)
            if (message) {
              this.messages[msgIndex] = {
                ...this.messages[msgIndex],
                content: message,
              }
            }
          },
        })
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

    scrollToBottom(force = false) {
      this.$nextTick(() => {
        const el = this.$refs.messages || this.$refs.messagesArea
        if (el) {
          const isNearBottom =
            el.scrollHeight - el.scrollTop - el.clientHeight < 150
          if (force || isNearBottom) {
            el.scrollTop = el.scrollHeight
          }
        }
      })
    },

    clear() {
      this.messages = []
      this.sessionId = ''
      localStorage.removeItem('chatSessionId')
    },

    // Aliases for template compatibility
    askQuestion() {
      return this.send()
    },
    clearChat() {
      return this.clear()
    },
    sendMessage() {
      return this.send()
    },
    get dynamicMessages() {
      return this.messages
    },

    escapeHtml: chatUtils.escapeHtml,
    renderMarkdown: chatUtils.renderMarkdown,
  }))
})
