# JavaScript tests

Tests for the browser code in `litigant_portal/app/static/js/`.

## Running them

```sh
make test-js                                   # all of them
node --test litigant_portal/app/tests/js/      # the same thing, directly
node --test litigant_portal/app/tests/js/chat_engine_markdown.test.cjs
```

`make test` runs these alongside the Python suite, and CI runs them in the
`tests` job.

**This adds Node as a host requirement for `make test`.** The Python suite runs
inside the Docker container; these run on the host, because the django image
carries no Node (Tailwind is a standalone binary there, not an npm package).
Anything from Node 18 onward works — `node:test`, `node:assert/strict` and
`node:vm` have been stable since then. CI relies on the Node that ships with
`ubuntu-latest` rather than adding a `setup-node` step, which would mean
pinning another action SHA for no gain.

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

## What is worth testing here

The pure functions. `chat_engine.js` is two things in one file: roughly the
first 429 lines are pure functions with no DOM, network or Alpine, and the
rest is the `chatApp` and `chatUsage` components. The pure half needs no
stubbing beyond the above and is where the behaviour worth pinning down
lives.

Testing the components themselves would mean faking enough DOM to be its own
project. If that becomes necessary, it is a decision to make deliberately,
not one to arrive at by adding stubs until something passes.
