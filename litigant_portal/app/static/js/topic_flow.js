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

// A required field counts as answered once it holds something. false is a
// deliberate answer to a checkbox, so booleans are always considered answered.
function isAnswered(field) {
  if (field.dataType === 'boolean') return true
  return String(field.value ?? '').trim() !== ''
}

// Whether a field holds anything the server would have stored. Distinct from
// isAnswered: an untouched checkbox satisfies "required" but is nothing to
// clear, so Clear stays hidden until there's actually something to wipe.
function hasValue(field) {
  if (field.dataType === 'boolean') return field.value === true
  return String(field.value ?? '').trim() !== ''
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
    // Furthest step reached this session — the stepper lets you jump back to
    // anything you've seen, but never skip forward past the Next gate.
    maxVisited: 0,
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
      for (const step of this.steps) {
        for (const field of step.fields) {
          this.answers[field.name] = field.value
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

    // Every required field on a step must be answered before Next unlocks.
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
          clickable: index <= this.maxVisited,
          disabled: index > this.maxVisited,
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

    // The Next/Finish button's gate and which label shows. Split out because
    // `saving` and answer edits move it without rebuilding the whole step.
    syncNext() {
      const complete = this.stepIsComplete(this.steps[this.stepIndex])
      this.nextDisabled = !complete || this.saving
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
      this.hasAnswers = fields.some((f) => hasValue(f))
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
      this.maxVisited = 0
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
      // progress count, and the Next gate all see it.
      for (const step of this.steps) {
        for (const field of step.fields) {
          if (field.name === name) field.value = value
        }
      }
      this.syncNext()
      this.refreshProgress()
      this.interviewError = ''
    },

    goToStep(e) {
      const index = Number(e.currentTarget.dataset.index)
      if (Number.isNaN(index) || index > this.maxVisited) return
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
      if (this.nextDisabled) return
      const saved = await this.saveAnswers()
      if (!saved) return
      if (this.isLastStep) {
        this.closeInterview()
        return
      }
      this.stepIndex += 1
      this.maxVisited = Math.max(this.maxVisited, this.stepIndex)
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
        for (const step of this.steps) {
          for (const field of step.fields) {
            field.value = field.dataType === 'boolean' ? false : ''
            this.answers[field.name] = field.value
          }
        }
        this.stepIndex = 0
        this.maxVisited = 0
        this.interviewError = ''
        this.applyDeadlines(data.deadlines || [])
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
