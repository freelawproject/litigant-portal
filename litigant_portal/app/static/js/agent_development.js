document.addEventListener('alpine:init', () => {
  Alpine.data('agentDevelopment', () => ({
    initialized: false,
    running: false,
    selectedCourt: '',
    conversationId: '',
    status: '',
    error: '',
    errorCode: '',
    runId: '',
    messages: [],
    events: [],
    progress: {},
    draft: '',
    configurationSummary: '',
    conversationView: {
      following: true,
      top: 0,
      feedback: '',
      copyTimer: null,
    },
    eventsView: { following: true, top: 0, feedback: '', copyTimer: null },
    scrollFrame: null,

    get sendDisabled() {
      return !this.initialized || this.running || !this.draft.trim()
    },
    get configurationLocked() {
      return this.running || !!this.conversationId
    },
    get conversationEmpty() {
      return this.messages.length === 0
    },
    get eventsEmpty() {
      return this.events.length === 0
    },
    get conversationPaused() {
      return !this.conversationView.following
    },
    get eventsPaused() {
      return !this.eventsView.following
    },
    get failureDetails() {
      return [
        this.errorCode,
        this.runId ? `${gettext('Run ID')}: ${this.runId}` : '',
      ]
        .filter(Boolean)
        .join(' · ')
    },
    get progressSummary() {
      if (!this.progress.procedure) return ''
      const phase =
        this.progress.current_phase?.title || gettext('Preparation complete')
      return `${this.progress.title}: ${phase} (${this.progress.percent_complete}%)`
    },

    messageEntry(entry) {
      const isUser = entry.role === 'user'
      return {
        ...entry,
        label: isUser ? gettext('You') : gettext('Assistant'),
        isUser,
        isAssistant: !isUser,
        alignmentClass: isUser ? 'items-end' : 'items-start',
        bubbleClass: isUser
          ? 'bg-primary-50 text-greyscale-900'
          : 'bg-greyscale-100 text-greyscale-900',
        sources: this.sources(entry.sources),
        get html() {
          return this.isAssistant ? renderMarkdown(this.text) : ''
        },
        get pending() {
          return !!this.waiting && !this.text
        },
        get hasSources() {
          return this.sources.length > 0
        },
      }
    },

    updateConfigurationSummary() {
      const fields = this.$root.elements
      const label = (name, fallback) =>
        fields[name].value
          ? fields[name].selectedOptions[0].textContent.trim()
          : fallback
      this.configurationSummary = [
        label('court', gettext('Court: choose through chat')),
        label('topic', gettext('Topic: choose through chat')),
        label('model', gettext('Choose an assistant model')),
      ].join(' · ')
    },

    updateMessage() {
      const input = this.$root.elements.message
      this.draft = input.value
      input.style.height = 'auto'
      input.style.height = `${input.scrollHeight}px`
    },

    handleMessageKeydown(event) {
      if (
        event.key !== 'Enter' ||
        event.shiftKey ||
        event.isComposing ||
        event.keyCode === 229
      )
        return
      event.preventDefault()
      if (!event.repeat) this.send()
    },

    resizePanels() {
      this.updateMessage()
      for (const panel of ['conversation', 'events'])
        this[`${panel}View`].top = this.$refs[panel].scrollTop
      this.queueScroll()
    },

    trackScroll(event) {
      const element = event.currentTarget
      if (!element.clientHeight) return
      const view = this[`${element.dataset.panel}View`]
      const atBottom =
        element.scrollHeight - element.scrollTop - element.clientHeight <= 48
      if (atBottom) view.following = true
      // Only upward movement pauses following. A growing response can make a
      // queued programmatic scroll event appear far from the new bottom.
      else if (element.scrollTop < view.top) view.following = false
      view.top = element.scrollTop
    },

    queueScroll() {
      if (this.scrollFrame !== null) return
      this.scrollFrame = requestAnimationFrame(async () => {
        await this.$nextTick()
        for (const panel of ['conversation', 'events']) {
          if (panel === 'events' && !this.$refs.eventsDisclosure.open) continue
          const view = this[`${panel}View`]
          const element = this.$refs[panel]
          if (view.following) {
            element.scrollTop = element.scrollHeight
            view.top = element.scrollTop
          }
        }
        this.scrollFrame = null
      })
    },

    jumpToLatest(event) {
      const panel = event.currentTarget.dataset.panel
      this[`${panel}View`].following = true
      this.queueScroll()
      this.$refs[panel].focus({ preventScroll: true })
    },

    eventsToggled() {
      if (this.$refs.eventsDisclosure.open) this.queueScroll()
    },

    resetPanel(panel) {
      const view = this[`${panel}View`]
      clearTimeout(view.copyTimer)
      view.following = true
      view.top = 0
      view.feedback = ''
    },

    async copyPanel(event) {
      const panel = event.currentTarget.dataset.panel
      const content =
        panel === 'conversation'
          ? this.messages
              .filter((entry) => entry.text || entry.sources.length)
              .map((entry) => {
                const sources = entry.sources.map(
                  (source) => `${source.title}: ${source.url}`
                )
                return [`${entry.label}:\n${entry.text}`, ...sources].join('\n')
              })
              .join('\n\n')
          : this.events.map((entry) => entry.text).join('\n\n')
      if (!content) return
      const view = this[`${panel}View`]
      clearTimeout(view.copyTimer)
      view.feedback = ''
      try {
        await navigator.clipboard.writeText(content)
        view.feedback = gettext('Copied')
        view.copyTimer = setTimeout(() => {
          view.feedback = ''
        }, 2000)
      } catch {
        view.feedback = gettext(
          'Copy failed. Select the text and copy it manually.'
        )
      }
    },

    destroy() {
      cancelAnimationFrame(this.scrollFrame)
      clearTimeout(this.conversationView.copyTimer)
      clearTimeout(this.eventsView.copyTimer)
    },

    sources(items) {
      return (items || [])
        .filter(
          (source) =>
            typeof source.locator === 'string' &&
            (/^https:\/\//.test(source.locator) ||
              /^\/(?!\/)/.test(source.locator))
        )
        .map((source) => ({ ...source, url: source.locator }))
    },

    setConversation(id) {
      this.conversationId = id
      const url = new URL(window.location.href)
      if (id) url.searchParams.set('conversation_id', id)
      else url.searchParams.delete('conversation_id')
      window.history.replaceState(null, '', url)
    },

    async init() {
      this.status = gettext('Ready')
      this.selectCourt()
      const id = new URL(window.location.href).searchParams.get(
        'conversation_id'
      )
      try {
        if (id) {
          if (!/^[0-9a-f-]{36}$/i.test(id))
            throw new Error(gettext('Conversation is unavailable.'))
          this.conversationId = id
          const url = this.$root.dataset.conversationUrl.replace(
            '00000000-0000-0000-0000-000000000000',
            id
          )
          const response = await fetch(url, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
          })
          if (
            !response.headers.get('Content-Type')?.includes('application/json')
          )
            throw new Error(
              gettext('Please sign in again and reload this page.')
            )
          const data = await response.json()
          if (!response.ok)
            throw new Error(
              data.error || gettext('Conversation is unavailable.')
            )
          this.setScope(data.scope)
          if (data.model) this.$root.elements.model.value = data.model
          if (data.judge) this.$root.elements.judge.value = data.judge
          this.messages = data.messages.map((entry) => this.messageEntry(entry))
          this.progress = data.progress
        }
      } catch (failure) {
        this.error =
          failure.message || gettext('Unable to restore the conversation.')
      } finally {
        this.updateConfigurationSummary()
        this.updateMessage()
        this.initialized = true
        this.queueScroll()
      }
    },

    setScope(scope) {
      const form = this.$root
      form.elements.court.value = scope.court || ''
      this.selectedCourt = scope.court || ''
      form.elements.topic.value = scope.topic || ''
      this.updateConfigurationSummary()
    },

    selectCourt() {
      const form = this.$root
      this.selectedCourt = form.elements.court.value
      const topic = form.elements.topic
      const selected = topic.selectedOptions[0]
      if (
        this.selectedCourt &&
        selected?.value &&
        selected.dataset.court !== this.selectedCourt
      )
        topic.value = ''
      this.updateConfigurationSummary()
    },

    newConversation() {
      if (this.running) return
      this.setConversation('')
      this.setScope({})
      this.messages = []
      this.events = []
      this.progress = {}
      this.error = ''
      this.errorCode = ''
      this.runId = ''
      this.status = gettext('Ready')
      this.resetPanel('conversation')
      this.resetPanel('events')
      this.queueScroll()
      this.$root.elements.message.focus({ preventScroll: true })
    },

    async send() {
      const form = this.$root
      if (this.sendDisabled) return
      if (!form.checkValidity()) {
        const invalid = form.querySelector(':invalid')
        if (this.$refs.configuration.contains(invalid))
          this.$refs.configuration.open = true
        await this.$nextTick()
        form.reportValidity()
        return
      }
      const data = new FormData(form)
      for (const name of ['court', 'topic', 'model', 'judge'])
        data.set(name, form.elements[name].value)
      if (this.conversationId) data.set('conversation_id', this.conversationId)
      const message = data.get('message')
      form.elements.message.value = ''
      this.updateMessage()
      this.running = true
      this.error = ''
      this.errorCode = ''
      this.runId = ''
      this.status = gettext('Starting')
      this.messages.push(
        this.messageEntry({
          id: `user:${this.messages.length}`,
          role: 'user',
          text: message,
        })
      )
      const answerIndex = this.messages.length
      this.messages.push(
        this.messageEntry({
          id: `assistant:${answerIndex}`,
          role: 'assistant',
          text: '',
          waiting: true,
        })
      )
      this.events = []
      this.resetPanel('conversation')
      this.resetPanel('events')
      this.queueScroll()
      let reader
      let completed = false
      const receive = (line) => {
        const event = JSON.parse(line)
        this.events.push({
          id: this.events.length,
          text: JSON.stringify(event, null, 2),
        })
        this.queueScroll()
        if (event.error) throw new Error(event.error)
        if (event.run_id) this.runId = event.run_id
        if (event.conversation_id) this.setConversation(event.conversation_id)
        const payload = event.payload
        if (payload.type === 'text')
          this.messages[answerIndex].text += payload.delta
        if (payload.type === 'status') this.status = payload.status.state
        if (payload.type === 'tool') {
          if (payload.name === 'scope_selection') this.setScope(payload.data)
          if (payload.name === 'preparation_progress')
            this.progress = payload.data
          if (payload.name === 'judge_and_retry' && payload.state === 'started')
            this.status = gettext('Checking answer')
          if (payload.name === 'model_response' && payload.state === 'started')
            this.status = gettext('Preparing answer')
        }
        if (payload.type === 'outcome') {
          completed = true
          this.status = payload.outcome.state
          if (payload.outcome.state === 'completed') {
            this.messages[answerIndex].text = payload.outcome.text
            this.messages[answerIndex].sources = this.sources(
              payload.outcome.sources
            )
          }
          if (payload.outcome.state === 'failed') {
            this.error = payload.outcome.error.message
            this.errorCode = payload.outcome.error.code
            this.messages[answerIndex].text = this.error
            this.messages[answerIndex].sources = []
          }
        }
      }
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: data,
          credentials: 'same-origin',
          headers: { Accept: 'application/x-ndjson' },
        })
        if (!response.ok) {
          if (
            response.headers.get('Content-Type')?.includes('application/json')
          ) {
            const body = await response.json()
            throw new Error(
              body.error ||
                Object.values(body.errors || {})
                  .flat()
                  .join(' ')
            )
          }
          throw new Error(
            gettext('Unable to send. Check your login and developer access.')
          )
        }
        if (
          !response.headers
            .get('Content-Type')
            ?.includes('application/x-ndjson')
        )
          throw new Error(gettext('Please sign in again and reload this page.'))
        reader = response.body.getReader()
        const decoder = new TextDecoder()
        let pending = ''
        while (true) {
          const { value, done } = await reader.read()
          pending += done
            ? decoder.decode()
            : decoder.decode(value, { stream: true })
          const lines = pending.split('\n')
          pending = lines.pop()
          for (const line of lines) {
            if (line.trim()) receive(line)
            if (completed) break
          }
          if (done || completed) break
        }
        if (!completed && pending.trim()) receive(pending)
        if (!completed)
          throw new Error(
            gettext('The connection ended before the response finished.')
          )
      } catch (failure) {
        this.status = gettext('Failed')
        this.error =
          failure.message || gettext('Unable to complete the response.')
        this.messages[answerIndex].text = this.error
        this.messages[answerIndex].sources = []
      } finally {
        this.running = false
        this.messages[answerIndex].waiting = false
        this.queueScroll()
        if (reader) {
          try {
            await reader.cancel()
          } catch {
            /* The connection may already be closed. */
          }
          reader.releaseLock()
        }
        await this.$nextTick()
        form.elements.message.focus({ preventScroll: true })
      }
    },
  }))
  Alpine.data('agentTopicOption', () => ({
    get unavailable() {
      return (
        !!this.selectedCourt && this.$el.dataset.court !== this.selectedCourt
      )
    },
  }))
})
