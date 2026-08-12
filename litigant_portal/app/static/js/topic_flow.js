// Public topic-flow page — the guided interview modal and computed deadlines.
// The CSP Alpine build can't evaluate inline expressions, so every row the
// templates loop over is decorated here (precomputed flags, labels, classes)
// and the markup binds only property paths and method names. Loop items pass
// their identity through data-* attributes, which handlers read off the event.
//
// The interview definition is fetched from interviewUrl (topic_flow_api:interview in
// views/topic_flow.py): steps, their fields, and the identity's stored
// answers already merged in as values. It is not inlined into the page —
// the modal is the only thing that renders it, so a visitor who never opens
// it never pays for it. Answers POST to answersUrl on every Next, so
// progress survives a refresh — the wizard itself is not resumable by
// design, it just reopens at step one with everything prefilled.

// "2026-02-14" -> "February 14, 2026" (parsed as local, not UTC midnight).
function deadlineDateLabel(iso) {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

// Flow data type -> <input type>. Choice and boolean render as their own
// controls and never reach here.
const INPUT_TYPES = {
  date: 'date',
  datetime: 'datetime-local',
  number: 'number',
}

// A field counts as answered when an answer is stored (the server sends
// `answered` alongside the default-merged value) or the user has edited it
// this session (setAnswer keeps the flag current). Authored defaults
// prefill inputs but are suggestions, not answers — so a fresh flow shows
// zero progress even when some inputs arrive prefilled.
function isAnswered(field) {
  return field.answered === true
}

// "Step {current} of {total}" -> "Step 2 of 5". Counted strings come from
// data-* attributes so they stay in the template where gettext can see them.
function format(template, values) {
  return template.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? '')
}

document.addEventListener('alpine:init', () => {
  Alpine.data('flowPage', () => ({
    // --- Answers and deadlines ---------------------------------------
    // Field name -> current value, POSTed wholesale so the server can
    // recompute every deadline in one round trip.
    answers: {},
    answersUrl: '',
    // Decorated deadline rows; the server-rendered list hides once these
    // hydrate so recomputed dates can replace it.
    deadlines: [],
    hydrated: false,
    notHydrated: true,
    hasCalendar: false,

    // --- Interview ---------------------------------------------------
    interviewUrl: '',
    // Fetched after init(). interviewPending gates the launcher so it can't
    // open an empty wizard; interviewReady gates the progress summary so an
    // empty bar doesn't flash before the steps land.
    interviewPending: true,
    interviewReady: false,
    steps: [],
    stepIndex: 0,
    // Never null: the modal's bindings walk these paths before init() lands.
    step: {
      title: '',
      hasTitle: false,
      description: '',
      hasDescription: false,
      fields: [],
    },
    stepChips: [],
    interviewOpen: false,
    hasInterview: false,
    canGoBack: false,
    isLastStep: false,
    saving: false,
    nextDisabled: true,
    showNextLabel: false,
    showFinishLabel: false,
    showRequiredHint: false,
    interviewError: '',
    stepCounter: '',
    // Sidebar progress summary.
    progressLabel: '',
    progressStyle: { width: '0%' },
    // --- Clear answers -----------------------------------------------
    hasAnswers: false,
    clearOpen: false,
    clearing: false,
    notClearing: true,
    clearError: '',
    // Translated "{current} of {total}"-style templates, read off the root.
    strings: {},

    init() {
      this.answersUrl = this.$root.dataset.answersUrl
      this.interviewUrl = this.$root.dataset.interviewUrl || ''
      this.strings = {
        stepCounter: this.$root.dataset.stepCounterText || '',
        stepFallback: this.$root.dataset.stepFallbackText || '',
        progress: this.$root.dataset.progressText || '',
      }
      // Deadlines seed synchronously off the server-rendered rows, so the
      // sidebar swaps to the decorated list without waiting on the network.
      this.applyDeadlines(
        Array.from(this.$root.querySelectorAll('[data-deadline]'), (el) => ({
          label: el.dataset.label,
          description: el.dataset.description,
          date: el.dataset.date || null,
        }))
      )
      this.hydrated = true
      this.notHydrated = false
      this.loadInterview()
    },

    // Pull the interview definition. Deliberately not awaited by init():
    // nothing above depends on it, and the page is fully usable (prose,
    // links, deadlines, form downloads) while it's in flight.
    async loadInterview() {
      if (!this.interviewUrl) {
        this.interviewPending = false
        return
      }
      try {
        const res = await fetch(this.interviewUrl, {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const payload = await res.json()
        this.steps = payload.steps || []
      } catch (err) {
        console.error('Failed to load the interview:', err)
        this.interviewPending = false
        return
      }
      this.hasInterview = this.steps.length > 0
      // Seed only stored answers: an untouched prefilled default must not
      // ride along on the next save and silently become a stored answer.
      for (const step of this.steps) {
        for (const field of step.fields) {
          if (field.answered) this.answers[field.name] = field.value
        }
      }
      this.refreshInterview()
      this.interviewPending = false
      this.interviewReady = this.hasInterview
    },

    // --- Deadlines ---------------------------------------------------

    // Precompute CSP-safe bindings for a deadline row.
    decorateDeadline(row) {
      const hasDate = !!row.date
      return {
        label: row.label,
        description: row.description || '',
        hasDescription: !!row.description,
        hasDate,
        noDate: !hasDate,
        dateLabel: hasDate ? deadlineDateLabel(row.date) : '',
      }
    },

    applyDeadlines(rows) {
      this.deadlines = rows.map((row) => this.decorateDeadline(row))
      this.hasCalendar = this.deadlines.some((d) => d.hasDate)
    },

    // --- Interview state ---------------------------------------------

    // Whether a step's required fields are all answered. Purely a signal
    // (chip check marks, the footer hint) — nothing gates on it, since the
    // interview lets people move freely and come back to gaps later.
    stepIsComplete(step) {
      return step.fields.every((f) => !f.required || isAnswered(f))
    },

    // Decorate one field for rendering: which control to draw, its current
    // value, and a unique input id for the label to point at.
    decorateField(field, stepIndex) {
      const isChoice = field.dataType === 'choice'
      const isBoolean = field.dataType === 'boolean'
      return {
        name: field.name,
        label: field.label,
        helpText: field.helpText || '',
        hasHelp: !!field.helpText,
        required: field.required,
        dataType: field.dataType,
        isChoice,
        isBoolean,
        isInput: !isChoice && !isBoolean,
        inputType: INPUT_TYPES[field.dataType] || 'text',
        // Alpine drops a null-bound attribute, so only number inputs get one.
        step: field.dataType === 'number' ? 'any' : null,
        value: isBoolean ? '' : (field.value ?? ''),
        checked: isBoolean ? !!field.value : false,
        inputId: `interview-${stepIndex}-${field.name}`,
        choices: (field.choices || []).map((choice) => ({
          value: choice.value,
          label: choice.label || choice.value,
          selected: String(field.value ?? '') === String(choice.value),
        })),
      }
    },

    // Rebuild everything the interview markup binds to. Called after any
    // state change rather than tracking each derived flag by hand.
    refreshInterview() {
      if (!this.hasInterview) return
      const current = this.steps[this.stepIndex]
      this.step = {
        title: current.title,
        hasTitle: !!current.title,
        description: current.description || '',
        hasDescription: !!current.description,
        fields: current.fields.map((f) =>
          this.decorateField(f, this.stepIndex)
        ),
      }
      this.stepChips = this.steps.map((step, index) => {
        const isCurrent = index === this.stepIndex
        const done = this.stepIsComplete(step)
        return {
          index,
          number: index + 1,
          title:
            step.title ||
            format(this.strings.stepFallback, { current: index + 1 }),
          isCurrent,
          // A tick replaces the number on a finished step you're not on.
          showCheck: done && !isCurrent,
          showNumber: !(done && !isCurrent),
          markerClass: isCurrent
            ? 'border-primary-600 bg-primary-600 text-white'
            : done
              ? 'border-primary-600 bg-primary-50 text-primary-700'
              : 'border-greyscale-300 bg-white text-greyscale-400',
          labelClass: isCurrent
            ? 'text-primary-700 font-medium'
            : 'text-greyscale-500',
          // The connector to the previous chip; filled once that step is past.
          showConnector: index > 0,
          connectorClass:
            index <= this.stepIndex ? 'bg-primary-600' : 'bg-greyscale-200',
        }
      })
      this.stepCounter = format(this.strings.stepCounter, {
        current: this.stepIndex + 1,
        total: this.steps.length,
      })
      this.canGoBack = this.stepIndex > 0
      this.isLastStep = this.stepIndex === this.steps.length - 1
      this.syncNext()
      this.refreshProgress()
    },

    // The Next/Finish button's state and which label shows. Split out
    // because `saving` and answer edits move it without rebuilding the
    // whole step. Unanswered required fields only show the hint — they
    // never block Next.
    syncNext() {
      const complete = this.stepIsComplete(this.steps[this.stepIndex])
      this.nextDisabled = this.saving
      this.showRequiredHint = !complete
      this.showNextLabel = !this.saving && !this.isLastStep
      this.showFinishLabel = !this.saving && this.isLastStep
    },

    // "6 of 9 answered" plus the sidebar bar width. Counts every field, not
    // just required ones — it's a fullness signal, not a validity one.
    refreshProgress() {
      const fields = this.steps.flatMap((step) => step.fields)
      const answered = fields.filter((f) => isAnswered(f)).length
      const total = fields.length
      this.progressLabel = format(this.strings.progress, {
        answered,
        total,
      })
      this.progressStyle = {
        width: total ? `${Math.round((answered / total) * 100)}%` : '0%',
      }
      this.hasAnswers = fields.some((f) => isAnswered(f))
    },

    // --- Interview actions -------------------------------------------

    openInterview() {
      // The launcher is disabled while the fetch is in flight, but a failed
      // load leaves it enabled with nothing to show — never open an empty
      // wizard.
      if (!this.hasInterview) return
      // Always reopen at the beginning: answers persist, wizard position
      // deliberately doesn't.
      this.stepIndex = 0
      this.interviewError = ''
      this.interviewOpen = true
      this.refreshInterview()
      this.focusFirstField()
    },

    closeInterview() {
      this.interviewOpen = false
      if (this.hasInterview) this.saveAnswers()
    },

    // Backdrop clicks close; clicks inside the dialog must not bubble out.
    stopClick(e) {
      e.stopPropagation()
    },

    focusFirstField() {
      this.$nextTick(() => {
        const el = this.$root.querySelector('[data-interview-field]')
        if (el) el.focus()
      })
    },

    // Change handler for every interview control — the field name rides on
    // the element's data-field attribute.
    setAnswer(e) {
      const el = e.currentTarget
      const name = el.dataset.field
      const value = el.type === 'checkbox' ? el.checked : el.value
      this.answers[name] = value
      // Write through to the step definition so the decorated copy, the
      // progress count, and the completeness signals all see it.
      for (const step of this.steps) {
        for (const field of step.fields) {
          if (field.name !== name) continue
          field.value = value
          field.answered =
            el.type === 'checkbox' || String(value ?? '').trim() !== ''
        }
      }
      this.syncNext()
      this.refreshProgress()
      this.interviewError = ''
    },

    // Jump anywhere from the stepper. The save is fire-and-forget: every
    // save posts the whole answers map, so a failure here loses nothing —
    // the next save (Next, close, another jump) carries the same answers.
    goToStep(e) {
      const index = Number(e.currentTarget.dataset.index)
      if (Number.isNaN(index) || index === this.stepIndex) return
      this.saveAnswers()
      this.stepIndex = index
      this.interviewError = ''
      this.refreshInterview()
      this.focusFirstField()
    },

    back() {
      if (this.stepIndex === 0) return
      this.stepIndex -= 1
      this.interviewError = ''
      this.refreshInterview()
      this.focusFirstField()
    },

    // Save first, then advance. A failed save leaves the user on the step
    // with the error showing — advancing past answers we didn't persist is
    // exactly the silent data loss this flow is supposed to prevent.
    async next() {
      if (this.saving) return
      const saved = await this.saveAnswers()
      if (!saved) return
      if (this.isLastStep) {
        this.closeInterview()
        return
      }
      this.stepIndex += 1
      this.refreshInterview()
      this.focusFirstField()
    },

    // The one write path. POSTs a whole answers map — the endpoint treats a
    // blank value as "delete", so saving and clearing differ only in what
    // they send. Returns the parsed response, or throws.
    async postAnswers(answers) {
      const res = await fetch(this.answersUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken(),
        },
        body: JSON.stringify({ answers }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || 'Request failed: ' + res.status)
      }
      return res.json()
    },

    // The response carries recomputed deadlines, so the sidebar updates as
    // the interview progresses.
    async saveAnswers() {
      this.saving = true
      this.syncNext()
      try {
        const data = await this.postAnswers(this.answers)
        this.applyDeadlines(data.deadlines || [])
        return true
      } catch (err) {
        console.error('Failed to save answers:', err)
        this.interviewError = err.message
        return false
      } finally {
        this.saving = false
        this.syncNext()
      }
    },

    // --- Clear answers -----------------------------------------------

    openClear() {
      this.clearError = ''
      this.clearOpen = true
    },

    closeClear() {
      if (this.clearing) return
      this.clearOpen = false
    },

    // Send every field blank: the endpoint deletes an answer whose value is
    // empty, so this wipes the identity's stored answers for the flow in one
    // round trip. Local state only resets once the server confirms.
    async confirmClear() {
      if (this.clearing) return
      this.clearing = true
      this.notClearing = false
      this.clearError = ''
      const blank = {}
      for (const step of this.steps) {
        for (const field of step.fields) blank[field.name] = ''
      }
      try {
        const data = await this.postAnswers(blank)
        this.applyDeadlines(data.deadlines || [])
        // Re-fetch instead of blanking locally: the server re-merges
        // authored field defaults into the interview, so this is the only
        // way the post-clear view matches what a refresh would show.
        this.answers = {}
        await this.loadInterview()
        this.stepIndex = 0
        this.interviewError = ''
        this.refreshInterview()
        this.clearOpen = false
      } catch (err) {
        console.error('Failed to clear answers:', err)
        this.clearError = err.message
      } finally {
        this.clearing = false
        this.notClearing = true
      }
    },

    csrfToken() {
      const input = document.querySelector('[name=csrfmiddlewaretoken]')
      return input ? input.value : ''
    },
  }))
})
