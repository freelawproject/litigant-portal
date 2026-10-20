// Tests for the siteMenu Alpine component in static/js/components.js.
//
// Run with: node --test litigant_portal/app/tests/js/components_site_menu.test.cjs
//
// The header's site menu is a native <details> (#988), so it opens and
// closes without JS. On its own it only closes from its own summary, so
// siteMenu adds the two closes people expect from a menu: a click
// anywhere outside it, and Escape. Escape also returns focus to the
// summary, since the focused link stops rendering once the menu shuts.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/components.js'),
  'utf8'
)

function mountMenu({ open = true } = {}) {
  const context = {
    window: {},
    console: { error() {} },
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
  const menu = registered.siteMenu()
  const summary = {
    focused: false,
    focus() {
      this.focused = true
    },
  }
  menu.$root = {
    open,
    querySelector: (selector) => (selector === 'summary' ? summary : null),
  }
  return { menu, summary }
}

test('closing shuts an open menu', () => {
  const { menu } = mountMenu()

  menu.close()

  assert.equal(menu.$root.open, false)
})

test('closing a menu that is already shut leaves it shut', () => {
  const { menu } = mountMenu({ open: false })

  menu.close()

  assert.equal(menu.$root.open, false)
})

test('Escape shuts the menu and returns focus to its summary', () => {
  const { menu, summary } = mountMenu()

  menu.dismiss()

  assert.equal(menu.$root.open, false)
  assert.equal(summary.focused, true)
})

test('an outside click shuts the menu without moving focus', () => {
  const { menu, summary } = mountMenu()

  menu.close()

  assert.equal(summary.focused, false)
})
