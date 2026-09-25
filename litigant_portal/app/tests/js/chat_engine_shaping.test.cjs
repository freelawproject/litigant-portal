// Tests for the pure shaping functions in static/js/chat_engine.js.
//
// Run with: node --test litigant_portal/app/tests/js/chat_engine_shaping.test.cjs
//
// WHY THESE FUNCTIONS EXIST
//
// Alpine's CSP build cannot evaluate expressions in a template. Every
// directive value has to be a plain property name or dot-path: no ternaries,
// no `!negation`, no concatenation, no method calls with arguments. So the
// work a normal template would do inline is done here instead, and the
// template only reads the result.
//
// That produces two invariants which are invisible in any single function but
// break the UI silently when violated. Both are tested below:
//
//   1. SHAPE. Every message-like object carries the full set of keys from
//      blankMessage(). A CSP template binding a key that is `undefined` on
//      some code path renders nothing and reports nothing — so a constructor
//      that forgets a key produces a blank spot on screen with no error.
//
//   2. BOOLEAN PAIRS. `isTool`/`notTool`, `copied`/`notCopied`,
//      `isImage`/`notImage` exist only because `x-show="!isTool"` is illegal
//      under CSP. They must always be exact inverses. If they drift, an
//      element shows and hides at the same time.
//
// A failure in either is not cosmetic. It is a rendering bug that produces no
// console error and no test failure anywhere else.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

// See ./README.md for why the code is loaded this way.
const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/chat_engine.js'),
  'utf8'
)
const context = { window: {}, document: { addEventListener() {} } }
vm.createContext(context)
vm.runInContext(source, context)

const {
  timeSince,
  threadRowClass,
  blankMessage,
  makeMessage,
  messageAttachment,
  prettyJson,
  computeToolFlags,
  makeToolFromCall,
  makeToolFromItem,
  buildItem,
  formatSize,
  fileStyle,
  uploadCardClass,
  uploadDeleteClass,
  decorateUpload,
} = context

// An ISO timestamp `seconds` in the past, for deterministic timeSince tests.
const ago = (seconds) => new Date(Date.now() - seconds * 1000).toISOString()

// The boolean pairs the CSP build depends on. Kept as data so a new pair is
// one line here rather than a new test.
const BOOLEAN_PAIRS = [
  ['isTool', 'notTool'],
  ['copied', 'notCopied'],
]

// ============================================================================
// 1. The CSP invariants
// ============================================================================

test('every message constructor produces the full blankMessage shape', () => {
  // A missing key is not a crash, it is a silently empty binding. This is the
  // test that catches "added a template binding, forgot one constructor".
  const keys = Object.keys(blankMessage())
  const built = {
    makeMessage: makeMessage('assistant', 'hi', []),
    makeToolFromCall: makeToolFromCall({ id: 't1', name: 'x', args: {} }),
    makeToolFromItem: makeToolFromItem({ id: 't2', name: 'x', args: {} }),
  }
  for (const [label, obj] of Object.entries(built)) {
    const missing = keys.filter((k) => !(k in obj))
    assert.deepEqual(missing, [], `${label} is missing keys: ${missing}`)
  }
})

test('paired booleans are always exact inverses', () => {
  const objects = [
    blankMessage(),
    makeMessage('user', 'hi', []),
    makeMessage('assistant', 'hi', []),
    makeToolFromCall({ id: 't', name: 'x', args: {} }),
    makeToolFromItem({ id: 't', name: 'x', args: {} }),
  ]
  for (const obj of objects) {
    for (const [yes, no] of BOOLEAN_PAIRS) {
      assert.equal(
        obj[yes],
        !obj[no],
        `${yes}/${no} drifted: ${obj[yes]}/${obj[no]}`
      )
    }
  }
})

test('an attachment chip has inverse image flags', () => {
  const image = messageAttachment({ id: 1, name: 'a.png', is_image: true })
  const doc = messageAttachment({ id: 2, name: 'a.pdf', is_image: false })
  assert.equal(image.isImage, !image.notImage)
  assert.equal(doc.isImage, !doc.notImage)
  assert.equal(image.isImage, true)
  assert.equal(doc.isImage, false)
})

test('is_image is coerced to a real boolean, not passed through', () => {
  // The API sends JSON, and a truthy non-boolean would make isImage and
  // notImage both truthy at once.
  const chip = messageAttachment({ id: 1, name: 'a.png', is_image: 1 })
  assert.equal(chip.isImage, true)
  assert.equal(chip.notImage, false)
})

// ============================================================================
// 2. Messages
// ============================================================================

test('a user message is not run through the markdown renderer', () => {
  // Deliberate: user text is shown as typed. Rendering it would also mean
  // rendering markup the user pasted.
  const msg = makeMessage('user', '**not bold**', [])
  assert.equal(msg.html, '')
  assert.equal(msg.content, '**not bold**')
})

test('an assistant message is rendered to html', () => {
  const msg = makeMessage('assistant', '**bold**', [])
  assert.ok(msg.html.includes('<strong'))
})

test('user and assistant get different row and bubble classes', () => {
  const user = makeMessage('user', 'hi', [])
  const bot = makeMessage('assistant', 'hi', [])
  assert.equal(user.rowClass, 'items-end')
  assert.equal(bot.rowClass, 'items-start')
  assert.notEqual(user.bubbleClass, bot.bubbleClass)
})

test('a role other than user is treated as assistant', () => {
  // The check is `role === 'user'`, so anything else renders as assistant.
  // Worth pinning: a future role would silently inherit assistant styling.
  const msg = makeMessage('system', 'hi', [])
  assert.equal(msg.isAssistant, true)
  assert.equal(msg.isUser, false)
})

test('missing attachments become an empty list, not undefined', () => {
  const msg = makeMessage('user', 'hi')
  // Array.isArray rather than deepStrictEqual: this array was built inside the
  // vm context, so it has that realm's Array prototype and strict deep
  // equality rejects it against an outer-realm []. See README.
  assert.ok(Array.isArray(msg.attachments))
  assert.equal(msg.attachments.length, 0)
  assert.equal(msg.hasAtts, false)
})

test('hasAtts reflects whether there are attachments', () => {
  const msg = makeMessage('user', 'hi', [{ id: 1 }])
  assert.equal(msg.hasAtts, true)
})

test('message ids are unique and increasing', () => {
  // Alpine keys list items on these. Duplicates would make it reuse DOM nodes
  // across different messages.
  const a = makeMessage('user', 'one', [])
  const b = makeMessage('user', 'two', [])
  assert.ok(b.id > a.id)
})

// ============================================================================
// 3. Tool parts
// ============================================================================

test('a calling tool shows the spinner only in custom render mode', () => {
  const custom = computeToolFlags({ status: 'calling', callMode: 'custom' })
  const dflt = computeToolFlags({ status: 'calling', callMode: 'default' })
  assert.equal(custom.showCallCustom, true)
  assert.equal(custom.showCallDefault, false)
  assert.equal(dflt.showCallCustom, false)
  assert.equal(dflt.showCallDefault, true)
})

test('the default call box persists after the call completes', () => {
  // The custom card is in-flight only; the default JSON box stays.
  const done = computeToolFlags({ status: 'done', callMode: 'default' })
  assert.equal(done.showCallDefault, true)
  assert.equal(done.pending, false)
})

test('result rendering waits for the call to finish', () => {
  const calling = computeToolFlags({ status: 'calling', resultMode: 'custom' })
  const done = computeToolFlags({ status: 'done', resultMode: 'custom' })
  assert.equal(calling.showResultCustom, false)
  assert.equal(done.showResultCustom, true)
})

test('a tool part is neither a user nor an assistant message', () => {
  const tool = makeToolFromCall({ id: 't', name: 'x', args: {} })
  assert.equal(tool.isTool, true)
  assert.equal(tool.isUser, false)
  assert.equal(tool.isAssistant, false)
})

test('a live tool call starts pending with no result yet', () => {
  const tool = makeToolFromCall({
    id: 't1',
    name: 'load_topic_flow',
    args: { path: 'a/b' },
    render_mode: 'custom',
  })
  assert.equal(tool.status, 'calling')
  assert.equal(tool.pending, true)
  assert.equal(tool.resultMode, 'pending')
  assert.equal(tool.resultHtml, '')
  assert.ok(tool.argsJson.includes('"path"'))
})

test('a reloaded tool part arrives already complete', () => {
  const tool = makeToolFromItem({
    id: 't2',
    name: 'load_topic_flow',
    args: {},
    call_render_mode: 'custom',
    result_render_mode: 'custom',
    result_render_html: '<div>x</div>',
  })
  assert.equal(tool.status, 'done')
  assert.equal(tool.pending, false)
  assert.equal(tool.showResultCustom, true)
})

test('buildItem routes on kind', () => {
  const tool = buildItem({ kind: 'tool', id: 't', name: 'x', args: {} })
  const msg = buildItem({ kind: 'user', content: 'hi' })
  assert.equal(tool.isTool, true)
  assert.equal(msg.isUser, true)
})

test('buildItem maps attachments into chips', () => {
  const msg = buildItem({
    kind: 'user',
    content: 'hi',
    attachments: [
      { id: 1, name: 'a.pdf', size: 2048, content_type: 'application/pdf' },
    ],
  })
  assert.equal(msg.attachments.length, 1)
  assert.equal(msg.attachments[0].sizeLabel, '2 KB')
})

// ============================================================================
// 4. JSON boxes
// ============================================================================

test('prettyJson renders nothing for absent values', () => {
  // The template always binds it, so it must be a string rather than
  // "undefined" appearing on screen.
  assert.equal(prettyJson(null), '')
  assert.equal(prettyJson(undefined), '')
})

test('prettyJson indents so the box is readable', () => {
  assert.equal(prettyJson({ a: 1 }), '{\n  "a": 1\n}')
})

test('prettyJson survives a circular structure', () => {
  // Tool args come from the model. A structure JSON.stringify cannot handle
  // must not take the whole message list down.
  const circular = {}
  circular.self = circular
  assert.doesNotThrow(() => prettyJson(circular))
  assert.equal(typeof prettyJson(circular), 'string')
})

// ============================================================================
// 5. Formatting helpers
// ============================================================================

test('formatSize switches unit at each threshold', () => {
  assert.equal(formatSize(0), '0 B')
  assert.equal(formatSize(1023), '1023 B')
  assert.equal(formatSize(1024), '1 KB')
  assert.equal(formatSize(1048575), '1024 KB')
  assert.equal(formatSize(1048576), '1.0 MB')
  assert.equal(formatSize(20 * 1048576), '20.0 MB')
})

test('formatSize renders nothing for a non-number', () => {
  assert.equal(formatSize(undefined), '')
  assert.equal(formatSize(null), '')
  assert.equal(formatSize('2048'), '')
  assert.equal(formatSize(NaN), '')
})

test('fileStyle matches in list order, not by specificity', () => {
  // text/csv and text/markdown both contain "text". They are listed before
  // the /text/ catch-all, and reordering the list would silently relabel
  // every CSV as TXT.
  assert.equal(fileStyle('text/csv').badge, 'CSV')
  assert.equal(fileStyle('text/markdown').badge, 'MD')
  assert.equal(fileStyle('text/plain').badge, 'TXT')
})

test('fileStyle covers the upload types the backend accepts', () => {
  assert.equal(fileStyle('application/pdf').badge, 'PDF')
  assert.equal(fileStyle('application/msword').badge, 'DOC')
  assert.equal(
    fileStyle(
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ).badge,
    'DOC'
  )
  assert.equal(fileStyle('application/vnd.ms-excel').badge, 'XLS')
  assert.equal(fileStyle('application/rtf').badge, 'RTF')
})

test('an unrecognised type falls back rather than rendering blank', () => {
  const style = fileStyle('application/x-unknown')
  assert.equal(style.badge, 'FILE')
  assert.ok(style.tileClass.length > 0)
})

test('fileStyle tolerates an empty content type', () => {
  assert.equal(fileStyle('').badge, 'FILE')
})

test('timeSince renders nothing for an unparseable date', () => {
  assert.equal(timeSince('not a date'), '')
  assert.equal(timeSince(undefined), '')
})

test('timeSince singularises exactly one unit', () => {
  assert.equal(timeSince(ago(60)), '1 minute ago')
  assert.equal(timeSince(ago(120)), '2 minutes ago')
  assert.equal(timeSince(ago(3600)), '1 hour ago')
  assert.equal(timeSince(ago(86400)), '1 day ago')
})

test('timeSince says just now under a minute', () => {
  assert.equal(timeSince(ago(0)), 'just now')
  assert.equal(timeSince(ago(59)), 'just now')
})

test('a future timestamp reads as just now rather than negative', () => {
  // Clock skew between server and browser is normal. "-3 minutes ago" is not.
  assert.equal(timeSince(ago(-3600)), 'just now')
})

// ============================================================================
// 6. Upload cards
// ============================================================================

test('selection and the delete control change class, not structure', () => {
  assert.notEqual(uploadCardClass(true), uploadCardClass(false))
  assert.notEqual(uploadDeleteClass(true), uploadDeleteClass(false))
})

test('the armed delete control turns red and spans the card', () => {
  const armed = uploadDeleteClass(true)
  const idle = uploadDeleteClass(false)
  assert.ok(armed.includes('bg-red-600'))
  assert.ok(armed.includes('inset-x-1.5'))
  assert.ok(!idle.includes('bg-red-600'))
})

test('decorateUpload composes the badge, size and age into one card', () => {
  const card = decorateUpload(
    {
      id: 7,
      name: 'petition.pdf',
      content_type: 'application/pdf',
      size: 1048576,
      is_image: false,
      created_at: ago(7200),
    },
    false
  )
  assert.equal(card.id, 7)
  assert.equal(card.badge, 'PDF')
  assert.equal(card.sizeLabel, '1.0 MB')
  assert.equal(card.metaLabel, '1.0 MB · 2 hours ago')
  assert.equal(card.isImage, false)
  assert.equal(card.notImage, true)
})

test('a decorated upload starts with its delete control unarmed', () => {
  // Arming survives a re-render otherwise, and the next click deletes.
  const card = decorateUpload(
    { id: 1, content_type: 'application/pdf', size: 1 },
    true
  )
  assert.equal(card.deleteArmed, false)
  assert.equal(card.deleteIdle, true)
  assert.equal(card.deleteClass, uploadDeleteClass(false))
})

test('threadRowClass marks only the active row', () => {
  const active = threadRowClass('a', 'a')
  const other = threadRowClass('b', 'a')
  assert.ok(active.includes('border-primary-500'))
  assert.ok(other.includes('border-transparent'))
})

test('the inactive thread row reserves its border so rows do not shift', () => {
  // A transparent border rather than none: swapping to a coloured border on
  // selection would otherwise move every row by a pixel.
  assert.ok(threadRowClass('b', 'a').includes('border-transparent'))
})
