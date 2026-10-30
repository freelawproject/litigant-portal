// Tests for the upload status helpers in static/js/chat_engine.js (#1124).
//
// Run with: node --test litigant_portal/app/tests/js/chat_engine_uploads.test.cjs
//
// Each file in an upload batch gets a status row (uploading, done, or failed
// with a reason), and one live region announces the batch. Both are pure
// functions, loaded the way ./README.md describes.

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../../static/js/chat_engine.js'),
  'utf8'
)
const context = { window: {}, document: { addEventListener() {} } }
vm.createContext(context)
vm.runInContext(source, context)

const { uploadRow, uploadAnnouncement } = context

test('a status row sets exactly one state flag', () => {
  // The template shows one icon per state with x-show, and the CSP build
  // can't negate, so each state is its own flag. Two true at once would
  // show two icons.
  for (const state of ['uploading', 'done', 'failed']) {
    const row = uploadRow('ticket.pdf', state)
    const flags = [row.isUploading, row.isDone, row.isFailed]
    assert.equal(flags.filter(Boolean).length, 1, state)
  }
})

test('a failed row carries its reason, other rows carry none', () => {
  assert.equal(
    uploadRow('notes.exe', 'failed', 'unsupported file type').reason,
    'unsupported file type'
  )
  assert.equal(uploadRow('ticket.pdf', 'done').reason, '')
})

test('rows get distinct ids for x-for keys', () => {
  assert.notEqual(
    uploadRow('ticket.pdf', 'uploading').id,
    uploadRow('ticket.pdf', 'uploading').id
  )
})

test('a batch in flight is announced as uploading', () => {
  assert.equal(
    uploadAnnouncement([
      uploadRow('ticket.pdf', 'uploading'),
      uploadRow('photo.jpg', 'uploading'),
    ]),
    'Uploading 2 files.'
  )
  assert.equal(
    uploadAnnouncement([uploadRow('ticket.pdf', 'uploading')]),
    'Uploading 1 file.'
  )
})

test('a finished batch is announced with each failure and its reason', () => {
  assert.equal(
    uploadAnnouncement([uploadRow('ticket.pdf', 'done')]),
    '1 file uploaded.'
  )
  assert.equal(
    uploadAnnouncement([
      uploadRow('ticket.pdf', 'done'),
      uploadRow('photo.jpg', 'done'),
      uploadRow('notes.exe', 'failed', 'unsupported file type'),
    ]),
    '2 files uploaded. notes.exe could not upload: unsupported file type.'
  )
  assert.equal(
    uploadAnnouncement([
      uploadRow('big.pdf', 'failed', 'too large (max 20 MB)'),
    ]),
    'big.pdf could not upload: too large (max 20 MB).'
  )
})

test('no rows announce nothing', () => {
  assert.equal(uploadAnnouncement([]), '')
})
