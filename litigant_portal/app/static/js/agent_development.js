document.addEventListener('alpine:init', () => {
  Alpine.data('agentDevelopment', () => ({
    initialized: false,
    running: false,
    started: false,
    selectedCourt: '',
    status: '',
    error: '',
    message: '',
    answer: '',
    events: [],

    get sendDisabled() {
      return !this.initialized || this.running
    },

    get conversationEmpty() {
      return !this.started
    },

    get eventsEmpty() {
      return this.events.length === 0
    },

    init() {
      this.status = gettext('Ready')
      this.selectCourt()
      this.initialized = true
    },

    selectCourt() {
      const form = this.$root
      this.selectedCourt = form.elements.court.value
      const topic = form.elements.topic
      const selected = topic.selectedOptions[0]
      if (selected?.value && selected.dataset.court !== this.selectedCourt)
        topic.value = ''
    },

    async send() {
      const form = this.$root
      if (this.sendDisabled || !form.reportValidity()) return
      const data = new FormData(form)
      form.elements.message.value = ''
      this.running = true
      this.started = true
      this.error = ''
      this.status = gettext('Starting')
      this.message = data.get('message')
      this.answer = ''
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
        const payload = event.payload
        if (payload.type === 'text') this.answer += payload.delta
        if (payload.type === 'status') this.status = payload.status.state
        if (payload.type === 'outcome') {
          completed = true
          this.status = payload.outcome.state
          if (payload.outcome.state === 'completed')
            this.answer = payload.outcome.text
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
        ) {
          throw new Error(gettext('Please sign in again and reload this page.'))
        }
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
      return this.$el.dataset.court !== this.selectedCourt
    },
  }))
})
