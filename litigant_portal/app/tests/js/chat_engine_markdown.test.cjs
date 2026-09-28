// Tests for the chat markdown renderer in static/js/chat_engine.js.
//
// Run with: node --test litigant_portal/app/tests/js/chat_engine_markdown.test.cjs
//
// WHY THIS FILE EXISTS
//
// The chat renders assistant messages with `x-html`, which writes markup into
// the page without sanitising it. CLAUDE.md justifies that on one ground:
//
//   "Safe because renderMarkdown() runs everything through escapeHtml()
//    before applying markdown transforms"
//
// That sentence is the whole argument for why model output cannot inject HTML
// into a litigant's browser. Until this file existed, nothing checked it. The
// tests below are ordered so the security guarantee comes first and the
// formatting behaviour second, because that is the order they matter in.
//
// A failure in "the escaping guarantee" is not a formatting regression. It
// means model output can put live markup on the page, and it should be
// treated as a security bug rather than a broken test.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

// --- Loading the code under test --------------------------------------------
//
// chat_engine.js is a browser script, not a module: it exports nothing and
// touches `window` and `document` at the top level. Evaluate it in a vm with a
// minimal fake browser, and its top-level function declarations land on the
// context object.
//
// `document.addEventListener` is a no-op on purpose. The Alpine components are
// registered inside an `alpine:init` listener, so never firing it means they
// are never constructed and these tests stay about the pure functions.

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/chat_engine.js'),
  'utf8'
)
const context = { window: {}, document: { addEventListener() {} } }
vm.createContext(context)
vm.runInContext(source, context)

const { escapeHtml, renderInline, renderMarkdown } = context

// The class attributes the renderer emits. Kept here so a styling change
// touches one place, and so the assertions below read as behaviour rather than
// as a wall of Tailwind.
const P = 'class="my-1.5 first:mt-0 last:mb-0 leading-relaxed"'
const LINK =
  'target="_blank" rel="noopener noreferrer" ' +
  'class="text-primary-700 underline hover:no-underline"'

// ============================================================================
// 1. escapeHtml — the primitive everything else depends on
// ============================================================================

test('escapeHtml escapes the four characters that can break out of markup', () => {
  assert.equal(escapeHtml('&'), '&amp;')
  assert.equal(escapeHtml('<'), '&lt;')
  assert.equal(escapeHtml('>'), '&gt;')
  assert.equal(escapeHtml('"'), '&quot;')
})

test('escapeHtml escapes the ampersand first, so escapes are not double-escaped', () => {
  // If `<` were replaced before `&`, the resulting `&lt;` would then have its
  // own ampersand escaped and the output would be `&amp;lt;`.
  assert.equal(escapeHtml('<b>'), '&lt;b&gt;')
  assert.equal(escapeHtml('&lt;'), '&amp;lt;')
})

test('escapeHtml leaves the single quote alone', () => {
  // Documented rather than asserted as correct. It is safe only because every
  // attribute this renderer emits is double-quoted. A future change that emits
  // a single-quoted attribute would make this a hole.
  assert.equal(escapeHtml("it's"), "it's")
})

test('escapeHtml coerces non-strings rather than throwing', () => {
  assert.equal(escapeHtml(42), '42')
  assert.equal(escapeHtml(null), 'null')
  assert.equal(escapeHtml(undefined), 'undefined')
})

// ============================================================================
// 2. The escaping guarantee — adversarial input
//
// Each of these is a payload that would execute if it reached the page as
// markup. They are the reason `x-html` is considered safe here.
// ============================================================================

test('a script tag in prose is inert', () => {
  const out = renderMarkdown('<script>alert(1)</script>')
  // Match on the opening bracket alone, not "<script>". If `<` stopped being
  // escaped while `>` still was, the output would read "<script&gt;" — which
  // does not contain "<script>" but is very much a live tag. Mutation testing
  // caught exactly that, so this assertion is deliberately the looser pattern.
  assert.ok(!/<script/i.test(out), 'an unescaped script tag reached the output')
  assert.ok(out.includes('&lt;script&gt;alert(1)&lt;/script&gt;'))
})

test('an event handler attribute is inert', () => {
  const out = renderMarkdown('<img src=x onerror=alert(1)>')
  assert.ok(!out.includes('<img'), 'raw img tag reached the output')
  assert.ok(out.includes('&lt;img src=x onerror=alert(1)&gt;'))
})

test('escaping happens before transforms, so markup cannot be smuggled through emphasis', () => {
  // The bold transform runs on already-escaped text. If it ran first, the
  // angle brackets would survive into the output as live markup.
  const out = renderInline('**<b>hi</b>**')
  assert.equal(
    out,
    '<strong class="font-semibold">&lt;b&gt;hi&lt;/b&gt;</strong>'
  )
})

test('a closing tag cannot escape a code span', () => {
  const out = renderInline('`</code><script>alert(1)</script>`')
  assert.ok(!out.includes('<script>'))
  assert.equal(
    out,
    '<code>&lt;/code&gt;&lt;script&gt;alert(1)&lt;/script&gt;</code>'
  )
})

test('markup inside a fenced code block is escaped', () => {
  const out = renderMarkdown('```\n<script>alert(1)</script>\n```')
  assert.ok(!out.includes('<script>'))
  assert.ok(out.includes('&lt;script&gt;alert(1)&lt;/script&gt;'))
})

test('a quote in a link target cannot break out of the href attribute', () => {
  // The double quote is escaped before the link regex runs, so it lands inside
  // the attribute as an entity rather than closing it.
  const out = renderInline('[x](https://e.com/a"onmouseover="alert(1))')
  assert.ok(!out.includes('onmouseover="alert'))
  assert.ok(out.includes('&quot;'))
})

// ============================================================================
// 3. Links — the scheme allowlist
//
// Anything outside http, https and mailto becomes "#". The check is a regex
// against the already-escaped URL, and it is case-insensitive.
// ============================================================================

test('http, https and mailto links keep their target', () => {
  assert.ok(renderInline('[a](https://e.com)').includes('href="https://e.com"'))
  assert.ok(renderInline('[a](http://e.com)').includes('href="http://e.com"'))
  assert.ok(
    renderInline('[a](mailto:a@e.com)').includes('href="mailto:a@e.com"')
  )
})

test('a javascript: URL is replaced with a dead link', () => {
  const out = renderInline('[click me](javascript:alert(1))')
  assert.ok(out.includes('href="#"'))
  assert.ok(!out.includes('javascript:'))
})

test('the scheme check is case-insensitive', () => {
  // Without the `i` flag, "JavaScript:" would pass straight through.
  assert.ok(renderInline('[a](JavaScript:alert(1))').includes('href="#"'))
  assert.ok(renderInline('[a](HTTPS://e.com)').includes('href="HTTPS://e.com"'))
})

test('data and vbscript URLs are replaced with a dead link', () => {
  assert.ok(
    renderInline('[a](data:text/html,<script>x</script>)').includes('href="#"')
  )
  assert.ok(renderInline('[a](vbscript:msgbox)').includes('href="#"'))
})

test('a relative URL is replaced with a dead link', () => {
  // Not a security problem, but worth pinning: the allowlist is schemes, not
  // origins, so a bare path does not survive.
  assert.ok(renderInline('[a](/t/north-dakota/)').includes('href="#"'))
})

test('a rejected link keeps its label and stays clickable-looking', () => {
  // The label is shown either way. Dropping it would hide from the litigant
  // that the model tried to link them somewhere.
  const out = renderInline('[Read the notice](javascript:alert(1))')
  assert.ok(out.includes('>Read the notice</a>'))
})

test('links carry noopener and a new-tab target', () => {
  assert.ok(renderInline('[a](https://e.com)').includes(LINK))
})

// ============================================================================
// 4. Code spans
// ============================================================================

test('a code span is not searched for markdown', () => {
  // The renderer splits on code spans before transforming, so emphasis and
  // link syntax inside one are shown literally.
  const out = renderInline('use `**not bold**` here')
  assert.equal(out, 'use <code>**not bold**</code> here')
})

test('markdown outside a code span still renders', () => {
  const out = renderInline('**bold** and `code`')
  assert.equal(
    out,
    '<strong class="font-semibold">bold</strong> and <code>code</code>'
  )
})

test('a lone backtick is left as text', () => {
  assert.equal(renderInline('a ` b'), 'a ` b')
})

// ============================================================================
// 5. Block structure
// ============================================================================

test('empty and falsy input render as nothing', () => {
  assert.equal(renderMarkdown(''), '')
  assert.equal(renderMarkdown(null), '')
  assert.equal(renderMarkdown(undefined), '')
})

test('plain prose renders as one paragraph', () => {
  assert.equal(renderMarkdown('hello'), `<p ${P}>hello</p>`)
})

test('a blank line separates paragraphs', () => {
  const out = renderMarkdown('one\n\ntwo')
  assert.equal(out, `<p ${P}>one</p><p ${P}>two</p>`)
})

test('a single newline inside a paragraph becomes a line break', () => {
  const out = renderMarkdown('one\ntwo')
  assert.equal(out, `<p ${P}>one<br>two</p>`)
})

test('headings render as emphasised paragraphs, not h1-h6', () => {
  // Deliberate: chat messages sit inside the page's heading outline, and
  // emitting real headings there would corrupt it for screen readers.
  const out = renderMarkdown('## Filing your petition')
  assert.ok(out.startsWith('<p class="font-semibold'))
  assert.ok(out.includes('Filing your petition'))
  assert.ok(!out.includes('<h2'))
})

test('unordered lists accept both dash and asterisk markers', () => {
  const dash = renderMarkdown('- one\n- two')
  const star = renderMarkdown('* one\n* two')
  assert.ok(dash.includes('<ul'))
  assert.ok(dash.includes('<li>one</li><li>two</li>'))
  assert.equal(dash, star)
})

test('ordered lists render as ol regardless of the numbers used', () => {
  // The numbers are markers, not values: the browser renumbers from the ol.
  const out = renderMarkdown('1. one\n7. two')
  assert.ok(out.includes('<ol'))
  assert.ok(out.includes('<li>one</li><li>two</li>'))
})

test('consecutive blockquote lines join into one quote', () => {
  const out = renderMarkdown('> one\n> two')
  assert.ok(out.includes('<blockquote'))
  assert.ok(out.includes('one two'))
  assert.equal(out.match(/<blockquote/g).length, 1)
})

test('an unclosed code fence runs to the end of the message', () => {
  // Streaming means a half-arrived fence is normal, not malformed. It must
  // still escape its contents rather than dropping into paragraph handling.
  const out = renderMarkdown('```\n<b>still open')
  assert.ok(out.includes('<pre'))
  assert.ok(out.includes('&lt;b&gt;still open'))
})

test('inline markdown renders inside list items and quotes', () => {
  assert.ok(renderMarkdown('- **bold**').includes('<strong'))
  assert.ok(renderMarkdown('> **bold**').includes('<strong'))
  assert.ok(renderMarkdown('# **bold**').includes('<strong'))
})

test('a block element ends the paragraph before it', () => {
  const out = renderMarkdown('prose\n- item')
  assert.ok(out.indexOf('</p>') < out.indexOf('<ul'))
})
