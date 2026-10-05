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

// With port 0, Chrome picks a free port and writes it to the profile.
let port
for (let i = 0; i < 50 && !port; i++) {
  await sleep(200)
  try {
    port = readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split(
      '\n'
    )[0]
  } catch {}
}
if (!port) {
  chrome.kill()
  console.error(
    `Chrome did not start (${CHROME}). Set CHROME=... if it lives elsewhere.`
  )
  process.exit(1)
}

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
const ws = new WebSocket(
  targets.find((t) => t.type === 'page').webSocketDebuggerUrl
)
await new Promise((resolve) => (ws.onopen = resolve))

let nextId = 0
const pending = new Map()
const loaded = []
ws.onmessage = ({ data }) => {
  const message = JSON.parse(data)
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message.result)
    pending.delete(message.id)
  } else if (message.method === 'Page.loadEventFired') {
    loaded.shift()?.()
  }
}
const send = (method, params = {}) =>
  new Promise((resolve) => {
    const id = ++nextId
    pending.set(id, resolve)
    ws.send(JSON.stringify({ id, method, params }))
  })

await send('Page.enable')
const outDir = join('.screenshots', label)
mkdirSync(outDir, { recursive: true })

try {
  for (const viewport of VIEWPORTS) {
    await send('Emulation.setDeviceMetricsOverride', {
      ...viewport,
      deviceScaleFactor: 1,
    })
    for (const [name, path] of PAGES) {
      const pageLoaded = new Promise((resolve) => loaded.push(resolve))
      await send('Page.navigate', { url: baseUrl + path })
      await pageLoaded
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
} finally {
  ws.close()
  // Chrome keeps writing its profile until it exits, so wait before removing it.
  const exited = new Promise((resolve) => chrome.once('exit', resolve))
  chrome.kill()
  await exited
  rmSync(profile, { recursive: true, force: true, maxRetries: 3 })
}
