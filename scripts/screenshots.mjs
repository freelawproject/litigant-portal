// Capture the front-end pages at desktop and phone width with headless
// Chrome, so a front-end change can be compared before and after.
//
//   node scripts/screenshots.mjs before            # then make the change...
//   node scripts/screenshots.mjs after
//   node scripts/screenshots.mjs after http://portal.localhost
//
// Writes .screenshots/<label>/<page>-<width>.png (gitignored), each a
// full-page capture. Needs the dev server running (`make docker`) and Google
// Chrome or Chromium: found in /Applications on macOS and on PATH on Linux,
// or set CHROME=/path/to/chrome. Node built-ins only, no install.
//
// Widths are set with the DevTools protocol's device emulation, not
// --window-size: headless Chrome will not lay a window out narrower than
// about 750px, so a 320px window is really a crop of a wider page.
//
// On macOS under Claude Code, run it outside the sandbox: Chrome aborts at
// startup when the sandbox denies it a Mach port, the same failure as the
// draw.io CLI (see CLAUDE.md).
import { spawn } from 'node:child_process'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { delimiter, join } from 'node:path'
import { setTimeout as sleep } from 'node:timers/promises'

const [label, baseUrl = 'http://localhost'] = process.argv.slice(2)
if (!label) {
  console.error('usage: node scripts/screenshots.mjs <label> [base-url]')
  process.exit(1)
}

// Where Chrome or Chromium usually lives: app bundles on macOS, command
// names to look up on PATH elsewhere (Linux).
const CHROME_CANDIDATES =
  process.platform === 'darwin'
    ? [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
      ]
    : ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME
  const pathDirs = (process.env.PATH || '').split(delimiter)
  for (const candidate of CHROME_CANDIDATES) {
    if (candidate.startsWith('/')) {
      if (existsSync(candidate)) return candidate
    } else {
      const dir = pathDirs.find((d) => existsSync(join(d, candidate)))
      if (dir) return join(dir, candidate)
    }
  }
  return null
}

const CHROME = findChrome()
if (!CHROME) {
  console.error(
    `Chrome not found (looked for ${CHROME_CANDIDATES.join(', ')}). Set CHROME=/path/to/chrome.`
  )
  process.exit(1)
}

// [name, path]. Add a line to capture another page or simulation.
const PAGES = [
  ['home', '/'],
  ['chat', '/chat/'],
  ['style-guide', '/style-guide/'],
  ['atomic-design', '/style-guide/atomic-design/'],
  ['atomic-design-organisms', '/style-guide/atomic-design/?level=organisms'],
  ['atomic-design-page', '/style-guide/atomic-design/?level=page'],
]

// Desktop, and the narrowest phone WCAG reflow (1.4.10) asks us to support.
const VIEWPORTS = [
  { width: 1440, height: 900, mobile: false },
  { width: 320, height: 640, mobile: true },
]

try {
  await fetch(baseUrl)
} catch {
  console.error(`No dev server at ${baseUrl}. Start it with: make docker`)
  process.exit(1)
}

// Every wait on Chrome gets a deadline, so a page that never loads or a
// Chrome that dies fails with a message instead of hanging forever.
const TIMEOUT_MS = 15_000

function withTimeout(promise, what) {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`Timed out after ${TIMEOUT_MS / 1000}s ${what}`)),
      TIMEOUT_MS
    )
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}

const profile = mkdtempSync(join(tmpdir(), 'lp-screenshots-'))
const chrome = spawn(
  CHROME,
  [
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    'about:blank',
  ],
  { stdio: 'ignore' }
)
// Registered now so cleanup can't miss an early exit. A failed spawn emits
// 'error' and may never emit 'exit'.
let startError
const chromeExited = new Promise((resolve) => {
  chrome.once('exit', resolve)
  chrome.once('error', (error) => {
    startError = error
    resolve()
  })
})

let ws
try {
  // With port 0, Chrome picks a free port and writes it to the profile.
  let port
  for (let i = 0; i < 50 && !port && !startError; i++) {
    await sleep(200)
    try {
      port = readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split(
        '\n'
      )[0]
    } catch {}
  }
  if (!port) {
    throw new Error(
      `Chrome did not start (${CHROME}). Set CHROME=... if it lives elsewhere.`
    )
  }

  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
  ws = new WebSocket(
    targets.find((t) => t.type === 'page').webSocketDebuggerUrl
  )
  await withTimeout(
    new Promise((resolve, reject) => {
      ws.onopen = resolve
      ws.onerror = () => reject(new Error('Could not connect to Chrome'))
    }),
    'connecting to Chrome'
  )

  let nextId = 0
  const pending = new Map()
  const loaded = []
  ws.onmessage = ({ data }) => {
    const message = JSON.parse(data)
    if (message.id && pending.has(message.id)) {
      const { method, resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      if (message.error)
        reject(new Error(`${method}: ${message.error.message}`))
      else resolve(message.result)
    } else if (message.method === 'Page.loadEventFired') {
      loaded.shift()?.resolve()
    } else if (message.method === 'Inspector.targetCrashed') {
      failAll(`The page crashed while capturing ${current}`)
    }
  }
  // Chrome can fail two ways, and neither answers what we're waiting on: a
  // crashed renderer leaves the socket open but the page dead, and a dead
  // Chrome closes the socket. Either way, fail every outstanding wait now,
  // and remember why: a send after close is silently dropped, so a wait that
  // starts later would otherwise hang until its timeout.
  let current = 'the first page'
  let failure
  const failAll = (reason) => {
    failure ??= new Error(reason)
    for (const { reject } of pending.values()) reject(failure)
    pending.clear()
    for (const { reject } of loaded.splice(0)) reject(failure)
  }
  ws.onclose = () => failAll('Chrome closed the connection (did it crash?)')
  const send = (method, params = {}) =>
    withTimeout(
      new Promise((resolve, reject) => {
        if (failure) return reject(failure)
        const id = ++nextId
        pending.set(id, { method, resolve, reject })
        ws.send(JSON.stringify({ id, method, params }))
      }),
      `waiting for ${method}`
    )

  await send('Page.enable')
  await send('Inspector.enable') // reports a renderer crash
  const outDir = join('.screenshots', label)
  mkdirSync(outDir, { recursive: true })

  for (const viewport of VIEWPORTS) {
    await send('Emulation.setDeviceMetricsOverride', {
      ...viewport,
      deviceScaleFactor: 1,
    })
    for (const [name, path] of PAGES) {
      current = `${name} (${path}) at ${viewport.width}px`
      // Listen before navigating so the load event can't arrive first.
      const pageLoaded = new Promise((resolve, reject) =>
        failure ? reject(failure) : loaded.push({ resolve, reject })
      )
      pageLoaded.catch(() => {}) // a failed navigate settles it unawaited
      await send('Page.navigate', { url: baseUrl + path })
      await withTimeout(pageLoaded, `loading ${current}`)
      await sleep(500) // fonts and images settle after the load event
      const { cssContentSize } = await send('Page.getLayoutMetrics')
      const shot = await send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: true,
        clip: {
          x: 0,
          y: 0,
          width: viewport.width,
          height: Math.ceil(cssContentSize.height),
          scale: 1,
        },
      })
      const file = join(outDir, `${name}-${viewport.width}.png`)
      writeFileSync(file, Buffer.from(shot.data, 'base64'))
      console.log(file)
    }
  }
} catch (error) {
  console.error(error.message)
  process.exitCode = 1
} finally {
  ws?.close()
  // Chrome keeps writing its profile until it exits, so wait before removing
  // it. Only kill a Chrome that is still running: a dead one won't exit twice.
  if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill()
  await chromeExited
  rmSync(profile, { recursive: true, force: true, maxRetries: 3 })
}
