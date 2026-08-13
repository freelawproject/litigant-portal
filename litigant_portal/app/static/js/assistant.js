// Components for the litigant assistant's chat surface. The chat engine
// (chat_engine.js) stays agent-neutral; anything specific to the
// LitigantAssistant agent — like the briefcase's active-guide card —
// lives here instead.
//
// assistantBriefcase nests inside a host component marked with the
// data-briefcase-host attribute (chatApp on the chat page, simulateApp on
// the admin simulate tab) and grabs the host's data with Alpine.$data,
// the same pattern chatUsage uses — under the CSP build, `this` inside a
// component's methods only sees its own data, never the parent scope.
// The host contract: a `stateData` object (the agent thread state), plus
// an optional `resolveSummaryUrl(ref)` override for hosts whose flow
// summaries must be fetched for someone else's identity.

// Blank card so the CSP-safe dot-paths in the template never hit null.
function blankFlowCard() {
  return {
    name: '',
    topicTitle: '',
    url: '',
    progressLabel: '',
    progressStyle: { width: '0%' },
    forms: [],
    hasForms: false,
    packetUrl: '',
    hasPacket: false,
  }
}

// Precompute everything the active-guide card needs from a flow summary
// response (see topic_flow_summary_view).
function decorateFlowCard(data) {
  const progress = data.progress || { answered: 0, total: 0, label: '' }
  const pct = progress.total
    ? Math.round((progress.answered / progress.total) * 100)
    : 0
  const forms = (data.forms || []).map((f) => ({
    slug: f.slug,
    name: f.name,
    url: f.url,
  }))
  return {
    name: data.name || '',
    topicTitle: data.topic_title || '',
    url: data.url || '',
    progressLabel: progress.label || '',
    progressStyle: { width: pct + '%' },
    forms,
    hasForms: forms.length > 0,
    packetUrl: data.packet_url || '',
    hasPacket: !!data.packet_url,
  }
}

document.addEventListener('alpine:init', () => {
  // The briefcase's active-guide card, hydrated from the flow summary
  // endpoint whenever the thread state points at a flow.
  Alpine.data('assistantBriefcase', () => ({
    flowCard: blankFlowCard(),
    hasFlowCard: false,
    flowCardFetchUrl: '',
    // Debug view of the raw agent state (the briefcase's fallback body).
    stateJson: '',
    hasState: false,
    noState: true,
    app: null,

    init() {
      // `stateData` belongs to the enclosing host component; watching it
      // refreshes the card on thread loads and as tool calls stream state.
      this.app = Alpine.$data(this.$root.closest('[data-briefcase-host]'))
      this.$watch('app.stateData', () => this.refresh())
      this.refresh()
    },

    // Everything the briefcase renders derives from the host's stateData,
    // computed here so the partial's bindings all live on this component.
    refresh() {
      const state = (this.app && this.app.stateData) || {}
      this.stateJson = prettyJson(state)
      this.hasState = Object.keys(state).length > 0
      this.noState = !this.hasState
      this.refreshFlowCard()
    },

    // Hydrate (or clear) the active-guide card. Progress and forms are
    // fetched live so the card agrees with the flow page even when
    // answers were changed there.
    async refreshFlowCard() {
      const state = (this.app && this.app.stateData) || {}
      const ref = state.active_topic_flow
      const url =
        ref &&
        (this.app.resolveSummaryUrl
          ? this.app.resolveSummaryUrl(ref)
          : ref.summary_url)
      if (!url) {
        this.hasFlowCard = false
        this.flowCard = blankFlowCard()
        this.flowCardFetchUrl = ''
        return
      }
      this.flowCardFetchUrl = url
      try {
        const res = await fetch(url, {
          headers: { Accept: 'application/json' },
        })
        // A newer state arrived while this fetch was in flight — drop it.
        if (this.flowCardFetchUrl !== url) return
        if (!res.ok) {
          this.hasFlowCard = false
          this.flowCard = blankFlowCard()
          return
        }
        this.flowCard = decorateFlowCard(await res.json())
        this.hasFlowCard = true
      } catch (e) {
        console.error('Failed to load flow summary:', e)
      }
    },
  }))
})
