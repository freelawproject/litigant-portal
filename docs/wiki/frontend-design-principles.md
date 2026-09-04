# Front-end design principles

> Current as of 2026-09-02.

## Why we build components this way

In January 2026 we settled the Litigant Portal's front end: Django with Django Cotton for components, Alpine.js for reactivity, Tailwind for styling, Postgres underneath. SvelteKit and React were both genuinely in the running. The stack we chose won on security, accessibility, CSP compliance, and on team support: FLP builds Django, so this is the code our team can review. (#14, #19, #15)

The decision came with a gap. Component frameworks ship with a component workbench, and Svelte and React give you Storybook essentially for free: WCAG audit tooling built-in, every component rendered in isolation, every variant visible on one page, somewhere a reviewer or a designer can _see_ the system instead of reading source. Django and Cotton give you nothing of the kind (yet).

So we build our own. [Atomic Design](https://atomicdesign.bradfrost.com/) is how.

## What it gets us

**A component workbench.** `/style-guide/` is our Storybook. Atoms, molecules, and organisms are what make it browseable and reviewable rather than an alphabetical pile: a shared vocabulary for talking about the system with people who don't read templates.

**Accessibility by default.** WCAG AA is FLP's floor, not a stretch goal. The primitives are where that floor gets enforced once instead of per page: `form-field` emits `aria-invalid` and owns the label/error/help-text relationship, the link atom carries the screen-reader new-tab cue. Compose from atoms and you inherit the floor for free. Hand-roll a `<button>` and you inherit nothing.

**Mobile-first layout that holds.** Most of our users are on phones, often older ones on bad connections. Small pieces with fixed behavior are what keep the site frame stable across breakpoints, instead of every page inventing its own responsive rules and its own drawer.

## What this document is for

Atomic Design has real, well-known costs, and this stack has real gaps. Both get their own sections below, honestly. This one exists so the _why_ is written down: the choice was deliberate, the reasons are still true, and nobody should have to reconstruct them from meeting memory again.

## Where Atomic Design costs us

These are real, and we know them. We chose to pay them.

**Locality.** Feature code spreads across tiers. Chat's pieces sit in `atoms/`, `molecules/`, and `organisms/` rather than one folder, so you can't browse a whole feature in one place.

**A fuzzy middle boundary.** Molecule versus organism is a judgment call, and it comes up again on every new component. The answer rarely changes how the component is written.

**A pull toward premature extraction.** "A page is composed of organisms" invites a component before there is a second use for it. Some of ours are referenced once.

**Ceremony on small work.** A new variant means touching the component, the style guide, and often a props table. That is the cost of having a workbench at all.

Where a cost has a cheap mitigation, it is in [The rules](#the-rules) below.

## What the stack doesn't give us, and what we build instead

Three tools a component framework hands you, that we build or replace by hand.

**The workbench.** `/style-guide/` stands in for Storybook. The difference that matters is coupling: a Storybook story lives next to its component, so a deleted or broken one shows up as a build failure. Ours is a page someone remembers to update.

**The formatter.** There is no Cotton-aware formatter. djlint's mangled template tags inside HTML attributes, so it runs lint-only and the conventions are manual (see the `django-templates` skill). `prettier-plugin-django-cotton` is the replacement, in progress, and this repo is its home. (#204, #215)

**Accessibility tooling.** Storybook has a11y addons; we audit instead. Our floor is enforced in the primitives and checked by review and audit passes, not by a tool watching every render. (See [WCAG strategy](wcag-strategy.md).)

## The rules

Enough to settle the recurring questions without a meeting.

**Compose before you create.** Check `templates/cotton/` and the theme tokens in `src/main.css` first. If an existing component is almost right, add a prop. New components and new tokens are the last resort, not the opening move.

**Extract on the second use.** The first time, write it inline. The second time, extract it. Not "I might reuse this," which builds an abstraction for an imagined need that rarely matches the real one when it arrives. If you are copy-pasting markup, the paste is the second use.

**Tier by composition, not by size.** An atom is one element with a design and accessibility decision baked in. A molecule is atoms plus the layout that gives them a single job. An organism is a page section composed of molecules. When it is genuinely ambiguous, take the lower tier: a component placed too low costs nothing, one placed too high is harder to find and invites duplication.

**One component with variants, or two components?** One if a change to one should propagate to the others, the way `button variant="primary|secondary"` evolves together. Two if the only thing they share is looking similar today. The test: imagine redesigning one variant. If the change would need a conditional to exempt the others, they were always two components sharing a file.

**Never hand-roll what a primitive owns.** Buttons, links, form fields, and icons go through their atoms. Not for tidiness: those atoms are where the WCAG floor lives, and a raw `<button>` inherits none of it. See [What it gets us](#what-it-gets-us).

**A component is not finished until it is in the style guide.** Our workbench does not couple itself to the code, so the entry is part of the work rather than follow-up. Same commit.

**Deleting a component means deleting its style-guide entry.** Same commit, along with every reference to it. A dangling `<c-...>` reference is a runtime error on whatever page renders it, and it will not surface until someone opens that page.

**Alpine is reactivity, not rendering.** Structure and content are Django and Cotton's job; Alpine toggles, binds, and transitions. The CSP-build constraints that follow from this are in `CLAUDE.md`.

### Where the Alpine boundary bites

"Reactivity, not rendering" is easy to say and hard to review, so it needs a test rather than good intentions.

**The test: if the JS is emitting HTML tags or Tailwind class strings, it is rendering.** State lives in JS. Markup and classes come from templates. That catches the two real cases we have — the `<pre>` and `<blockquote>` strings inside `renderMarkdown`, and the `DROPZONE_IDLE` / `DROPZONE_ACTIVE` class pair that hands the template a Tailwind string through a bound property (#784, which carries two CSP-safe candidate patterns).

**The named exception: streamed assistant content.** Text arriving token by token over SSE has no natural server round-trip, so it is assembled client-side. The condition on the exception is that escaping stays centralized in one place, which `escapeHtml()` already is. Naming it as an exception is the point; pretending the rule has no exceptions is how the rule gets ignored everywhere else.

**The counter-example, which proves the boundary is reachable:** tool call and result cards travel the same SSE stream under the same constraints, and Django renders them server-side before shipping the HTML. Same stream, markup stayed in templates. Point at that, not at an abstraction.

Worth naming why the slope is slippery rather than treating each instance as carelessness. Once a JS component owns the state, emitting a string is three lines and threading the data back into a template is a plumbing exercise. A rule that only says "don't" loses to that every time.
