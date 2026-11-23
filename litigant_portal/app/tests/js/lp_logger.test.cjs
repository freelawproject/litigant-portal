const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

test('console output is immediate and retains original options when delivery fails', async () => {
  const calls = []
  const context = {
    Error,
    URLSearchParams,
    window: {},
    document: {
      currentScript: { dataset: { url: '/api/logs/', csrfToken: 'token' } },
    },
    fetch: (_url, options) => {
      calls.push(['fetch', options])
      return Promise.reject(new Error('offline'))
    },
    console: { log: (options) => calls.push(['console', options]) },
  }
  vm.runInNewContext(
    fs.readFileSync(
      path.join(__dirname, '../../static/js/lp_logger.js'),
      'utf8'
    ),
    context
  )
  const options = { type: new Error('original detail'), msg: 'Chat failed' }
  context.window.lpLogger(options)
  assert.deepEqual(
    calls.map(([kind]) => kind),
    ['fetch', 'console']
  )
  assert.equal(calls[1][1], options)
  assert.deepEqual(JSON.parse(calls[0][1].body.get('options')), {
    type: 'error',
    msg: 'Chat failed',
  })
  assert.equal(calls[0][1].body.get('csrfmiddlewaretoken'), 'token')
  await new Promise(setImmediate)
  options.context = options
  context.window.lpLogger(options)
  assert.equal(calls.at(-1)[1], options)
  assert.equal(calls.length, 3)
})
