document.addEventListener('alpine:init', () => {
  Alpine.data('agentDevelopment', () => ({
    initialized: false,
    running: false,
    selectedCourt: '',
    conversationId: '',
    status: '',
    error: '',
    messages: [],
    events: [],
    progress: {},

    get sendDisabled() {
      return !this.initialized || this.running
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
    get progressSummary() {
      if (!this.progress.procedure) return ''
      const phase =
        this.progress.current_phase?.title || gettext('Preparation complete')
      return `${this.progress.title}: ${phase} (${this.progress.percent_complete}%)`
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
          this.messages = data.messages.map((entry) => ({
            ...entry,
            label:
              entry.role === 'user' ? gettext('You') : gettext('Assistant'),
            sources: this.sources(entry.sources),
          }))
          this.progress = data.progress
        }
      } catch (failure) {
        this.error =
          failure.message || gettext('Unable to restore the conversation.')
      } finally {
        this.initialized = true
      }
    },

    setScope(scope) {
      const form = this.$root
      form.elements.court.value = scope.court || ''
      this.selectedCourt = scope.court || ''
      form.elements.topic.value = scope.topic || ''
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
    },

    newConversation() {
      if (this.running) return
      this.setConversation('')
      this.setScope({})
      this.messages = []
      this.events = []
      this.progress = {}
      this.error = ''
      this.status = gettext('Ready')
      this.$root.elements.message.focus()
    },

    async send() {
      const form = this.$root
      if (this.sendDisabled || !form.reportValidity()) return
      const data = new FormData(form)
      for (const name of ['court', 'topic', 'model', 'judge'])
        data.set(name, form.elements[name].value)
      if (this.conversationId) data.set('conversation_id', this.conversationId)
      const message = data.get('message')
      form.elements.message.value = ''
      this.running = true
      this.error = ''
      this.status = gettext('Starting')
      this.messages.push({
        id: `user:${this.messages.length}`,
        role: 'user',
        label: gettext('You'),
        text: message,
        sources: [],
      })
      const answerIndex = this.messages.length
      this.messages.push({
        id: `assistant:${answerIndex}`,
        role: 'assistant',
        label: gettext('Assistant'),
        text: '',
        sources: [],
      })
      this.events = []
      let reader
      let completed = false
      const receive = (line) => {
        const event = JSON.parse(line)
        this.events.push({
          id: this.events.length,
          text: JSON.stringify(event, null, 2),
        })
        if (event.error) throw new Error(event.error)
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
          if (payload.outcome.state === 'failed')
            this.error = payload.outcome.error.message
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
          for (const line of lines) if (line.trim()) receive(line)
          if (done) break
        }
        if (pending.trim()) receive(pending)
        if (!completed)
          throw new Error(
            gettext('The connection ended before the response finished.')
          )
      } catch (failure) {
        this.status = gettext('Failed')
        this.error =
          failure.message || gettext('Unable to complete the response.')
      } finally {
        if (reader) {
          try {
            await reader.cancel()
          } catch {
            /* The connection may already be closed. */
          }
          reader.releaseLock()
        }
        this.running = false
        await this.$nextTick()
        form.elements.message.focus()
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
