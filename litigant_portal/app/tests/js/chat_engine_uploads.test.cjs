// Upload jobs in chatApp, built the way chat_stream.test.cjs builds the app.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/chat_engine.js'),
  'utf8'
)

const MB = 1024 * 1024

function makeApp(fetchImpl) {
  const components = {}
  const calls = []
  const context = {
    AbortController,
    FormData,
    TextDecoder,
    URLSearchParams,
    console: { ...console, error() {} },
    fetch: (url, options) => {
      calls.push({ url, options })
      return fetchImpl(url, options)
    },
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
  app.$nextTick = (callback) => callback()
  app.$refs = {}
  app.csrfToken = () => ''
  return { app, calls }
}

function response(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      if (body === undefined) throw new SyntaxError('not JSON')
      return body
    },
  }
}

const UPLOAD = {
  id: 'u1',
  name: 'contract.pdf',
  content_type: 'application/pdf',
  size: 1234,
  is_image: false,
  created_at: new Date().toISOString(),
}

test('a started upload is an uploading job until the request ends', async () => {
  let finish
  const { app } = makeApp(() => new Promise((resolve) => (finish = resolve)))

  const run = app.uploadFiles([{ name: 'contract.pdf', size: 10 }])
  await Promise.resolve()

  assert.equal(app.uploadJobs.length, 1)
  const job = app.uploadJobs[0]
  assert.equal(job.name, 'contract.pdf')
  assert.equal(job.status, 'uploading')
  assert.equal(job.isUploading, true)
  assert.equal(job.isDone, false)
  assert.equal(job.isFailed, false)
  assert.equal(app.hasUploadJobs, true)

  finish(response(200, { upload: UPLOAD }))
  await run
  assert.equal(job.status, 'done')
})

test('a finished upload is a done job and a selected card in the grid', async () => {
  const { app } = makeApp(async () => response(200, { upload: UPLOAD }))

  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])

  const job = app.uploadJobs[0]
  assert.equal(job.status, 'done')
  assert.equal(job.isDone, true)
  assert.equal(job.isUploading, false)
  assert.equal(job.error, '')
  assert.equal(app.uploads.length, 1)
  assert.equal(app.uploads[0].id, 'u1')
  assert.equal(app.uploads[0].selected, true)
})

test('a 400 with a JSON error keeps the server message', async () => {
  const { app } = makeApp(async () =>
    response(400, { error: 'File is too large (max 20 MB).' })
  )

  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])

  const job = app.uploadJobs[0]
  assert.equal(job.status, 'failed')
  assert.equal(job.isFailed, true)
  assert.equal(job.error, 'File is too large (max 20 MB).')
  assert.equal(app.uploads.length, 0)
})

test('a bare 413 on a file under our limit does not quote the limit', async () => {
  const { app } = makeApp(async () => response(413))

  await app.uploadFiles([{ name: 'scan.pdf', size: 12 * MB }])

  assert.equal(
    app.uploadJobs[0].error,
    'scan.pdf was refused as too large. Try a smaller file.'
  )
})

test('a 429 asks the user to wait a minute', async () => {
  const { app } = makeApp(async () => response(429))

  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])

  assert.equal(
    app.uploadJobs[0].error,
    'Too many uploads at once. Wait a minute and try again.'
  )
})

test('a 403 asks the user to reload the page', async () => {
  const { app } = makeApp(async () => response(403))

  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])

  assert.equal(
    app.uploadJobs[0].error,
    'Your session expired. Reload the page and try again.'
  )
})

test('a network error and a non-JSON 500 get the generic line', async () => {
  const generic = 'Upload failed. Check your connection and try again.'

  const offline = makeApp(async () => {
    throw new TypeError('offline')
  })
  await offline.app.uploadFiles([{ name: 'contract.pdf', size: 10 }])
  assert.equal(offline.app.uploadJobs[0].status, 'failed')
  assert.equal(offline.app.uploadJobs[0].error, generic)

  const broken = makeApp(async () => response(500))
  await broken.app.uploadFiles([{ name: 'contract.pdf', size: 10 }])
  assert.equal(broken.app.uploadJobs[0].error, generic)
})

test('a wrong extension fails before any request', async () => {
  const { app, calls } = makeApp(async () => response(200, { upload: UPLOAD }))

  await app.uploadFiles([{ name: 'report.exe', size: 10 }])

  assert.equal(calls.length, 0)
  const job = app.uploadJobs[0]
  assert.equal(job.status, 'failed')
  assert.equal(
    job.error,
    "This file type isn't supported (.exe). Use PDF, Word, Excel, images or text."
  )
})

test('an oversize file fails before any request and states its size', async () => {
  const { app, calls } = makeApp(async () => response(200, { upload: UPLOAD }))

  await app.uploadFiles([{ name: 'scan.pdf', size: 32 * MB }])

  assert.equal(calls.length, 0)
  assert.equal(app.uploadJobs[0].status, 'failed')
  assert.equal(
    app.uploadJobs[0].error,
    'scan.pdf is 32.0 MB. The limit is 20 MB.'
  )
})

test('rows are styled by status', async () => {
  const { app } = makeApp(async () => response(200, { upload: UPLOAD }))

  await app.uploadFiles([
    { name: 'contract.pdf', size: 10 },
    { name: 'report.exe', size: 10 },
  ])

  const [done, failed] = app.uploadJobs
  assert.match(done.rowClass, /green/)
  assert.match(failed.rowClass, /red/)
})

test('jobs stay until the dialog closes', async () => {
  const { app } = makeApp(async () => response(200, { upload: UPLOAD }))

  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])
  assert.equal(app.uploadJobs.length, 1)
  assert.equal(app.hasUploadJobs, true)

  app.closeAttach()

  assert.equal(app.uploadJobs.length, 0)
  assert.equal(app.hasUploadJobs, false)
})

test('deleting an upload removes its job row', async () => {
  const { app } = makeApp(async (url) =>
    url.endsWith('/delete/')
      ? response(200, {})
      : response(200, { upload: UPLOAD })
  )

  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])
  assert.equal(app.uploadJobs[0].uploadId, 'u1')

  await app.confirmUploadDelete(app.uploads[0])

  assert.equal(app.uploads.length, 0)
  assert.equal(app.uploadJobs.length, 0)
  assert.equal(app.hasUploadJobs, false)
})

test('a new pick keeps only the rows still uploading', async () => {
  // Only slow.pdf makes a request; the .exe is refused first.
  let release
  const { app, calls } = makeApp(() =>
    calls.length === 1
      ? new Promise((resolve) => {
          release = () => resolve(response(200, { upload: UPLOAD }))
        })
      : response(200, { upload: UPLOAD })
  )

  await app.uploadFiles([{ name: 'report.exe', size: 10 }])
  const slow = app.uploadFiles([{ name: 'slow.pdf', size: 10 }])
  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])

  assert.equal(
    app.uploadJobs.map((j) => j.name).join(','),
    'slow.pdf,contract.pdf'
  )

  release()
  await slow
  assert.equal(app.uploadJobs.find((j) => j.name === 'slow.pdf').isDone, true)
})

// An app with one uploaded, selected file and a stream endpoint that fails
// fast, so a send leaves no timers behind.
async function makeAttachApp() {
  const made = makeApp(async (url) =>
    url.endsWith('stream/') ? response(500) : response(200, { upload: UPLOAD })
  )
  const { app } = made
  app.threads = []
  app.setThreadStatus = () => {}
  app.updateThinking = () => {}
  await app.uploadFiles([{ name: 'contract.pdf', size: 10 }])
  return made
}

function streamCalls(calls) {
  return calls.filter((c) => c.url.endsWith('stream/'))
}

async function settle() {
  await new Promise((resolve) => setImmediate(resolve))
}

test('attaching with an empty composer sends the files right away', async () => {
  const { app, calls } = await makeAttachApp()
  app.threadId = 'thread-id'

  app.confirmAttach()
  await settle()

  const [sent] = streamCalls(calls)
  assert.ok(sent)
  assert.equal(sent.options.body.get('message'), '')
  assert.equal(sent.options.body.get('thread_id'), 'thread-id')
  assert.deepEqual(sent.options.body.getAll('attachment_ids'), ['u1'])
  assert.equal(app.attachments.length, 0)
  assert.equal(app.hasAttachments, false)
  assert.equal(app.attachOpen, false)

  const message = app.messages.find((m) => m.isUser)
  assert.equal(message.hasText, false)
  assert.equal(message.hasAtts, true)
  assert.equal(message.attachments[0].id, 'u1')
})

test('attaching with text in the composer keeps the chips', async () => {
  const { app, calls } = await makeAttachApp()
  app.input = 'I got this ticket'

  app.confirmAttach()
  await settle()

  assert.equal(streamCalls(calls).length, 0)
  assert.equal(app.attachments.length, 1)
  assert.equal(app.hasAttachments, true)
})

test('attaching while a reply streams keeps the chips', async () => {
  const { app, calls } = await makeAttachApp()
  app.streaming = true

  app.confirmAttach()
  await settle()

  assert.equal(streamCalls(calls).length, 0)
  assert.equal(app.attachments.length, 1)
})

test('chips kept by a stream send on their own once it ends', async () => {
  const { app, calls } = await makeAttachApp()
  app.threadId = 'thread-id'
  app.streaming = true
  app.confirmAttach()
  await settle()
  assert.equal(streamCalls(calls).length, 0)

  app.streaming = false
  app.refreshSendState()
  assert.equal(app.sendDisabled, false)
  app.send()
  await settle()

  const [sent] = streamCalls(calls)
  assert.ok(sent)
  assert.equal(sent.options.body.get('message'), '')
  assert.deepEqual(sent.options.body.getAll('attachment_ids'), ['u1'])
  assert.equal(app.attachments.length, 0)
})

test('chips kept by typed text send on their own once it is cleared', async () => {
  const { app, calls } = await makeAttachApp()
  app.threadId = 'thread-id'
  app.input = 'I got this ticket'
  app.confirmAttach()
  await settle()
  assert.equal(streamCalls(calls).length, 0)

  app.updateInput({ target: { value: '', style: {}, scrollHeight: 0 } })
  assert.equal(app.sendDisabled, false)
  app.send()
  await settle()

  const [sent] = streamCalls(calls)
  assert.ok(sent)
  assert.equal(sent.options.body.get('message'), '')
  assert.deepEqual(sent.options.body.getAll('attachment_ids'), ['u1'])
  assert.equal(app.attachments.length, 0)
})

test('an empty composer with no chips cannot send', async () => {
  const { app, calls } = await makeAttachApp()
  app.refreshSendState()
  assert.equal(app.sendDisabled, true)
  app.send()
  await settle()
  assert.equal(streamCalls(calls).length, 0)
})

test('removing the last chip disables the send button again', async () => {
  const { app } = await makeAttachApp()
  app.streaming = true
  app.confirmAttach()
  app.streaming = false
  app.refreshSendState()
  assert.equal(app.sendDisabled, false)

  app.removeAttachment({ currentTarget: { dataset: { uploadId: 'u1' } } })

  assert.equal(app.hasAttachments, false)
  assert.equal(app.sendDisabled, true)
})

test('an auto-send leaves focus free for the reply to return it', async () => {
  const { app } = await makeAttachApp()
  let focused = 0
  app.attachTrigger = { focus: () => focused++ }

  app.confirmAttach()
  await settle()

  assert.equal(focused, 0)
  assert.equal(app.attachTrigger, null)
})

test('chips kept by typed text return focus to the Attach button', async () => {
  const { app } = await makeAttachApp()
  app.input = 'I got this ticket'
  let focused = 0
  app.attachTrigger = { focus: () => focused++ }

  app.confirmAttach()
  await settle()

  assert.equal(focused, 1)
  assert.equal(app.attachTrigger, null)
})

test('attaching with nothing selected makes no request', async () => {
  const { app, calls } = await makeAttachApp()
  app.uploads[0].selected = false

  app.confirmAttach()
  await settle()

  assert.equal(streamCalls(calls).length, 0)
  assert.equal(app.attachments.length, 0)
})

test('hasText is false only for a user message with no text', async () => {
  const { app } = await makeAttachApp()

  app.input = 'hello'
  app.send()
  await settle()
  app.appendContent({ messages: app.messages, openIndex: null }, '')

  const typed = app.messages.find((m) => m.isUser)
  const assistant = app.messages[app.messages.length - 1]
  assert.equal(typed.content, 'hello')
  assert.equal(typed.hasText, true)
  assert.equal(assistant.isAssistant, true)
  assert.equal(assistant.content, '')
  assert.equal(assistant.hasText, true)
})

// A $nextTick that runs after the current tick, like Alpine's, and records
// what the live region holds each time.
function deferredTick(app, heard) {
  return (callback) =>
    Promise.resolve().then(() => {
      callback()
      heard.push(app.uploadAnnouncement)
    })
}

test('each status change is announced to the live region', async () => {
  const { app } = makeApp(async () => response(200, { upload: UPLOAD }))
  const heard = []
  app.$nextTick = deferredTick(app, heard)

  await app.uploadFiles([
    { name: 'contract.pdf', size: 10 },
    { name: 'report.exe', size: 10 },
  ])
  await Promise.resolve()

  assert.deepEqual(heard, [
    'Uploading contract.pdf. Uploading report.exe. ' +
      "report.exe failed: This file type isn't supported (.exe). Use PDF, Word, Excel, images or text.",
    'Uploaded contract.pdf',
  ])
})

test('same-tick status changes are joined, none is dropped', async () => {
  const { app } = makeApp(async () => response(200, {}))
  const heard = []
  app.$nextTick = deferredTick(app, heard)

  app.announce('Uploading a.pdf')
  app.announce('Uploading b.pdf')
  app.announce('b.pdf failed: too big')
  assert.equal(app.uploadAnnouncement, '')
  await Promise.resolve()

  assert.deepEqual(heard, [
    'Uploading a.pdf. Uploading b.pdf. b.pdf failed: too big',
  ])
  assert.equal(app.pendingAnnouncements.length, 0)

  app.announce('Uploaded a.pdf')
  await Promise.resolve()
  assert.equal(heard[1], 'Uploaded a.pdf')
})

test('the same text is announced again by clearing it first', () => {
  const { app } = makeApp(async () => response(200, {}))
  const seen = []
  app.$nextTick = (callback) => {
    seen.push(app.uploadAnnouncement)
    callback()
  }

  app.announce('Uploaded contract.pdf')
  app.announce('Uploaded contract.pdf')

  assert.deepEqual(seen, ['', ''])
  assert.equal(app.uploadAnnouncement, 'Uploaded contract.pdf')
})

test('closing the dialog clears the announcement', () => {
  const { app } = makeApp(async () => response(200, {}))

  app.$nextTick = () => {}

  app.announce('Uploaded contract.pdf')
  app.closeAttach()

  assert.equal(app.uploadAnnouncement, '')
  assert.equal(app.pendingAnnouncements.length, 0)
})
