const agentDevelopmentForm = document.getElementById('agent-development-form')

if (agentDevelopmentForm) {
  const form = agentDevelopmentForm
  const court = form.elements.court
  const topic = form.elements.topic
  const send = document.getElementById('agent-send')
  const conversation = document.getElementById('agent-conversation')
  const events = document.getElementById('agent-events')
  const status = document.getElementById('agent-status')
  const error = document.getElementById('agent-error')
  const controls = [
    court,
    topic,
    form.elements.model,
    form.elements.max_active_seconds,
    form.elements.message,
    send,
  ]
  let running = false

  function filterTopics() {
    for (const option of topic.options) {
      const unavailable = Boolean(
        option.value && (!court.value || option.dataset.court !== court.value)
      )
      option.hidden = unavailable
      option.disabled = unavailable
    }
    if (topic.selectedOptions[0]?.disabled) topic.value = ''
  }

  function addMessage(label, text) {
    const entry = document.createElement('div')
    const heading = document.createElement('strong')
    const content = document.createElement('p')
    heading.textContent = label
    content.textContent = text
    entry.append(heading, content)
    conversation.append(entry)
    return content
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    if (running || !form.reportValidity()) return
    const data = new FormData(form)
    running = true
    controls.forEach((control) => {
      control.disabled = true
    })
    error.textContent = ''
    status.textContent = gettext('Starting')
    conversation.replaceChildren()
    events.replaceChildren()
    addMessage(gettext('You'), data.get('message'))
    const answer = addMessage(gettext('Assistant'), '')
    let reader
    let completed = false

    function receive(line) {
      const event = JSON.parse(line)
      const entry = document.createElement('pre')
      entry.className = 'text-xs whitespace-pre-wrap break-all mb-3'
      entry.textContent = JSON.stringify(event, null, 2)
      events.append(entry)
      if (event.error) throw new Error(event.error)
      const payload = event.payload
      if (payload.type === 'text')
        answer.append(document.createTextNode(payload.delta))
      if (payload.type === 'status') status.textContent = payload.status.state
      if (payload.type === 'outcome') {
        completed = true
        status.textContent = payload.outcome.state
        if (payload.outcome.state === 'completed')
          answer.textContent = payload.outcome.text
        if (payload.outcome.state === 'failed')
          error.textContent = payload.outcome.error.message
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
        !response.headers.get('Content-Type')?.includes('application/x-ndjson')
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
      status.textContent = gettext('Failed')
      error.textContent =
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
      running = false
      controls.forEach((control) => {
        control.disabled = false
      })
      form.elements.message.focus()
    }
  })

  court.addEventListener('change', filterTopics)
  filterTopics()
  send.disabled = false
}
