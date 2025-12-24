/**
 * Test cases for the renderMarkdown function.
 *
 * Usage (browser console):
 *   1. Open the chat page
 *   2. Paste this file contents into console
 *   3. Call testRenderMarkdown()
 *
 * Usage (Node.js):
 *   node scripts/test_render.js
 */

// Copy of renderMarkdown from chat.js for testing
function renderMarkdown(text) {
  if (!text) return ''
  return text
    // Strip LLM artifacts
    .replace(/\\+/g, '')           // Backslash escapes
    .replace(/<!--.*?-->/g, '')    // HTML comments
    // Escape HTML first
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Bold: **text** or __text__
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    // Italic: *text* or _text_
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/_([^_]+)_/g, '<em>$1</em>')
    // Links: [text](url)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-primary-600 underline" target="_blank" rel="noopener">$1</a>')
    // Ordered lists: 1. item or 1\. item (escaped period)
    .replace(/^\d+[.\\]+\s+(.+)$/gm, '<li>$1</li>')
    // Unordered lists: * item or - item
    .replace(/^[\*\-]\s+(.+)$/gm, '<li>$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul class="list-disc ml-4 my-2">$&</ul>')
    // Headers: ## text
    .replace(/^###\s+(.+)$/gm, '<h4 class="font-semibold mt-3 mb-1">$1</h4>')
    .replace(/^##\s+(.+)$/gm, '<h3 class="font-semibold text-lg mt-3 mb-1">$1</h3>')
    // Paragraphs: double newlines
    .replace(/\n\n+/g, '</p><p class="my-2">')
    // Single newlines to <br>
    .replace(/\n/g, '<br>')
    // Wrap in paragraph
    .replace(/^(.+)$/, '<p class="my-2">$1</p>')
}

// Test cases: [input, expected_to_contain, expected_not_to_contain]
const testCases = [
  // Backslash escapes
  ['\\\\Address:\\\\', 'Address:', ['\\']],
  ['1\\. First item', '<li>First item</li>', ['\\']],
  ['Step 1\\:', 'Step 1:', ['\\']],

  // HTML comments
  ['Before<!--comment-->After', 'BeforeAfter', ['<!--', '-->']],
  ['Text<!---->', 'Text', ['<!--']],

  // Bold
  ['**bold text**', '<strong>bold text</strong>', []],
  ['__also bold__', '<strong>also bold</strong>', []],

  // Italic
  ['*italic text*', '<em>italic text</em>', []],
  ['_also italic_', '<em>also italic</em>', []],

  // Links
  ['[Click here](https://example.com)', '<a href="https://example.com"', []],

  // Ordered lists
  ['1. First\n2. Second', '<li>First</li>', []],
  ['1\\. Escaped', '<li>Escaped</li>', ['\\']],

  // Unordered lists
  ['- Item one\n- Item two', '<li>Item one</li>', []],
  ['* Asterisk item', '<li>Asterisk item</li>', []],

  // Headers
  ['## Header Two', '<h3', []],
  ['### Header Three', '<h4', []],

  // HTML escaping
  ['<script>alert("xss")</script>', '&lt;script&gt;', ['<script>']],

  // Combined
  ['**Bold** and *italic*', '<strong>Bold</strong>', ['**', '*italic*']],
];

function testRenderMarkdown() {
  console.log('Testing renderMarkdown function...\n');
  let passed = 0;
  let failed = 0;

  for (const [input, shouldContain, shouldNotContain = []] of testCases) {
    const output = renderMarkdown(input);
    let ok = true;
    let reason = '';

    // Check should contain
    if (!output.includes(shouldContain)) {
      ok = false;
      reason = `Missing: "${shouldContain}"`;
    }

    // Check should not contain
    for (const bad of shouldNotContain) {
      if (output.includes(bad)) {
        ok = false;
        reason = `Unwanted: "${bad}"`;
        break;
      }
    }

    if (ok) {
      console.log(`✓ PASS: ${JSON.stringify(input).slice(0, 40)}`);
      passed++;
    } else {
      console.log(`✗ FAIL: ${JSON.stringify(input).slice(0, 40)}`);
      console.log(`  Input:  ${input}`);
      console.log(`  Output: ${output}`);
      console.log(`  Reason: ${reason}`);
      failed++;
    }
  }

  console.log(`\n${passed}/${passed + failed} tests passed`);
  return failed === 0;
}

// Run if Node.js
if (typeof module !== 'undefined' && require.main === module) {
  const success = testRenderMarkdown();
  process.exit(success ? 0 : 1);
}

// Export for browser
if (typeof window !== 'undefined') {
  window.testRenderMarkdown = testRenderMarkdown;
}
