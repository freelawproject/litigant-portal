// Run with: node --test litigant_portal/app/tests/js/agent_development.test.cjs
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const script = fs.readFileSync(
  path.join(__dirname, '../../static/js/agent_development.js'),
  'utf8'
)
const runId = '56bfd9d2-e900-4092-848e-04ca863dd74c'
const conversationId = '1385df04-f2d2-47b5-b869-4b2dbdcf2e38'
const reference = { run_id: runId, conversation_id: conversationId }
const model = 'bedrock_mantle/openai.gpt-5.6-luna'
const failed = {
  type: 'outcome',
  outcome: {
    ...reference,
    state: 'failed',
    error: {
      code: 'model_failed',
      message: 'The model response failed. Please try again.',
    },
  },
}
const reportedEvents = [
  {
    type: 'status',
    status: { ...reference, state: 'running', pending_question: null },
  },
  {
    type: 'tool',
    call_id: `scope:${runId}`,
    name: 'scope_selection',
    state: 'completed',
    data: { court: 'north-dakota', topic: 'adult-name-change' },
  },
  {
    type: 'tool',
    call_id: 'model:1',
    name: 'model_response',
    state: 'started',
    data: { candidate_attempt: 1, model },
  },
  {
    type: 'status',
    status: { ...reference, state: 'failed', pending_question: null },
  },
  failed,
]
const encode = (payloads) =>
  payloads
    .map((payload) => JSON.stringify({ ...reference, attempt: 1, payload }))
    .join('\n')

function harness(text, { close = false, continued = false } = {}) {
  let factory
  let cancelled = false
  const submissions = []
  const stream = new ReadableStream({
    start(controller) {
      const bytes = new TextEncoder().encode(text)
      // Exercise lines split across network chunks.
      controller.enqueue(bytes.slice(0, 17))
      controller.enqueue(bytes.slice(17))
      if (close) controller.close()
    },
    cancel() {
      cancelled = true
    },
  })
  const fields = Object.fromEntries(
    Object.entries({
      csrfmiddlewaretoken: 'test-csrf-token',
      message: 'Hello.',
      court: 'north-dakota',
      topic: 'adult-name-change',
      model,
      judge: '',
      max_active_seconds: '300',
    }).map(([name, value]) => [
      name,
      {
        value,
        disabled: continued && ['court', 'topic', 'model'].includes(name),
        style: {},
        scrollHeight: 60,
        focus() {},
      },
    ])
  )
  class BrowserFormData extends FormData {
    constructor(form) {
      super()
      for (const [name, field] of Object.entries(form.elements))
        if (!field.disabled) this.set(name, field.value)
    }
  }
  vm.runInNewContext(script, {
    document: { addEventListener: (name, callback) => callback() },
    Alpine: {
      data: (name, callback) => {
        if (name === 'agentDevelopment') factory = callback
      },
    },
    gettext: (text) => text,
    FormData: BrowserFormData,
    TextDecoder,
    clearTimeout,
    fetch: async (url, options) => {
      submissions.push(Object.fromEntries(options.body))
      return new Response(stream, {
        headers: { 'Content-Type': 'application/x-ndjson' },
      })
    },
  })
  const page = factory()
  Object.assign(page, {
    initialized: true,
    draft: fields.message.value,
    conversationId: continued ? conversationId : '',
    $root: {
      elements: fields,
      action: '/dev/agent/stream/',
      checkValidity: () => true,
    },
    $nextTick: async () => {},
    queueScroll() {},
    updateConfigurationSummary() {},
    setConversation(id) {
      this.conversationId = id
    },
  })
  return { page, stream, submissions, wasCancelled: () => cancelled }
}

test(
  'reported failure ends the waiting state while HTTP stays open',
  { timeout: 2000 },
  async () => {
    const { page, stream, submissions, wasCancelled } = harness(
      encode(reportedEvents) + '\n'
    )
    await page.send()
    assert.equal(page.running, false)
    assert.equal(page.messages.at(-1).pending, false)
    assert.equal(page.messages.at(-1).waiting, false)
    assert.equal(page.messages.at(-1).text, failed.outcome.error.message)
    assert.equal(page.status, 'failed')
    assert.equal(page.errorCode, 'model_failed')
    assert.equal(page.runId, runId)
    assert.ok(page.failureDetails.includes(runId))
    assert.ok(page.failureDetails.includes('model_failed'))
    assert.equal(page.events.length, 5)
    assert.equal(submissions.length, 1)
    assert.equal(wasCancelled(), true)
    assert.equal(stream.locked, false)
    page.draft = 'Try again'
    assert.equal(page.sendDisabled, false)
    page.newConversation()
    assert.equal(page.error, '')
    assert.equal(page.errorCode, '')
    assert.equal(page.runId, '')
  }
)

for (const continued of [false, true]) {
  test(`preserves ${continued ? 'continued' : 'fresh'} request options`, async () => {
    const { page, submissions } = harness(encode([failed]) + '\n', {
      continued,
    })
    await page.send()
    assert.deepEqual(submissions, [
      {
        csrfmiddlewaretoken: 'test-csrf-token',
        message: 'Hello.',
        court: 'north-dakota',
        topic: 'adult-name-change',
        model,
        judge: '',
        max_active_seconds: '300',
        ...(continued ? { conversation_id: conversationId } : {}),
      },
    ])
  })
}

for (const state of ['completed', 'cancelled']) {
  test(
    `${state} outcome ends reading before HTTP closes`,
    { timeout: 2000 },
    async () => {
      const payload = {
        type: 'outcome',
        outcome: { ...reference, state, text: 'Hello!', sources: [] },
      }
      const { page, stream } = harness(
        encode([payload]) + '\nignored trailing data\n'
      )
      await page.send()
      assert.equal(page.status, state)
      assert.equal(page.running, false)
      assert.equal(page.messages.at(-1).pending, false)
      assert.equal(page.error, '')
      assert.equal(stream.locked, false)
      if (state === 'completed')
        assert.equal(page.messages.at(-1).text, 'Hello!')
    }
  )
}

test('accepts the final outcome without a newline at EOF', async () => {
  const { page } = harness(encode(reportedEvents), { close: true })
  await page.send()
  assert.equal(page.errorCode, 'model_failed')
  assert.equal(page.events.length, 5)
  assert.equal(page.running, false)
})

test('an early disconnect clears waiting and explains the incomplete response', async () => {
  const { page } = harness(encode(reportedEvents.slice(0, 3)), { close: true })
  await page.send()
  assert.equal(page.status, 'Failed')
  assert.equal(page.error, 'The connection ended before the response finished.')
  assert.equal(page.running, false)
  assert.equal(page.messages.at(-1).pending, false)
  assert.equal(page.errorCode, '')
  assert.equal(page.runId, runId)
})
