// Tests for the frameDrawer Alpine component in static/js/components.js.
//
// Run with: node --test litigant_portal/app/tests/js/components_frame_drawer.test.cjs
//
// Below xl each site frame region is a native popover drawer. The popover
// opens and closes itself; frameDrawer only adds focus handling. These tests
// cover the two ways that handling can leave the drawer in the wrong state:
// reopening it when its own header button is pressed, and leaving it open
// over the content after a link inside it was followed.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/components.js'),
  'utf8'
)

// A stand-in for the <aside popover> the component is mounted on. `inside`
// marks the fake elements that live within it.
function fakeDrawer(id) {
  return {
    id,
    open: true,
    focused: false,
    matches(selector) {
      return selector === ':popover-open' && this.open
    },
    hidePopover() {
      this.open = false
    },
    contains(element) {
      return element.inside === true
    },
    focus() {
      this.focused = true
    },
  }
}

function fakeElement({ inside = false, attributes = {}, link = null } = {}) {
  return {
    inside,
    focused: false,
    attributes: { ...attributes },
    getAttribute(name) {
      return name in this.attributes ? this.attributes[name] : null
    },
    hasAttribute(name) {
      return name in this.attributes
    },
    setAttribute(name, value) {
      this.attributes[name] = value
    },
    closest(selector) {
      return selector === 'a[href]' ? link : null
    },
    focus() {
      this.focused = true
    },
  }
}

function mountDrawer({ elementsById = {} } = {}) {
  const context = {
    window: {},
    console: { error() {} },
    document: {
      addEventListener(name, handler) {
        if (name === 'alpine:init') context.__init = handler
      },
      getElementById(id) {
        return elementsById[id] || null
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
  const drawer = registered.frameDrawer()
  drawer.$root = fakeDrawer('frame-left')
  return drawer
}

test('focus leaving for the rest of the page closes the drawer', () => {
  const drawer = mountDrawer()

  drawer.onFocusOut({ relatedTarget: fakeElement() })

  assert.equal(drawer.$root.open, false)
})

test('focus moving within the drawer keeps it open', () => {
  const drawer = mountDrawer()

  drawer.onFocusOut({ relatedTarget: fakeElement({ inside: true }) })

  assert.equal(drawer.$root.open, true)
})

test('pressing the header button for this drawer leaves the toggle to it', () => {
  // Chrome focuses the button on mousedown, before its click toggles the
  // popover. Closing here would let that click reopen the drawer.
  const drawer = mountDrawer()
  const ownButton = fakeElement({
    attributes: { popovertarget: 'frame-left' },
  })

  drawer.onFocusOut({ relatedTarget: ownButton })

  assert.equal(drawer.$root.open, true)
})

test("the other drawer's header button still closes this one", () => {
  const drawer = mountDrawer()
  const otherButton = fakeElement({
    attributes: { popovertarget: 'frame-right' },
  })

  drawer.onFocusOut({ relatedTarget: otherButton })

  assert.equal(drawer.$root.open, false)
})

test('following a link inside the drawer closes it', () => {
  const drawer = mountDrawer()
  const link = fakeElement({ inside: true, attributes: { href: '/' } })

  drawer.onClick({ target: fakeElement({ inside: true, link }) })

  assert.equal(drawer.$root.open, false)
})

test('an in-page link moves focus to the section it points at', () => {
  // Hiding a popover returns focus to the button that opened it, so without
  // this a keyboard user would land back in the header, not the section.
  const section = fakeElement()
  const drawer = mountDrawer({ elementsById: { deadlines: section } })
  const link = fakeElement({
    inside: true,
    attributes: { href: '#deadlines' },
  })

  drawer.onClick({ target: fakeElement({ inside: true, link }) })

  assert.equal(section.focused, true)
  assert.equal(section.getAttribute('tabindex'), '-1')
})

test('a click that is not on a link leaves the drawer open', () => {
  const drawer = mountDrawer()

  drawer.onClick({ target: fakeElement({ inside: true }) })

  assert.equal(drawer.$root.open, true)
})
