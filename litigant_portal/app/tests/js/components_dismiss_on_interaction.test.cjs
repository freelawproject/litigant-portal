// Tests for the dismissOnInteraction Alpine component in
// static/js/components.js.
//
// Run with: node --test litigant_portal/app/tests/js/components_dismiss_on_interaction.test.cjs
//
// The component shows its content until the first click or keypress
// anywhere, then fades (a class the template binds) and hides on the
// fade's animationend. A timer would take the content away before
// someone using screen magnification has panned to it.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/components.js'),
  'utf8'
)

function mount() {
  const listeners = []
  const context = {
    window: {
      addEventListener(name, handler) {
        listeners.push({ name, handler })
      },
      removeEventListener(name, handler) {
        const at = listeners.findIndex(
          (l) => l.name === name && l.handler === handler
        )
        if (at !== -1) listeners.splice(at, 1)
      },
    },
    console: { error() {} },
    setTimeout() {},
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
  const component = registered.dismissOnInteraction()
  component.init()
  return { component, listeners }
}

test('shows with no fade until the first interaction', () => {
  const { component, listeners } = mount()

  assert.equal(component.show, true)
  assert.equal(component.fadeClass, '')
  assert.deepEqual(listeners.map((l) => l.name).sort(), [
    'keydown',
    'pointerdown',
  ])
})

test('the first interaction starts the fade and stops listening', () => {
  const { component, listeners } = mount()

  listeners[0].handler()

  assert.equal(component.fadeClass, 'dismiss-fade-out')
  assert.equal(component.show, true)
  assert.equal(listeners.length, 0)
})

test('the fade ending hides the content', () => {
  const { component, listeners } = mount()

  listeners[0].handler()
  component.dismiss()

  assert.equal(component.show, false)
})

test('destroy removes the listeners when nothing was pressed', () => {
  const { component, listeners } = mount()

  component.destroy()

  assert.equal(listeners.length, 0)
})
