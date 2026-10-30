const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/chat_engine.js'),
  'utf8'
)

function makeApp(
  fetchImpl = async () => {
    throw new Error('offline')
  }
) {
  const components = {}
  const context = {
    AbortController,
    FormData,
    TextDecoder,
    URLSearchParams,
    console: { ...console, error() {} },
    fetch: fetchImpl,
    setTimeout,
    clearTimeout,
    window: {},
    document: {
      body: {},
      activeElement: null,
      hasFocus() {
        return true
      },
      addEventListener(_name, callback) {
        callback()
      },
      querySelector() {
        return null
      },
    },
    Alpine: {
      data(name, factory) {
        components[name] = factory
      },
      $data() {
        return {}
      },
    },
  }
  vm.runInNewContext(source, context)
  const app = components.chatApp()
  app.base = '/api/agents/assistant/'
  app.threads = []
  app.$nextTick = (callback) => callback()
  app.$refs = {}
  app.loadThreads = async () => {}
  const updateThinking = app.updateThinking.bind(app)
  app.updateThinking = () => {}
  app.scrollToBottom = () => {}
  app.setThreadStatus = () => {}
  app.csrfToken = () => ''
  app.clearAttachments = () => {
    app.attachments = []
    app.hasAttachments = false
  }
  return { app, context, updateThinking }
}

function newStream(app) {
  const stream = {
    threadId: 'thread-id',
    messages: app.messages,
    openIndex: null,
    failureRendered: false,
    terminal: false,
    receivedFirstStreamEvent: false,
    inFlightToolIds: [],
    hadAssistantText: false,
    controller: new AbortController(),
  }
  app.activeStream = stream
  app.streaming = true
  return stream
}

function sse(type, fields = {}) {
  return new TextEncoder().encode(
    'data: ' + JSON.stringify({ type, ...fields }) + '\n\n'
  )
}

test('judging shows checking only on the attached stream and clears on progress or termination', () => {
  for (const type of [
    'heartbeat',
    'content_delta',
    'tool_call',
    'done',
    'error',
  ]) {
    const { app, updateThinking } = makeApp()
    app.updateThinking = updateThinking
    const stream = newStream(app)
    app.handleEvent(stream, { type: 'judging' })
    assert.equal(app.thinkingVisible, true)
    assert.equal(app.checkingVisible, true)
    assert.ok(stream.stallTimer)

    app.messages = []
    app.updateThinking()
    assert.equal(app.checkingVisible, false)
    app.messages = stream.messages
    app.updateThinking()
    assert.equal(app.checkingVisible, true)

    app.handleEvent(stream, {
      type,
      content: 'Answer',
      id: 'tool',
      name: 'LoadTopicFlow',
    })
    assert.equal(app.checkingVisible, false)
    app.handleEvent(stream, { type: 'done' })
    assert.equal(app.thinkingVisible, false)
  }
})

test('judging followed by silence reaches the fallback', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const { app, updateThinking } = makeApp()
  app.updateThinking = updateThinking
  const stream = newStream(app)
  app.handleEvent(stream, { type: 'judging' })
  t.mock.timers.tick(59000)
  assert.equal(stream.failureRendered, false)
  t.mock.timers.tick(1000)
  assert.equal(stream.failureRendered, true)
  assert.equal(stream.controller.signal.aborted, true)
  assert.equal(app.checkingVisible, false)
  assert.match(app.messages.at(-1).html, /Browse the help topics/)
})

test('heartbeats keep buffered work alive without rendering or scrolling', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  for (const checking of [false, true]) {
    const { app, updateThinking } = makeApp()
    app.updateThinking = updateThinking
    const stream = newStream(app)
    app.handleEvent(stream, { type: checking ? 'judging' : 'heartbeat' })
    app.scrollToBottom = () => assert.fail('heartbeat scrolled the view')
    for (let index = 0; index < 8; index++) {
      t.mock.timers.tick(10000)
      app.handleEvent(stream, { type: 'heartbeat' })
      assert.equal(stream.failureRendered, false)
      assert.equal(app.checkingVisible, false)
      assert.equal(app.messages.length, 0)
    }
    t.mock.timers.tick(59000)
    assert.equal(stream.failureRendered, false)
    app.scrollToBottom = () => {}
    t.mock.timers.tick(1000)
    assert.equal(stream.failureRendered, true)
  }
})

test('a background rewrite clears checking before reattaching and reviewing again', () => {
  const { app, updateThinking } = makeApp()
  app.updateThinking = updateThinking
  const stream = newStream(app)
  app.handleEvent(stream, { type: 'judging' })
  app.messages = []
  app.updateThinking()
  app.updateThinking = () =>
    assert.fail('background heartbeat updated the view')
  app.handleEvent(stream, { type: 'heartbeat' })
  app.messages = stream.messages
  app.updateThinking = updateThinking
  app.updateThinking()
  assert.equal(app.checkingVisible, false)
  app.handleEvent(stream, { type: 'judging' })
  assert.equal(app.checkingVisible, true)
  app.handleEvent(stream, { type: 'done' })
})

test('review warnings survive streaming, reload and copying without changing answer text', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  for (const warning of [false, true]) {
    const content = 'Answer [source:court/example]'
    const item = { kind: 'assistant', content }
    if (warning) item.review_warning = warning
    const { app, context } = makeApp(async () => ({
      ok: true,
      json: async () => ({ id: 'thread-id', items: [item] }),
    }))
    app.reviewWarningText = 'Current translated warning'
    let copied
    context.navigator = {
      clipboard: {
        writeText(text) {
          copied = text
        },
      },
    }
    const stream = newStream(app)
    app.handleEvent(stream, { type: 'content_delta', ...item })
    app.handleEvent(stream, { type: 'done' })
    assert.equal(app.messages[0].content, content)
    assert.equal(app.messages[0].reviewWarning, warning)
    app.activeStream = null
    app.streaming = false
    await app.openThread('thread-id')
    assert.equal(app.messages[0].content, content)
    assert.equal(app.messages[0].reviewWarning, warning)
    app.copyMessage({
      currentTarget: { dataset: { messageId: app.messages[0].id } },
    })
    assert.equal(
      copied,
      warning ? app.reviewWarningText + '\n\nAnswer' : 'Answer'
    )
  }
})

test('network drop uses the fallback card renderer', async () => {
  const { app } = makeApp(async () => {
    throw new Error('connection dropped')
  })

  await app.sendMessage('Help', null)

  const fallback = app.messages.at(-1)
  assert.match(fallback.html, /Browse the help topics/)
  assert.match(fallback.html, /href="\/"/)
  assert.equal(
    app.messages.filter((item) => item.html.includes('Browse the help topics'))
      .length,
    1
  )
  assert.equal(app.streaming, false)
})

test('external and protocol-relative fallback URLs become home links', () => {
  const { app } = makeApp()
  for (const fallbackUrl of [
    'https://evil.example',
    '//evil.example',
    '/\\evil.example',
  ]) {
    const stream = newStream(app)
    app.handleEvent(stream, {
      type: 'error',
      message: 'Safe copy',
      fallback_url: fallbackUrl,
      fallback_label: 'Continue',
    })
    assert.match(app.messages.at(-1).html, /href="\/"/)
  }
})

test('a stream drop preserves partial text and renders one incomplete fallback', () => {
  const { app } = makeApp()
  const stream = newStream(app)
  app.handleEvent(stream, { type: 'content_delta', content: 'Partial answer' })
  app.handleEvent(stream, {
    type: 'error',
    message: 'Safe error copy',
    fallback_url: '/t/franklin-county-oh/eviction/tenant/',
    fallback_label: 'Continue the eviction guide',
  })
  app.failStream(stream, { message: 'duplicate' })

  assert.equal(app.messages[0].content, 'Partial answer')
  assert.equal(app.messages[1].content, 'This response may be incomplete.')
  assert.match(app.messages[2].html, /Continue the eviction guide/)
  assert.equal(
    app.messages.filter((item) =>
      item.html.includes('Continue the eviction guide')
    ).length,
    1
  )
})

test('initial-response timeout resolves a silent initial stream', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const { app } = makeApp(async (_url, options) => ({
    ok: true,
    body: {
      getReader: () => ({
        read: () =>
          new Promise((_resolve, reject) => {
            if (options.signal.aborted) return reject(new Error('aborted'))
            options.signal.addEventListener('abort', () =>
              reject(new Error('aborted'))
            )
          }),
      }),
    },
  }))
  const pending = app.sendMessage('Help', null)
  for (let index = 0; index < 10; index++) await Promise.resolve()
  t.mock.timers.tick(30000)
  await pending

  assert.match(app.messages.at(-1).html, /Browse the help topics/)
  assert.equal(
    app.messages.filter((item) => item.html.includes('Browse the help topics'))
      .length,
    1
  )
})

test('early lifecycle events clear the initial deadline and reset the stall watchdog', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  for (const type of ['thread', 'state']) {
    let reads = 0
    let resolveRead
    const { app } = makeApp(async (_url, options) => ({
      ok: true,
      body: {
        getReader: () => ({
          read: () => {
            if (reads++ === 0) {
              return Promise.resolve({
                value: sse(type, { thread_id: 'thread-id', state: {} }),
                done: false,
              })
            }
            return new Promise((resolve, reject) => {
              resolveRead = resolve
              options.signal.addEventListener('abort', () =>
                reject(new Error('aborted'))
              )
            })
          },
          cancel: async () => {},
          releaseLock: () => {},
        }),
      },
    }))
    const pending = app.sendMessage('Help', null)
    for (let index = 0; index < 10; index++) await Promise.resolve()
    t.mock.timers.tick(30000)
    assert.equal(app.activeStream.failureRendered, false)
    assert.equal(app.streaming, true)

    resolveRead({ value: sse('state', { state: {} }), done: false })
    for (let index = 0; index < 10; index++) await Promise.resolve()
    t.mock.timers.tick(59000)
    assert.equal(app.activeStream.failureRendered, false)
    t.mock.timers.tick(1000)
    await pending
    assert.match(app.messages.at(-1).html, /Browse the help topics/)
    assert.equal(app.streaming, false)
  }
})

test('silent stall resolves after activity stops', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let released = false
  const { app } = makeApp(async (_url, options) => {
    let reads = 0
    return {
      ok: true,
      body: {
        getReader: () => ({
          read: () => {
            if (reads++ === 0) {
              return Promise.resolve({
                value: sse('content_delta', { content: 'Started' }),
                done: false,
              })
            }
            return new Promise((_resolve, reject) => {
              if (options.signal.aborted) return reject(new Error('aborted'))
              options.signal.addEventListener('abort', () =>
                reject(new Error('aborted'))
              )
            })
          },
          cancel: async () => {},
          releaseLock: () => {
            released = true
          },
        }),
      },
    }
  })
  const pending = app.sendMessage('Help', null)
  for (let index = 0; index < 10; index++) await Promise.resolve()
  t.mock.timers.tick(60000)
  await pending

  assert.equal(app.messages[1].content, 'Started')
  assert.equal(app.messages[2].content, 'This response may be incomplete.')
  assert.match(app.messages.at(-1).html, /Browse the help topics/)
  assert.equal(released, true)
})

test('tool response resumes the stall watchdog', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const { app } = makeApp()
  const stream = newStream(app)
  app.handleEvent(stream, { type: 'content_delta', content: 'A' })
  t.mock.timers.tick(59000)
  app.handleEvent(stream, {
    type: 'tool_call',
    id: 'call-1',
    name: 'tool',
    args: {},
  })
  t.mock.timers.tick(59000)
  assert.equal(stream.failureRendered, false)
  app.handleEvent(stream, {
    type: 'tool_response',
    id: 'call-1',
    render_mode: 'default',
    render_data: {},
  })
  t.mock.timers.tick(59000)
  assert.equal(stream.failureRendered, false)
  t.mock.timers.tick(1000)
  assert.equal(stream.failureRendered, true)
  assert.equal(
    app.messages.filter((item) => item.html.includes('Browse the help topics'))
      .length,
    1
  )
})

test('a tool can run longer than the stall interval, then a later stall fails', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let resolveToolResponse
  let reads = 0
  const { app } = makeApp(async (_url, options) => ({
    ok: true,
    body: {
      getReader: () => ({
        read: () => {
          reads++
          if (reads === 1) {
            return Promise.resolve({
              value: sse('tool_call', {
                id: 'call-1',
                name: 'tool',
                args: {},
                render_mode: 'default',
              }),
              done: false,
            })
          }
          if (reads === 2) {
            return new Promise((resolve) => {
              resolveToolResponse = resolve
            })
          }
          return new Promise((_resolve, reject) => {
            if (options.signal.aborted) return reject(new Error('aborted'))
            options.signal.addEventListener('abort', () =>
              reject(new Error('aborted'))
            )
          })
        },
        cancel: async () => {},
        releaseLock: () => {},
      }),
    },
  }))

  const pending = app.sendMessage('Help', null)
  for (let index = 0; index < 10; index++) await Promise.resolve()
  t.mock.timers.tick(120000)
  assert.equal(
    app.messages.some((item) => item.html.includes('Browse the help topics')),
    false
  )

  resolveToolResponse({
    value: sse('tool_response', {
      id: 'call-1',
      render_mode: 'default',
      render_data: { result: 'finished' },
    }),
    done: false,
  })
  for (let index = 0; index < 10; index++) await Promise.resolve()
  assert.equal(app.messages[1].status, 'done')
  assert.equal(
    app.messages.some((item) => item.html.includes('Browse the help topics')),
    false
  )

  t.mock.timers.tick(60000)
  await pending
  assert.match(app.messages.at(-1).html, /Browse the help topics/)
  assert.equal(app.streaming, false)
})

test('stream failure clears pending tool spinners and preserves completed cards', () => {
  const { app } = makeApp()
  const stream = newStream(app)
  app.handleEvent(stream, {
    type: 'tool_call',
    id: 'completed-call',
    name: 'completed tool',
    args: {},
    render_mode: 'custom',
  })
  app.handleEvent(stream, {
    type: 'tool_response',
    id: 'completed-call',
    render_mode: 'custom',
    render_html: '<p>Completed</p>',
  })
  app.handleEvent(stream, {
    type: 'tool_call',
    id: 'pending-call',
    name: 'pending tool',
    args: {},
    render_mode: 'custom',
  })

  app.failStream(stream)

  assert.equal(app.messages[0].status, 'done')
  assert.equal(app.messages[1].status, 'failed')
  assert.equal(app.messages[1].pending, false)
  assert.equal(app.messages[1].showCallCustom, false)
  assert.equal(
    app.messages.filter((item) => item.html.includes('Browse the help topics'))
      .length,
    1
  )
})

test('reader rejection after partial content preserves output and cleans up', async () => {
  let reads = 0
  let released = false
  const { app } = makeApp(async () => ({
    ok: true,
    body: {
      getReader: () => ({
        read: async () => {
          if (reads++ === 0) {
            return {
              value: sse('content_delta', { content: 'Partial answer' }),
              done: false,
            }
          }
          throw new Error('network read failed')
        },
        cancel: async () => {
          throw new Error('cancel cleanup failed')
        },
        releaseLock: () => {
          released = true
        },
      }),
    },
  }))

  await app.sendMessage('Help', null)

  assert.equal(app.messages[1].content, 'Partial answer')
  assert.equal(app.messages[2].content, 'This response may be incomplete.')
  assert.match(app.messages[3].html, /Browse the help topics/)
  assert.equal(
    app.messages.filter((item) => item.html.includes('Browse the help topics'))
      .length,
    1
  )
  assert.equal(app.streaming, false)
  assert.equal(app.activeStream, null)
  assert.equal(app.thinkingVisible, false)
  app.input = 'Follow up'
  app.refreshSendState()
  assert.equal(app.sendDisabled, false)
  assert.equal(released, true)
})

test('normal SSE completion keeps streamed output unchanged', async () => {
  let reads = 0
  let canceled = false
  let released = false
  const { app } = makeApp(async () => {
    const chunks = [
      sse('content_delta', { content: 'Healthy answer' }),
      sse('done'),
    ]
    return {
      ok: true,
      body: {
        getReader: () => ({
          read: async () => {
            reads++
            return chunks.length
              ? { value: chunks.shift(), done: false }
              : { value: undefined, done: true }
          },
          cancel: async () => {
            canceled = true
          },
          releaseLock: () => {
            released = true
          },
        }),
      },
    }
  })

  await app.sendMessage('Help', null)

  assert.equal(app.messages.at(-1).content, 'Healthy answer')
  assert.equal(
    app.messages.some((item) => item.html.includes('Browse the help topics')),
    false
  )
  assert.equal(reads, 2)
  assert.equal(canceled, true)
  assert.equal(released, true)
  assert.equal(app.streaming, false)
})

for (const scenario of [
  'normal completion',
  'judged completion',
  'request failure',
  'another control focused',
  'thread switched',
  'attachment dialog open',
  'delete confirmation open',
  'another stream started',
  'page inactive',
]) {
  test(`composer focus after ${scenario}`, async () => {
    const { app, context } = makeApp(async () => {
      if (scenario === 'request failure') throw new Error('offline')
      const chunks = [sse('content_delta', { content: 'Answer' }), sse('done')]
      if (scenario === 'judged completion') chunks.unshift(sse('judging'))
      return {
        ok: true,
        body: {
          getReader: () => ({
            read: async () => ({ value: chunks.shift(), done: false }),
            cancel: async () => {},
            releaseLock() {},
          }),
        },
      }
    })
    const callbacks = []
    let focused = false
    app.$nextTick = (callback) => callbacks.push(callback)
    app.$refs.input = {
      disabled: true,
      focus(options) {
        assert.equal(this.disabled, false)
        assert.equal(options.preventScroll, true)
        focused = true
      },
    }
    context.document.activeElement = context.document.body

    await app.sendMessage('Help', null)

    assert.equal(app.streaming, false)
    assert.equal(focused, false)
    // Alpine re-enables the input before nextTick callbacks run.
    app.$refs.input.disabled = false
    if (scenario === 'another control focused')
      context.document.activeElement = {}
    if (scenario === 'thread switched') app.messages = []
    if (scenario === 'attachment dialog open') app.attachOpen = true
    if (scenario === 'delete confirmation open') app.confirmingDelete = true
    if (scenario === 'another stream started') app.streaming = true
    if (scenario === 'page inactive') context.document.hasFocus = () => false
    callbacks.forEach((callback) => callback())

    assert.equal(
      focused,
      ['normal completion', 'judged completion', 'request failure'].includes(
        scenario
      )
    )
  })
}

// An upload batch gives each file a status row and announces the batch to
// screen readers when it starts and when it ends (#1124).
function storedUpload(name) {
  return {
    id: 'u-' + name,
    name,
    size: 10,
    content_type: 'application/pdf',
    is_image: false,
    created_at: new Date().toISOString(),
  }
}

test("an upload batch shows each file's status and announces start and end", async () => {
  let finishUpload
  const { app } = makeApp(
    () =>
      new Promise((resolve) => {
        finishUpload = () =>
          resolve({
            ok: true,
            json: async () => ({ upload: storedUpload('ticket.pdf') }),
          })
      })
  )

  const batch = app.uploadFiles([
    { name: 'ticket.pdf', size: 10 },
    { name: 'notes.exe', size: 10 },
  ])
  assert.equal(app.uploadStatusText, 'Uploading 1 file.')
  assert.deepEqual(
    Array.from(app.uploadRows, (r) => r.name + ': ' + r.state),
    ['ticket.pdf: uploading', 'notes.exe: failed']
  )

  finishUpload()
  await batch

  assert.equal(
    app.uploadStatusText,
    '1 file uploaded. notes.exe could not upload: unsupported file type.'
  )
  assert.deepEqual(
    Array.from(app.uploadRows, (r) => r.name + ': ' + r.state),
    ['ticket.pdf: done', 'notes.exe: failed']
  )
  assert.equal(app.uploads[0].name, 'ticket.pdf')
})

test("a server-side upload failure shows the server's reason on its row", async () => {
  const { app } = makeApp(async () => ({
    ok: false,
    json: async () => ({ error: 'File is empty' }),
  }))

  await app.uploadFiles([{ name: 'blank.pdf', size: 10 }])

  assert.equal(app.uploadRows[0].reason, 'File is empty')
  assert.equal(
    app.uploadStatusText,
    'blank.pdf could not upload: File is empty.'
  )
})

// The briefcase refresh runs with no DOM in Node, so the parser and the
// mounted panel are stand-ins that only honor the selector the app uses.
function mountBriefcase(app, context) {
  context.DOMParser = class {
    parseFromString(html) {
      return {
        querySelector(selector) {
          if (selector !== '[data-briefcase-facts]') return null
          if (!html.includes('data-briefcase-facts')) return null
          return { html, cloneNode: () => ({ html }) }
        },
      }
    }
  }
  const panel = { html: 'initial', replaced: [] }
  panel.replaceWith = (node) => panel.replaced.push(node.html)
  app.$root = {
    dataset: {
      agentBase: '/api/agents/assistant/',
      briefcaseUrl: '/chat/briefcase/',
      citationChips: 'false',
      reviewWarning: 'Warning',
    },
    querySelectorAll: (selector) =>
      selector === '[data-briefcase-facts]' ? [panel] : [],
  }
  app.consumeQueryMessage = () => {}
  app.init()
  return panel
}

test('briefcase_changed swaps in the fetched fragment, even for a detached stream', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const requested = []
  const { app, context } = makeApp(async (url) => {
    requested.push(url)
    return {
      ok: true,
      text: async () => '<div data-briefcase-facts>County: Cass</div>',
    }
  })
  const panel = mountBriefcase(app, context)
  const stream = newStream(app)
  app.messages = []

  app.handleEvent(stream, { type: 'briefcase_changed' })
  for (let index = 0; index < 10; index++) await Promise.resolve()

  assert.deepEqual(requested, ['/chat/briefcase/'])
  assert.deepEqual(panel.replaced, [
    '<div data-briefcase-facts>County: Cass</div>',
  ])
})

test('a fragment without the briefcase hook leaves the panel alone', async () => {
  const { app, context } = makeApp(async () => ({
    ok: true,
    text: async () => '<p>Not the panel</p>',
  }))
  const panel = mountBriefcase(app, context)

  await app.refreshBriefcase()

  assert.deepEqual(panel.replaced, [])
})

test('only the latest briefcase fetch swaps the panel', async () => {
  const pending = []
  const { app, context } = makeApp(
    () =>
      new Promise((resolve) => {
        pending.push((html) => resolve({ ok: true, text: async () => html }))
      })
  )
  const panel = mountBriefcase(app, context)

  // Two refreshes in flight; the earlier request resolves last.
  const first = app.refreshBriefcase()
  const second = app.refreshBriefcase()
  pending[1]('<div data-briefcase-facts>Burleigh</div>')
  await second
  pending[0]('<div data-briefcase-facts>Cass</div>')
  await first

  assert.deepEqual(panel.replaced, ['<div data-briefcase-facts>Burleigh</div>'])
})
