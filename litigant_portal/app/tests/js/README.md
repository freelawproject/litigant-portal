# JavaScript tests

Tests for the browser code in `litigant_portal/app/static/js/`.

## Running them

```sh
make test-js                                   # all of them
node --test litigant_portal/app/tests/js/*.test.cjs   # the same thing, directly
node --test litigant_portal/app/tests/js/chat_engine_markdown.test.cjs
```

`make test` runs these alongside the Python suite, and CI runs them in the
`tests` job.

**This adds Node as a host requirement for `make test`.** The Python suite runs
inside the Docker container; these run on the host, because the django image
carries no Node (Tailwind is a standalone binary there, not an npm package).
CI relies on the Node that ships with `ubuntu-latest` rather than adding a
`setup-node` step, which would mean pinning another action SHA for no gain.

**Pass the test files, not the directory.** `node --test <directory>` is not
supported on every version of Node. It fails on the Node 22 that CI currently
runs, which tries to load the directory as a module and reports `Cannot find
module`. Newer Node accepts it, which is how the directory form passed locally
and failed in CI. The glob above works on both.

They need no `npm install`: Node's built-in test runner and assertion library
do the work, so there is no `package.json`, no bundler and no lockfile to keep
current. That is deliberate — the repo serves its JavaScript as plain static
files with no build step, and a test harness that needed one would be the
first crack in that.

## Why `.cjs`

`package.json` does not exist, so Node treats `.js` as CommonJS anyway. The
explicit `.cjs` extension says so out loud and keeps the files working if a
`package.json` with `"type": "module"` ever appears.

## How a test file loads the code

The files under `static/js/` are browser scripts, not modules. They export
nothing, and some of them touch `window` or `document` at the top level. So a
test reads the source off disk and evaluates it in a `node:vm` context with
just enough of a fake browser to get through the top-level statements:

```js
const context = { window: {}, document: { addEventListener() {} } }
vm.createContext(context)
vm.runInContext(source, context)
// top-level function declarations are now properties of `context`
```

Two things make this work:

- Top-level `function` declarations in a sloppy-mode script become properties
  of the context object, so `context.renderMarkdown` is the real function.
- Stubbing `document.addEventListener` as a no-op means the `alpine:init`
  callback never fires, so the Alpine components inside it are never
  constructed. A test of the pure functions does not drag in Alpine.

This pattern comes from `agent_development.test.cjs` — follow it rather than
introducing a second approach.

## Gotcha: values from the vm are cross-realm

Anything the code under test constructs — an array, an object, a `Date` — gets
the vm context's prototypes, not the test file's. So:

```js
assert.deepEqual(msg.attachments, []) // fails: prototypes differ
assert.ok(Array.isArray(msg.attachments)) // works: cross-realm safe
```

`assert.deepStrictEqual` (which `node:assert/strict` gives you for
`deepEqual`) compares prototypes and rejects a vm-built `[]` against a local
one. `Array.isArray`, `typeof` and comparing primitives are all fine. Assert
on length and specific properties rather than on whole structures.

## What is worth testing here

The pure functions. `chat_engine.js` is two things in one file: roughly the
first 429 lines are pure functions with no DOM, network or Alpine, and the
rest is the `chatApp` and `chatUsage` components. The pure half needs no
stubbing beyond the above and is where the behaviour worth pinning down
lives.

Testing the components themselves would mean faking enough DOM to be its own
project. If that becomes necessary, it is a decision to make deliberately,
not one to arrive at by adding stubs until something passes.

## Verifying a test actually tests something

Tests written after the code get mutation-verified before they are trusted.
A test that passes against deliberately broken source is not coverage, it is
decoration, and there is no way to tell the two apart by reading them.

The loop: break one thing in the source, confirm a test fails, put it back.
Because these files load the source as a string, a mutant is a string
replacement rather than an edit to the real file:

```js
const SRC = fs.readFileSync(SOURCE_PATH, 'utf8')
const ctx = { window: {}, document: { addEventListener() {} } }
vm.createContext(ctx)
vm.runInContext(SRC.replace('deleteArmed: false,', 'deleteArmed: true,'), ctx)
// now re-run the assertions against ctx and expect them to fail
```

Write that as a throwaway script outside the repo, run it, and delete it. It is
scaffolding for one afternoon, not a second test suite to maintain. Assert that
each mutant is caught, and that the pattern you replaced was actually found:
a typo in the search string produces a "surviving" mutant that was never
applied.

Mutate behaviour a reviewer would care about, not syntax. The ones that earned
their keep here: dropping a key from `blankMessage()`, flipping one half of a
boolean pair, removing a `!!` coercion, reordering the `FILE_STYLES` patterns
so a catch-all shadows a specific one, an off-by-one on a size threshold, and
showing a tool result before its call finished.

Two things this caught that reading the tests would not have:

- **A passing assertion that proved nothing.** `!out.includes('<script>')` is
  satisfied by `<script&gt;`, which is a live tag. The escaping was fine; the
  assertion was not. It is now `!/<script/i`.
- **Assertions that silently never ran**, because the value under test came
  from the vm and `deepStrictEqual` was rejecting it on prototype rather than
  on content. See the cross-realm section above.

**A surviving mutant is not automatically a missing test.** Some code cannot be
killed because it cannot be reached. The `Math.max(0, …)` clamp in `timeSince`
is the example in this suite: with negative seconds every `Math.floor(seconds /
unit)` is also negative and never satisfies `value >= 1`, so the function falls
through to `'just now'` with or without the clamp. That is an equivalent
mutant. Leave the defensive code, keep the test that pins the behaviour, and
write down why nothing can cover the line, or the next person will spend the
afternoon rediscovering it.
