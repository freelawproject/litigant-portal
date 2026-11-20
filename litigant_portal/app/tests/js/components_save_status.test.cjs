// Tests for the saveStatus Alpine component in static/js/components.js.
//
// Run with: node --test litigant_portal/app/tests/js/components_save_status.test.cjs
//
// A live region announces what changes after load, not what it loaded
// with, so the component starts the text empty and puts the
// server-rendered text back once the page has settled.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/components.js'),
  'utf8'
)

function mountStatus(text) {
  const timers = []
  const context = {
    window: {},
    console: { error() {} },
    setTimeout(fn, delay) {
      timers.push({ fn, delay })
    },
    document: {
      addEventListener(name, handler) {
        if (name === 'alpine:init') context.__init = handler
      },
    },
  }
  vm.createContext(context)
  vm.runInContext(source, context)

  const registered = {}
  context.Alpine = {
    data(name, factory) {
      registered[name] = factory
    },
  }
  context.__init()
  const status = registered.saveStatus()
  status.$el = { dataset: { text } }
  status.init()
  return { status, timers }
}

test('the text starts empty and is filled after a short delay', () => {
  const { status, timers } = mountStatus('Saved')

  assert.equal(status.text, '')
  assert.equal(timers.length, 1)
  assert.ok(timers[0].delay > 0)

  timers[0].fn()

  assert.equal(status.text, 'Saved')
})
