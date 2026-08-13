// Admin Simulate tab — drives a conversation between the simulated-user
// actor and the litigant assistant. Each Play turn is two streams through
// the neutral chat engine: the actor's thread decides what the "person"
// says (its text never renders directly; it becomes the user message), and
// the assistant's thread renders exactly like the real chat page.
//
// Depends on chat_engine.js (loaded globally via base.html) for the
// message-part builders: makeMessage, messageAttachment, makeToolFromCall,
// computeToolFlags, buildItem, prettyJson, renderMarkdown, formatSize,
// fileStyle.

// Opening nudge for the actor's very first turn — stored on the actor
// thread only, never shown in the conversation view.
const SIM_KICKOFF =
  "(You've just opened the legal help chat. Send your first message.)"
// Fallback prompt when the assistant's turn somehow produced no text.
const SIM_NUDGE = '(The assistant is waiting for your reply.)'
const SIM_MAX_TURNS = 40

// Parse an SSE body, invoking onEvent per JSON frame. Mirrors chatApp's
// inline reader; kept standalone so any component can consume a stream.
async function readSimSse(res, onEvent) {
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
        onEvent(JSON.parse(payload))
      } catch (e) {
        // Ignore parse errors for partial chunks.
      }
    }
  }
}

document.addEventListener('alpine:init', () => {
  Alpine.data('simulateApp', () => ({
    base: '/api/admin/simulate/',
    // Simulated users
    simUsers: [],
    simUserOptions: [],
    simUserId: null,
    hasSimUser: false,
    noSimUser: true,
    simName: '',
    simStory: '',
    personaStatus: '',
    // Persona modal (persona fields + document bank)
    personaOpen: false,
    personaDisabled: true,
    // Document bank
    uploads: [],
    noUploads: true,
    uploadError: '',
    // Runs (assistant-side thread + its actor peer)
    runs: [],
    runOptions: [],
    runId: null,
    actorThreadId: null,
    // Conversation (chat-messages organism contract)
    messages: [],
    conversationEmpty: true,
    thinkingVisible: false,
    // Assistant-thread state, mirrored for the nested assistantBriefcase
    // component (the simulate root carries data-briefcase-host).
    stateData: {},
    // Briefcase panel: in-flow width-animated squish at lg+, overlay
    // drawer below lg. Both render off the same flag; the floating
    // toggle in the conversation shows only while closed.
    briefcaseOpen: false,
    notBriefcaseOpen: true,
    briefcasePanelClass: 'lg:w-0',
    // Loop state
    running: false,
    notRunning: true,
    playDisabled: true,
    statusLabel: '',
    turnCount: 0,

    async init() {
      await this.loadSimUsers()
      const first = this.simUsers[0]
      if (first) await this.applySimUser(first.id)
    },

    // --- Plumbing ---------------------------------------------------

    csrfToken() {
      const input = document.querySelector('[name=csrfmiddlewaretoken]')
      return input ? input.value : ''
    },

    async getJson(url) {
      const res = await fetch(url, {
        headers: { Accept: 'application/json' },
      })
      if (!res.ok) throw new Error('Request failed: ' + res.status)
      return res.json()
    },

    async postJson(url, data) {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken(),
        },
        body: JSON.stringify(data || {}),
      })
      if (!res.ok) throw new Error('Request failed: ' + res.status)
      return res.json()
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const el = this.$refs.messagesArea
        if (el) el.scrollTop = el.scrollHeight
      })
    },

    setStatus(label) {
      this.statusLabel = label
    },

    // --- Simulated users --------------------------------------------

    refreshSimUserFlags() {
      this.hasSimUser = !!this.simUserId
      this.noSimUser = !this.simUserId
      this.playDisabled = !this.simUserId
      this.personaDisabled = !this.simUserId
      this.simUserOptions = this.simUsers.map((u) => ({
        id: u.id,
        name: u.name,
        selected: u.id === this.simUserId,
      }))
    },

    async loadSimUsers() {
      try {
        const data = await this.getJson(this.base + 'users/')
        this.simUsers = data.simulated_users || []
      } catch (e) {
        console.error('Failed to load simulated users:', e)
        this.simUsers = []
      }
      this.refreshSimUserFlags()
    },

    async applySimUser(simId) {
      this.simUserId = simId
      const sim = this.simUsers.find((u) => u.id === simId)
      this.simName = sim ? sim.name : ''
      this.simStory = sim ? sim.story : ''
      this.personaStatus = ''
      this.refreshSimUserFlags()
      this.messages = []
      this.conversationEmpty = true
      this.stateData = {}
      this.runId = null
      this.actorThreadId = null
      this.turnCount = 0
      this.setStatus('')
      await Promise.all([this.loadUploads(), this.loadRuns()])
      const latest = this.runs[0]
      if (latest) await this.applyRun(latest.assistant_thread_id)
    },

    selectSimUser(e) {
      this.applySimUser(e.target.value)
    },

    async createSimUser() {
      try {
        const data = await this.postJson(this.base + 'users/create/', {})
        this.simUsers.push(data.simulated_user)
        await this.applySimUser(data.simulated_user.id)
      } catch (e) {
        console.error('Failed to create simulated user:', e)
      }
    },

    async deleteSimUser() {
      if (!this.simUserId) return
      if (!window.confirm('Delete this simulated user and all its runs?')) {
        return
      }
      try {
        await this.postJson(
          this.base + 'users/' + this.simUserId + '/delete/',
          {}
        )
      } catch (e) {
        console.error('Failed to delete simulated user:', e)
        return
      }
      this.personaOpen = false
      this.simUserId = null
      await this.loadSimUsers()
      const first = this.simUsers[0]
      if (first) await this.applySimUser(first.id)
      else {
        this.refreshSimUserFlags()
        this.messages = []
        this.conversationEmpty = true
        this.uploads = []
        this.noUploads = true
        this.runs = []
        this.runOptions = []
      }
    },

    toggleBriefcase() {
      this.briefcaseOpen = !this.briefcaseOpen
      this.notBriefcaseOpen = !this.briefcaseOpen
      this.briefcasePanelClass = this.briefcaseOpen
        ? 'lg:w-[40%] lg:border-l lg:border-greyscale-200'
        : 'lg:w-0'
    },

    closeBriefcase() {
      if (!this.briefcaseOpen) return
      this.toggleBriefcase()
    },

    // The briefcase card must show the simulated user's flow progress,
    // not the admin's, so its summary fetch is routed through the
    // sim-scoped endpoint (see assistantBriefcase's host contract).
    resolveSummaryUrl(ref) {
      return (
        this.base +
        'users/' +
        this.simUserId +
        '/topic-flow/' +
        ref.topic_slug +
        '/' +
        ref.flow_slug +
        '/summary/'
      )
    },

    openPersona() {
      if (!this.simUserId) return
      this.personaStatus = ''
      this.personaOpen = true
    },

    closePersona() {
      this.personaOpen = false
    },

    // Clicks inside the modal dialog must not reach the backdrop's close.
    stopClick(e) {
      e.stopPropagation()
    },

    updateSimName(e) {
      this.simName = e.target.value
    },

    updateSimStory(e) {
      this.simStory = e.target.value
    },

    async savePersona() {
      if (!this.simUserId) return
      this.personaStatus = 'Saving…'
      try {
        const data = await this.postJson(
          this.base + 'users/' + this.simUserId + '/update/',
          { name: this.simName, story: this.simStory }
        )
        const sim = data.simulated_user
        const row = this.simUsers.find((u) => u.id === sim.id)
        if (row) {
          row.name = sim.name
          row.story = sim.story
        }
        this.refreshSimUserFlags()
        this.personaStatus = 'Saved'
      } catch (e) {
        console.error('Failed to save persona:', e)
        this.personaStatus = 'Save failed'
      }
    },

    // --- Documents ---------------------------------------------------

    decorateDoc(upload) {
      return {
        ...upload,
        sizeLabel: formatSize(upload.size),
        tileClass: fileStyle(upload.content_type || '').tileClass,
      }
    },

    async loadUploads() {
      if (!this.simUserId) return
      try {
        const data = await this.getJson(
          this.base + 'users/' + this.simUserId + '/uploads/'
        )
        this.uploads = (data.uploads || []).map((u) => this.decorateDoc(u))
      } catch (e) {
        console.error('Failed to load documents:', e)
        this.uploads = []
      }
      this.noUploads = this.uploads.length === 0
    },

    pickFile() {
      const el = this.$refs.fileInput
      if (el) el.click()
    },

    async uploadFile(e) {
      const file = e.target.files && e.target.files[0]
      e.target.value = ''
      if (!file || !this.simUserId) return
      this.uploadError = ''
      const body = new FormData()
      body.append('file', file)
      body.append('csrfmiddlewaretoken', this.csrfToken())
      try {
        const res = await fetch(
          this.base + 'users/' + this.simUserId + '/uploads/create/',
          { method: 'POST', body }
        )
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          this.uploadError = data.error || 'Upload failed'
          return
        }
      } catch (err) {
        console.error('Failed to upload document:', err)
        this.uploadError = 'Upload failed'
        return
      }
      this.loadUploads()
    },

    async deleteUpload(e) {
      const uploadId = e.currentTarget.dataset.uploadId
      if (!uploadId || !this.simUserId) return
      try {
        await this.postJson(
          this.base +
            'users/' +
            this.simUserId +
            '/uploads/' +
            uploadId +
            '/delete/',
          {}
        )
      } catch (err) {
        console.error('Failed to delete document:', err)
      }
      this.loadUploads()
    },

    // --- Runs --------------------------------------------------------

    refreshRunOptions() {
      this.runOptions = this.runs.map((r, index) => ({
        id: r.assistant_thread_id,
        label: r.description || 'Run ' + (this.runs.length - index),
        selected: r.assistant_thread_id === this.runId,
      }))
    },

    async loadRuns() {
      if (!this.simUserId) return
      try {
        const data = await this.getJson(
          this.base + 'users/' + this.simUserId + '/runs/'
        )
        this.runs = data.runs || []
      } catch (e) {
        console.error('Failed to load runs:', e)
        this.runs = []
      }
      this.refreshRunOptions()
    },

    async applyRun(assistantThreadId) {
      const run = this.runs.find(
        (r) => r.assistant_thread_id === assistantThreadId
      )
      if (!run) return
      this.runId = run.assistant_thread_id
      this.actorThreadId = run.actor_thread_id
      this.turnCount = 0
      this.setStatus('')
      this.refreshRunOptions()
      await this.loadThread()
    },

    selectRun(e) {
      this.applyRun(e.target.value)
    },

    async newRun() {
      if (!this.simUserId) return
      try {
        const data = await this.postJson(
          this.base + 'users/' + this.simUserId + '/runs/create/',
          {}
        )
        this.runId = data.run.assistant_thread_id
        this.actorThreadId = data.run.actor_thread_id
        this.messages = []
        this.conversationEmpty = true
        this.stateData = {}
        this.turnCount = 0
        this.setStatus('')
        await this.loadRuns()
        this.refreshRunOptions()
      } catch (e) {
        console.error('Failed to create run:', e)
      }
    },

    async loadThread() {
      if (!this.simUserId || !this.runId) return
      try {
        const data = await this.getJson(
          this.base + 'users/' + this.simUserId + '/threads/' + this.runId + '/'
        )
        // Custom tool cards, same as the chat page. To debug with the
        // raw-JSON cards instead, pass true as buildItem's second arg
        // (and mirror it in handleAssistantEvent/applyToolResponse).
        this.messages = (data.items || []).map((item) => buildItem(item))
        this.stateData = data.state || {}
      } catch (e) {
        console.error('Failed to load run:', e)
        this.messages = []
        this.stateData = {}
      }
      this.conversationEmpty = this.messages.length === 0
      this.scrollToBottom()
    },

    // --- The run loop ------------------------------------------------

    // Everything the assistant said in its latest turn: all consecutive
    // trailing assistant text parts (a turn splits into several around
    // tool calls), skipping client-fabricated error bubbles.
    lastAssistantText() {
      const parts = []
      for (let i = this.messages.length - 1; i >= 0; i--) {
        const m = this.messages[i]
        if (m.isUser) break
        if (m.isAssistant && m.content && !m.localError) {
          parts.unshift(m.content)
        }
      }
      return parts.join('\n\n')
    },

    async play() {
      if (this.running || !this.simUserId) return
      if (!this.runId) await this.newRun()
      if (!this.runId) return
      this.running = true
      this.notRunning = false
      // The cap is per Play press, so a capped or resumed run can continue.
      this.turnCount = 0
      this.setStatus('')
      try {
        while (this.running && this.turnCount < SIM_MAX_TURNS) {
          const turn = await this.actorTurn()
          if (!turn) break
          // A turn with attachments but no words still has to deliver them.
          const text =
            turn.text || (turn.attachmentIds.length ? '(Sent a document.)' : '')
          if (!text && !turn.ended) {
            this.setStatus('Simulated user sent nothing; stopped.')
            break
          }
          if (text) {
            const ok = await this.assistantTurn(text, turn.attachmentIds)
            if (!ok) break
          }
          this.turnCount++
          if (turn.ended) {
            this.setStatus('Conversation ended')
            break
          }
          if (this.turnCount >= SIM_MAX_TURNS) {
            this.setStatus('Turn limit reached')
          }
        }
      } finally {
        // A Stop click cleared `running`; natural endings and failures set
        // their own status inside the loop and leave it intact here.
        if (!this.running) this.setStatus('Stopped')
        this.running = false
        this.notRunning = true
        this.thinkingVisible = false
        this.loadRuns()
      }
    },

    stop() {
      // Finish the in-flight turn, then halt before the next one.
      this.running = false
      this.setStatus('Stopping…')
    },

    // One actor turn: ask the simulator what the person says next.
    // Returns {text, attachmentIds, ended} or null on failure.
    async actorTurn() {
      const prompt =
        this.messages.length === 0
          ? SIM_KICKOFF
          : this.lastAssistantText() || SIM_NUDGE
      this.setStatus((this.simName || 'Simulated user') + ' is typing…')

      const body = new FormData()
      body.append('message', prompt)
      body.append('csrfmiddlewaretoken', this.csrfToken())
      if (this.actorThreadId) body.append('thread_id', this.actorThreadId)

      const turn = { text: '', attachmentIds: [], ended: false, failed: false }
      try {
        const res = await fetch(
          this.base + 'users/' + this.simUserId + '/actor/stream/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await readSimSse(res, (event) => {
          if (event.type === 'thread') {
            this.actorThreadId = event.thread_id
          } else if (event.type === 'content_delta') {
            turn.text += event.content || ''
          } else if (event.type === 'error') {
            // The engine reports LLM failures as an in-stream event on an
            // HTTP-200 response; without this the loop would spin.
            turn.failed = true
          } else if (event.type === 'tool_response') {
            const data = event.render_data || {}
            if (event.name === 'AttachUpload' && data.upload_ids) {
              turn.attachmentIds.push(...data.upload_ids)
            } else if (event.name === 'EndConversation') {
              turn.ended = true
            }
          }
        })
      } catch (e) {
        console.error('Actor turn failed:', e)
        this.setStatus('Simulated user failed to respond')
        return null
      }
      if (turn.failed) {
        this.setStatus('Simulated user failed to respond')
        return null
      }
      turn.text = turn.text.trim()
      turn.attachmentIds = [...new Set(turn.attachmentIds)]
      return turn
    },

    // A client-side error bubble: shown in the transcript but never
    // stored, and never fed back to the actor as assistant speech.
    pushLocalError(text) {
      const part = makeMessage('assistant', text)
      part.localError = true
      this.messages.push(part)
    },

    // One assistant turn: send the actor's message through the real
    // assistant stream and render it exactly like the chat page does.
    // Returns false when the turn failed, so the loop halts instead of
    // feeding error text back to the actor.
    async assistantTurn(text, attachmentIds) {
      const atts = (attachmentIds || [])
        .map((id) => this.uploads.find((u) => u.id === id))
        .filter(Boolean)
        .map(messageAttachment)
      this.messages.push(makeMessage('user', text, atts))
      this.conversationEmpty = false
      this.setStatus('Assistant is replying…')
      this.thinkingVisible = true
      this.scrollToBottom()

      const body = new FormData()
      body.append('message', text)
      body.append('csrfmiddlewaretoken', this.csrfToken())
      body.append('thread_id', this.runId)
      ;(attachmentIds || []).forEach((id) => body.append('attachment_ids', id))

      const stream = { openIndex: null, failed: false }
      try {
        const res = await fetch(
          this.base + 'users/' + this.simUserId + '/assistant/stream/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await readSimSse(res, (event) =>
          this.handleAssistantEvent(stream, event)
        )
      } catch (e) {
        console.error('Assistant turn failed:', e)
        stream.failed = true
        this.pushLocalError('Something went wrong on this turn.')
      }
      this.thinkingVisible = false
      this.scrollToBottom()
      if (stream.failed) this.setStatus('Assistant turn failed')
      return !stream.failed
    },

    handleAssistantEvent(stream, event) {
      if (event.type === 'content_delta') {
        this.appendContent(stream, event.content || '')
      } else if (event.type === 'tool_call') {
        stream.openIndex = null
        this.messages.push(makeToolFromCall(event))
      } else if (event.type === 'tool_response') {
        this.applyToolResponse(event)
      } else if (event.type === 'state') {
        this.stateData = event.state || {}
      } else if (event.type === 'description') {
        this.refreshRunOptions()
      } else if (event.type === 'error') {
        stream.failed = true
        this.pushLocalError(event.error || 'Something went wrong.')
      }
      this.updateThinking(stream)
      this.scrollToBottom()
    },

    appendContent(stream, text) {
      if (stream.openIndex === null) {
        this.messages.push(makeMessage('assistant', ''))
        stream.openIndex = this.messages.length - 1
      }
      const msg = this.messages[stream.openIndex]
      const content = msg.content + text
      this.messages[stream.openIndex] = {
        ...msg,
        content,
        html: renderMarkdown(content),
      }
    },

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

    // The thinking row shows while the assistant is between visible steps.
    updateThinking(stream) {
      const last = this.messages[this.messages.length - 1]
      if (last && last.isTool && last.status === 'calling') {
        this.thinkingVisible = false
      } else if (last && last.isAssistant && stream.openIndex !== null) {
        this.thinkingVisible = false
      } else {
        this.thinkingVisible = true
      }
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
  }))
})
