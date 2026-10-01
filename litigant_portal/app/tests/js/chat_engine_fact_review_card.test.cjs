// Tests for the factReviewCard Alpine component in static/js/chat_engine.js.
//
// Run with: node --test litigant_portal/app/tests/js/chat_engine_fact_review_card.test.cjs
//
// The one component test in the suite (see ./README.md). It exists for a bug
// no Python test can see: the card sits in the message flow ahead of the
// page's CSRF token, so a first-match token lookup finds the card's own empty
// input, the launch POST fails CSRF, and Django's fallback opens the plain,
// unprefilled interview with no error anywhere. The DOM fake below is the
// smallest thing that reproduces that ordering.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/chat_engine.js'),
  'utf8'
)

const PAGE_TOKEN = 'page-token-value'
const CONFIRM_URL = '/facts/confirm/'
const AS_OF = '2026-09-29T12:00:00.000000+00:00'

function mountCard({ allReviewed = false, names = 'first_name,county' } = {}) {
  const confirmButton = { disabled: false }
  const launchButton = { disabled: false }
  const confirmedNote = { hidden: true }
  const errorNote = { hidden: true }
  const staleNote = { hidden: true }
  const pendingBadges = [{ hidden: false }, { hidden: false }]
  const confirmedBadges = [{ hidden: true }, { hidden: true }]

  // Inputs the card puts into the message flow, in DOM order.
  const cardInputs = []
  const form = {
    querySelector(selector) {
      if (selector === 'input[name=csrfmiddlewaretoken]') {
        return cardInputs[0] || null
      }
      return null
    },
    appendChild(element) {
      cardInputs.push(element)
    },
  }
  const root = {
    dataset: {
      names,
      confirmUrl: CONFIRM_URL,
      asOf: AS_OF,
      allReviewed: allReviewed ? 'true' : 'false',
    },
    querySelector(selector) {
      switch (selector) {
        case '[data-role=confirm]':
          return confirmButton
        case '[data-role=confirmed-note]':
          return confirmedNote
        case '[data-role=error-note]':
          return errorNote
        case '[data-role=stale-note]':
          return staleNote
        case 'form button[type=submit]':
          return launchButton
        case 'form':
          return form
        default:
          return null
      }
    },
    querySelectorAll(selector) {
      if (selector === '[data-role=badge-pending]') return pendingBadges
      if (selector === '[data-role=badge-confirmed]') return confirmedBadges
      return []
    },
  }

  // The page's own {% csrf_token %} input comes AFTER the message flow.
  const pageToken = { name: 'csrfmiddlewaretoken', value: PAGE_TOKEN }
  const fetchCalls = []
  let fetchResponse = okResponse({ confirmed: 2, pending: [] })
  const context = {
    window: {},
    console: { error() {} },
    FormData,
    fetch(url, options) {
      fetchCalls.push({ url, options })
      return Promise.resolve(fetchResponse)
    },
    document: {
      addEventListener(name, handler) {
        if (name === 'alpine:init') context.__init = handler
      },
      createElement(tag) {
        assert.equal(tag, 'input')
        return { type: '', name: '', value: '' }
      },
      querySelectorAll(selector) {
        assert.equal(selector, '[name=csrfmiddlewaretoken]')
        return [...cardInputs, pageToken]
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
  const card = registered.factReviewCard()
  card.$root = root
  card.init()

  return {
    card,
    confirmButton,
    launchButton,
    confirmedNote,
    errorNote,
    staleNote,
    pendingBadges,
    confirmedBadges,
    cardInputs,
    fetchCalls,
    failNextFetch() {
      fetchResponse = { ok: false, status: 403 }
    },
    respondWith(body) {
      fetchResponse = okResponse(body)
    },
  }
}

function okResponse(body) {
  return { ok: true, json: () => Promise.resolve(body) }
}

test('arming the launch form fills it with the PAGE token, not its own empty input', () => {
  const { cardInputs } = mountCard()
  assert.equal(cardInputs.length, 1)
  assert.equal(cardInputs[0].name, 'csrfmiddlewaretoken')
  assert.equal(cardInputs[0].value, PAGE_TOKEN)
})

test('arming twice reuses the one input and keeps the page token', () => {
  const { card, cardInputs } = mountCard()
  card.armLaunch()
  assert.equal(cardInputs.length, 1)
  assert.equal(cardInputs[0].value, PAGE_TOKEN)
})

test('confirming posts a form body with the token, as_of and every name, no JSON header', async () => {
  const { card, fetchCalls } = mountCard()
  await card.confirmFacts()
  assert.equal(fetchCalls.length, 1)
  const { url, options } = fetchCalls[0]
  assert.equal(url, CONFIRM_URL)
  assert.equal(options.method, 'POST')
  assert.equal(options.headers, undefined)
  assert.ok(options.body instanceof FormData)
  assert.equal(options.body.get('csrfmiddlewaretoken'), PAGE_TOKEN)
  assert.equal(options.body.get('as_of'), AS_OF)
  assert.equal(options.body.getAll('names').join(','), 'first_name,county')
})

// Confirm is a shortcut, not a gate: unconfirmed facts never prefill, so an
// early launch only means the interview asks those questions itself.
test('launch is armed and enabled on init, before any confirm', () => {
  const { launchButton, cardInputs, fetchCalls } = mountCard()
  assert.equal(fetchCalls.length, 0)
  assert.equal(launchButton.disabled, false)
  assert.equal(cardInputs.length, 1)
  assert.equal(cardInputs[0].value, PAGE_TOKEN)
})

test('a successful confirm disables the button and shows the note', async () => {
  const { card, confirmButton, launchButton, confirmedNote, errorNote } =
    mountCard()
  await card.confirmFacts()
  assert.equal(confirmButton.disabled, true)
  assert.equal(confirmedNote.hidden, false)
  assert.equal(errorNote.hidden, true)
  assert.equal(launchButton.disabled, false)
  assert.equal(card.done, true)
})

test('a successful confirm flips every badge from pending to confirmed', async () => {
  const { card, pendingBadges, confirmedBadges } = mountCard()
  await card.confirmFacts()
  assert.ok(pendingBadges.every((b) => b.hidden))
  assert.ok(confirmedBadges.every((b) => !b.hidden))
})

test('a failed confirm leaves the badges pending', async () => {
  const { card, pendingBadges, confirmedBadges, failNextFetch } = mountCard()
  failNextFetch()
  await card.confirmFacts()
  assert.ok(pendingBadges.every((b) => !b.hidden))
  assert.ok(confirmedBadges.every((b) => b.hidden))
})

test('a failed confirm shows the error note and leaves launch enabled', async () => {
  const { card, launchButton, confirmedNote, errorNote, failNextFetch } =
    mountCard()
  failNextFetch()
  await card.confirmFacts()
  assert.equal(errorNote.hidden, false)
  assert.equal(confirmedNote.hidden, true)
  assert.equal(launchButton.disabled, false)
  assert.equal(card.done, false)
})

// The endpoint confirms only rows unchanged since as_of. A row re-saved after
// the card rendered comes back in `pending`, and the card must not show it as
// confirmed: the badges are the surface that earns the litigant's trust.
test('a confirm the server left partly pending shows the stale note and flips nothing', async () => {
  const {
    card,
    confirmButton,
    launchButton,
    confirmedNote,
    staleNote,
    pendingBadges,
    confirmedBadges,
    respondWith,
  } = mountCard()
  respondWith({ confirmed: 1, pending: ['county'] })
  await card.confirmFacts()
  assert.equal(staleNote.hidden, false)
  assert.equal(confirmedNote.hidden, true)
  assert.ok(pendingBadges.every((b) => !b.hidden))
  assert.ok(confirmedBadges.every((b) => b.hidden))
  assert.equal(launchButton.disabled, false)
  assert.equal(confirmButton.disabled, false)
  assert.equal(card.done, false)
})

// A reloaded card renders badges frozen at call time (#966), so its rows may
// already be confirmed: the count is 0 but nothing is pending.
test('a confirm with a zero count but nothing pending still marks the card confirmed', async () => {
  const { card, staleNote, confirmedNote, launchButton, respondWith } =
    mountCard()
  respondWith({ confirmed: 0, pending: [] })
  await card.confirmFacts()
  assert.equal(staleNote.hidden, true)
  assert.equal(confirmedNote.hidden, false)
  assert.equal(launchButton.disabled, false)
  assert.equal(card.done, true)
})

test('a later full confirm clears the stale note', async () => {
  const { card, staleNote, confirmedNote, respondWith } = mountCard()
  respondWith({ confirmed: 1, pending: ['county'] })
  await card.confirmFacts()
  respondWith({ confirmed: 1, pending: [] })
  await card.confirmFacts()
  assert.equal(staleNote.hidden, true)
  assert.equal(confirmedNote.hidden, false)
})

test('an already-reviewed card arms launch on init without posting', () => {
  const { launchButton, confirmedNote, cardInputs, fetchCalls } = mountCard({
    allReviewed: true,
  })
  assert.equal(fetchCalls.length, 0)
  assert.equal(launchButton.disabled, false)
  assert.equal(confirmedNote.hidden, false)
  assert.equal(cardInputs[0].value, PAGE_TOKEN)
})

test('a card with no names never posts', async () => {
  const { card, fetchCalls } = mountCard({ names: '' })
  await card.confirmFacts()
  assert.equal(fetchCalls.length, 0)
})
