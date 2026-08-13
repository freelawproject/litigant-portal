// Admin dashboard — sidebar tab switching. The CSP Alpine build can't
// evaluate inline expressions, so per-tab flags are precomputed here. Tab
// styling lives in the template via data-active variants; Alpine only
// toggles the data-active attribute, so the server-rendered default
// (settings active) paints correctly before Alpine loads.
const ADMIN_TABS = ['settings', 'users', 'knowledge', 'simulate']
// On/off pill styles for the per-user permission toggles.
const PILL_ON = 'bg-primary-100 text-primary-700 hover:bg-primary-200'
const PILL_OFF = 'bg-greyscale-100 text-greyscale-500 hover:bg-greyscale-200'
// Court-detail fields whose save button tracks a loaded baseline. Model
// selections are not listed — they save automatically on change.
const SITE_FIELDS = [
  'siteCourtName',
  'siteJurisdictionLevel',
  'siteState',
  'siteOfficialUrl',
  'siteOfficialResourcesUrl',
]

// Heroicons (outline) path data for the topic icons. Topic cards are
// client-rendered, so the server-side icon component can't supply these;
// names map onto the same heroicons the home page uses.
const KB_ICON_PATHS = {
  home: 'm2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25',
  users:
    'M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z',
  'currency-dollar':
    'M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  'shield-check':
    'M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z',
  identification:
    'M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5a2.25 2.25 0 0 0 2.25 2.25Zm6-10.125a1.875 1.875 0 1 1-3.75 0 1.875 1.875 0 0 1 3.75 0Zm1.294 6.336a6.721 6.721 0 0 1-3.17.789 6.721 6.721 0 0 1-3.168-.789 3.376 3.376 0 0 1 6.338 0Z',
  truck:
    'M8.25 18.75a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 0 1-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 0 0-3.213-9.193 2.056 2.056 0 0 0-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 0 0-10.026 0 1.106 1.106 0 0 0-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12',
  scale:
    'M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0 0 12 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52 2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 0 1-2.031.352 5.988 5.988 0 0 1-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971Zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0 2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 0 1-2.031.352 5.989 5.989 0 0 1-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971Z',
  'book-open':
    'M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25',
}

// Size a textarea to its content so it grows instead of scrolling.
function autoResize(el) {
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

// Immutably swap a row with its neighbor for an optimistic reorder.
function swapRow(rows, id, direction) {
  const idx = rows.findIndex((r) => r.id === id)
  const other = direction === 'up' ? idx - 1 : idx + 1
  if (idx < 0 || other < 0 || other >= rows.length) return rows
  const next = rows.slice()
  ;[next[idx], next[other]] = [next[other], next[idx]]
  return next
}

// The flow field names a form mapping's template pulls from. Mirrors the
// str.format() syntax _resolve_template uses server-side: "{name}" with an
// optional format spec ("{date:%b %d}") or attribute/index access
// ("{addr.city}"), and "{{" escaping a literal brace.
function templateFieldRefs(template) {
  const refs = []
  for (const match of (template || '')
    .replace(/{{|}}/g, '')
    .matchAll(/{([^{}]*)}/g)) {
    const name = match[1].split(/[:!.[]/)[0].trim()
    if (name && !refs.includes(name)) refs.push(name)
  }
  return refs
}

// The builder's field-type options (mirrors TopicFlowField.DataType).
const FIELD_DATA_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'date', label: 'Date' },
  { value: 'datetime', label: 'Datetime' },
  { value: 'number', label: 'Number' },
  { value: 'choice', label: 'Choice' },
  { value: 'boolean', label: 'Boolean' },
]

// Choice list <-> the field modal's one-per-line "value | label" textarea.
function choicesToText(choices) {
  return (choices || [])
    .map((c) =>
      c.label && c.label !== c.value ? c.value + ' | ' + c.label : c.value
    )
    .join('\n')
}

function parseChoicesText(text) {
  return String(text || '')
    .split('\n')
    .map((line) => {
      const [value, ...rest] = line.split('|')
      const v = (value || '').trim()
      const label = rest.join('|').trim()
      return v ? { value: v, label: label || v } : null
    })
    .filter(Boolean)
}

// Minimal escape-first markdown for flow section bodies — paragraphs,
// dash lists, links, bold/italic. Mirrors chat_engine.js's renderer so
// authored corpus copy previews faithfully and safely.
function mdEscape(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function mdInline(text) {
  return mdEscape(text)
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, label, url) => {
      const safe = /^(https?:|mailto:)/i.test(url) ? url : '#'
      return (
        '<a href="' +
        safe +
        '" target="_blank" rel="noopener noreferrer" class="text-primary-700 underline hover:no-underline">' +
        label +
        '</a>'
      )
    })
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>')
}

function renderFlowMarkdown(md) {
  if (!md) return ''
  const lines = String(md).split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    if (/^\s*-\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
        items.push(
          '<li>' + mdInline(lines[i].replace(/^\s*-\s+/, '')) + '</li>'
        )
        i++
      }
      out.push(
        '<ul class="list-disc pl-5 my-2 space-y-0.5">' +
          items.join('') +
          '</ul>'
      )
      continue
    }
    out.push('<p class="my-2 first:mt-0 last:mb-0">' + mdInline(line) + '</p>')
    i++
  }
  return out.join('')
}

function kbIconSvg(name) {
  const d = KB_ICON_PATHS[name] || KB_ICON_PATHS['book-open']
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"' +
    ' stroke-width="1.5" stroke="currentColor" class="w-6 h-6">' +
    '<path stroke-linecap="round" stroke-linejoin="round" d="' +
    d +
    '"/></svg>'
  )
}

document.addEventListener('alpine:init', () => {
  Alpine.data('adminApp', () => ({
    activeTab: 'settings',
    tabActive: {
      settings: true,
      users: false,
      knowledge: false,
      simulate: false,
    },
    showSettings: true,
    showUsers: false,
    showKnowledge: false,
    showSimulate: false,
    // Mobile drawers — the side panels collapse below lg.
    navOpen: false,
    libraryOpen: false,
    // Whether the current tab has right-rail (library) content.
    railActive: true,
    // Site settings
    siteCourtName: '',
    siteJurisdictionLevel: '',
    siteState: '',
    siteOfficialUrl: '',
    siteOfficialResourcesUrl: '',
    siteFastModel: '',
    siteAssistantModel: '',
    // Court details save: siteDirty means the fields differ from
    // siteBaseline (the values as loaded), siteClean is its inverse
    // (drives the button's aria-disabled binding — the CSP Alpine build
    // can't negate inline), and siteStatus feeds the aria-live region.
    siteBaseline: {},
    siteDirty: false,
    siteClean: true,
    siteStatus: '',
    siteStatusClass: 'text-greyscale-500',
    // Models auto-save status (aria-live region in the section heading).
    modelsStatus: '',
    modelsStatusClass: 'text-greyscale-500',
    // Content library (right sidebar). The modal serves three modes:
    // 'apply' (full configuration) and 'contact'/'resource' (single-row
    // overwrite when a + button hits a naming conflict).
    library: [],
    libraryExpandedSlug: null,
    // Topic library (knowledge tab sidebar); keys are court/topic.
    topicLibrary: [],
    topicLibraryExpandedKey: null,
    // Row keys (slug:kind:index) whose + button briefly shows a check.
    libraryAddedFlashes: {},
    libraryModalOpen: false,
    libraryModalMode: null,
    libraryModalTitle: '',
    libraryModalIntro: '',
    // [{heading, items}] cards enumerating what an apply overwrites.
    libraryModalSections: [],
    libraryModalNote: '',
    libraryModalConfirmLabel: 'Apply',
    // Prune option (apply mode only): delete rows outside the config.
    libraryModalShowPrune: false,
    libraryModalPrune: false,
    libraryModalDeleteSections: [],
    libraryModalDeleteEmpty: false,
    libraryModalHasOverwrites: false,
    libraryModalHasDeletes: false,
    libraryModalSlug: null,
    libraryModalTargetId: null,
    libraryModalPayload: null,
    // Topic/flow apply targets (knowledge tab library modes).
    libraryModalTopicCourt: null,
    libraryModalTopicSlug: null,
    libraryModalFlowSlug: null,
    libraryError: '',
    // Settings tab — contacts
    contacts: [],
    contactEditorVisible: false,
    contactEditorTitle: '',
    contactEditingId: null,
    contactConfirmingId: null,
    contactName: '',
    contactPhone: '',
    contactEmail: '',
    contactUrl: '',
    contactNote: '',
    contactError: '',
    // Settings tab — resources
    resources: [],
    resourceEditorVisible: false,
    resourceEditorTitle: '',
    resourceEditingId: null,
    resourceConfirmingId: null,
    resourceLabel: '',
    resourceUrl: '',
    resourceNote: '',
    resourceError: '',
    // Knowledge base tab
    kbTopics: [],
    kbListVisible: true,
    kbEditorVisible: false,
    kbEditorTitle: '',
    kbEditingId: null,
    // Topic / flow delete confirmation modals
    topicDeleteModalOpen: false,
    topicDeleteId: null,
    topicDeleteTitle: '',
    topicDeleteFlowsNote: '',
    flowDeleteModalOpen: false,
    flowDeleteTitle: '',
    kbTitle: '',
    kbSubtitle: '',
    kbDescription: '',
    kbIcon: '',
    kbMetaDescription: '',
    kbPrompts: '',
    kbError: '',
    // The topic list's scroll offset, restored when a subview closes.
    kbListScrollTop: 0,
    // Flow viewer/editor (center of the knowledge tab)
    kbFlowVisible: false,
    // Right-rail occupant on the knowledge tab: the topic library on the
    // list/editor views, the interview builder while a flow is open.
    railKbLibrary: false,
    railKbBuilder: false,
    railHeadLibrary: true,
    // Interview builder (right rail while a flow is open)
    builderGroups: [],
    builderIntro: '',
    builderGroupEditorVisible: false,
    builderGroupEditorTitle: '',
    builderGroupEditingId: null,
    builderGroupTitle: '',
    builderGroupDescription: '',
    builderGroupError: '',
    builderFieldEditorVisible: false,
    builderFieldEditorTitle: '',
    builderFieldEditingId: null,
    builderFieldGroupId: null,
    builderFieldName: '',
    builderFieldLabel: '',
    builderFieldHelpText: '',
    builderFieldRequired: false,
    builderFieldDataType: 'text',
    builderFieldIsChoice: false,
    builderFieldChoicesText: '',
    builderFieldDefault: '',
    builderFieldError: '',
    builderFieldTypeOptions: [],
    builderFieldShowGroupSelect: false,
    builderFieldGroupOptions: [],
    builderFieldTargetGroupId: null,
    builderDeleteModalOpen: false,
    builderDeleteTitle: '',
    builderDeleteIsGroup: false,
    builderDeleteIsField: false,
    builderDeleteTargetId: null,
    flowEditing: false,
    flowNotEditing: true,
    // Read-view content truncation ("show more" fade)
    flowContentExpanded: false,
    flowContentCollapsible: false,
    flowContentCollapsed: false,
    flowContentClass: '',
    flowContentToggleLabel: 'Show more',
    flowId: null,
    // Read-view name/slug inline form
    flowMetaName: '',
    flowMetaSlug: '',
    flowMetaError: '',
    // Deadline editor modal (read-view rows)
    flowDeadlineEditorVisible: false,
    flowDeadlineEditorTitle: '',
    flowDeadlineEditingId: null,
    flowDeadlineLabel: '',
    flowDeadlineOffsetDays: '0',
    flowDeadlineOffsetFrom: '',
    flowDeadlineDescription: '',
    flowDeadlineError: '',
    flowDeadlineConfirmingId: null,
    flowDeadlineFieldOptions: [],
    flowDeadlineHasDateFields: false,
    flowDeadlineNoDateFields: true,
    // Link editor modal (read-view rows)
    flowLinkEditorVisible: false,
    flowLinkEditorTitle: '',
    flowLinkEditingId: null,
    flowLinkName: '',
    flowLinkUrl: '',
    flowLinkError: '',
    flowLinkConfirmingId: null,
    // Form editor modal (read-view rows; file upload on create only)
    flowFormEditorVisible: false,
    flowFormEditorTitle: '',
    flowFormEditingId: null,
    flowFormRowName: '',
    flowFormRowError: '',
    flowFormEditorCreating: false,
    flowFormEditorEditing: false,
    flowFormPreviewUrl: '',
    // Create-flow modal
    flowCreateOpen: false,
    flowCreateTopicId: null,
    flowCreateName: '',
    flowCreateSlug: '',
    flowCreateError: '',
    flowName: '',
    flowContext: '',
    flowSections: [],
    flowFields: [],
    flowLinks: [],
    flowDeadlines: [],
    flowForms: [],
    flowNoSections: false,
    flowError: '',
    flowUid: 0,
    flowFormConfirmingId: null,
    flowFormsExpandedIds: [],
    // Header title and the content save-bar's dirty tracking: flowDirty
    // compares a serialized snapshot against the baseline taken when
    // editing starts; flowClean drives the aria-disabled binding.
    flowTitle: '',
    flowDirty: false,
    flowClean: true,
    flowBaseline: '',
    // Users tab
    users: [],
    usersQuery: '',
    usersPage: 1,
    usersNumPages: 1,
    usersEmpty: false,
    usersNoPrev: true,
    usersNoNext: true,
    usersPageLabel: '',
    usersCountLabel: '',
    usersFetchSeq: 0,

    init() {
      this.loadSite()
      this.loadUsers()
      this.loadTopics()
      this.loadContacts()
      this.loadResources()
      this.loadLibrary()
      this.loadTopicLibrary()
    },

    // Click handler for a sidebar tab — the tab id rides on the element.
    selectTab(e) {
      this.applyTab(e.currentTarget.dataset.tab)
    },

    applyTab(tab) {
      this.activeTab = tab
      for (const id of ADMIN_TABS) {
        this.tabActive[id] = id === tab
      }
      this.showSettings = tab === 'settings'
      this.showUsers = tab === 'users'
      this.showKnowledge = tab === 'knowledge'
      this.showSimulate = tab === 'simulate'
      this.railActive = tab === 'settings' || tab === 'knowledge'
      // Selecting a tab (usually from the nav drawer) dismisses drawers.
      this.navOpen = false
      this.libraryOpen = false
      // Any tab selection lands the knowledge tab back on its topic list.
      this.kbListVisible = true
      this.kbEditorVisible = false
      this.kbFlowVisible = false
      this.flowEditing = false
      this.flowNotEditing = true
      this.refreshKbRail()
    },

    openNav() {
      this.navOpen = true
    },

    closeNav() {
      this.navOpen = false
    },

    openLibrary() {
      this.libraryOpen = true
    },

    closeLibrary() {
      this.libraryOpen = false
    },

    // --- Site settings ---

    async loadSite() {
      try {
        const res = await fetch('/api/admin/site/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const site = await res.json()
        this.siteCourtName = site.court_name || ''
        this.siteJurisdictionLevel = site.jurisdiction_level || ''
        this.siteState = site.state || ''
        this.siteOfficialUrl = site.official_url || ''
        this.siteOfficialResourcesUrl = site.official_resources_url || ''
        this.siteFastModel = site.fast_model || ''
        this.siteAssistantModel = site.assistant_model || ''
        this.captureSiteBaseline()
      } catch (e) {
        console.error('Failed to load site settings:', e)
      }
    },

    // Input handler for every settings field — the target property name
    // rides on the element's data-field attribute.
    updateSiteField(e) {
      this[e.currentTarget.dataset.field] = e.currentTarget.value
      this.refreshSiteDirty()
    },

    // Snapshot the current field values as the clean reference point.
    captureSiteBaseline() {
      this.siteBaseline = {}
      for (const field of SITE_FIELDS) {
        this.siteBaseline[field] = this[field]
      }
      this.refreshSiteDirty()
    },

    // Dirty = any field differs from the baseline, so an edit that is
    // typed and then undone counts as no change.
    refreshSiteDirty() {
      this.siteDirty = SITE_FIELDS.some(
        (field) => this[field] !== this.siteBaseline[field]
      )
      this.siteClean = !this.siteDirty
      this.siteStatus = this.siteDirty ? 'Unsaved changes' : ''
      this.siteStatusClass = 'text-greyscale-500'
    },

    async saveCourtDetails() {
      if (!this.siteDirty) return
      try {
        const body = new FormData()
        body.append('court_name', this.siteCourtName.trim())
        body.append('jurisdiction_level', this.siteJurisdictionLevel)
        body.append('state', this.siteState.trim().toUpperCase())
        body.append('official_url', this.siteOfficialUrl.trim())
        body.append(
          'official_resources_url',
          this.siteOfficialResourcesUrl.trim()
        )
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/site/court-details/', {
          method: 'POST',
          body,
        })
        if (!res.ok) {
          // Surface the server's validation message next to Save.
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        // loadSite resets the button to clean; Saved goes on top.
        await this.loadSite()
        this.siteStatus = 'Saved'
        this.siteStatusClass = 'text-green-600'
      } catch (e) {
        console.error('Failed to save court details:', e)
        this.siteStatus = e.message
        this.siteStatusClass = 'text-red-600'
      }
    },

    // Change handler for a model select — applies the value and saves
    // immediately.
    async updateSiteModel(e) {
      this[e.currentTarget.dataset.field] = e.currentTarget.value
      try {
        const body = new FormData()
        body.append('fast_model', this.siteFastModel)
        body.append('assistant_model', this.siteAssistantModel)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/site/models/', {
          method: 'POST',
          body,
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        this.modelsStatus = 'Saved'
        this.modelsStatusClass = 'text-green-600'
      } catch (err) {
        console.error('Failed to save model selection:', err)
        this.modelsStatus = err.message
        this.modelsStatusClass = 'text-red-600'
      }
    },

    csrfToken() {
      const input = document.querySelector('[name=csrfmiddlewaretoken]')
      return input ? input.value : ''
    },

    // Generic input handler — the target property rides on data-field.
    updateField(e) {
      this[e.currentTarget.dataset.field] = e.currentTarget.value
    },

    // --- Content library ---

    async loadLibrary() {
      try {
        const res = await fetch('/api/admin/library/courts/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.library = (data.courts || []).map((c) =>
          this.decorateLibraryEntry(c)
        )
      } catch (e) {
        console.error('Failed to load content library:', e)
      }
    },

    // Precompute CSP-safe bindings for a library card.
    decorateLibraryEntry(entry) {
      const expanded = entry.slug === this.libraryExpandedSlug
      const courtLines = [
        entry.court_name,
        [entry.jurisdiction_level, entry.state].filter(Boolean).join(' · '),
        entry.official_url,
        entry.official_resources_url,
      ].filter(Boolean)
      const contacts = entry.contacts.length
      const resources = entry.resources.length
      const flashed = (kind, index) =>
        !!this.libraryAddedFlashes[entry.slug + ':' + kind + ':' + index]
      return {
        ...entry,
        contacts: entry.contacts.map((c, i) => ({
          ...c,
          added: flashed('contact', i),
          notAdded: !flashed('contact', i),
        })),
        resources: entry.resources.map((r, i) => ({
          ...r,
          added: flashed('resource', i),
          notAdded: !flashed('resource', i),
        })),
        expanded,
        collapsed: !expanded,
        summary:
          contacts +
          (contacts === 1 ? ' contact · ' : ' contacts · ') +
          resources +
          (resources === 1 ? ' resource' : ' resources'),
        courtText: courtLines.join('\n') || '—',
        hasContacts: contacts > 0,
        contactsHeading: 'Contacts (' + contacts + ')',
        hasResources: resources > 0,
        resourcesHeading: 'Resources (' + resources + ')',
      }
    },

    redecorateLibrary() {
      this.library = this.library.map((e) => this.decorateLibraryEntry(e))
    },

    // Briefly swap a + button's icon for a check so a click that opened
    // no modal (added, or already identical) still visibly lands.
    flashLibraryAdded(slug, kind, index) {
      const key = slug + ':' + kind + ':' + index
      this.libraryAddedFlashes[key] = true
      this.redecorateLibrary()
      this.redecorateTopicLibrary()
      setTimeout(() => {
        delete this.libraryAddedFlashes[key]
        this.redecorateLibrary()
        this.redecorateTopicLibrary()
      }, 1500)
    },

    // Expand/collapse the card whose slug rides on the element.
    toggleLibraryEntry(e) {
      const slug = e.currentTarget.dataset.librarySlug
      this.libraryExpandedSlug = this.libraryExpandedSlug === slug ? null : slug
      this.redecorateLibrary()
    },

    // JSON POST helper for library adds/overwrites; throws with the
    // server's validation message on failure.
    async libraryPost(url, payload) {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken(),
        },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || 'Request failed: ' + res.status)
      }
    },

    // --- Topic library (knowledge tab sidebar) ---

    async loadTopicLibrary() {
      try {
        const res = await fetch('/api/admin/library/topics/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.topicLibrary = (data.topics || []).map((t) =>
          this.decorateTopicLibraryEntry(t)
        )
      } catch (e) {
        console.error('Failed to load topic library:', e)
      }
    },

    // Precompute CSP-safe bindings for a topic library card.
    decorateTopicLibraryEntry(entry) {
      const key = entry.court_slug + '/' + entry.slug
      const expanded = key === this.topicLibraryExpandedKey
      const flows = entry.flows.length
      const prompts = (entry.prompts || []).length
      const metaLines = [
        entry.subtitle,
        entry.description,
        entry.icon && 'Icon: ' + entry.icon,
        prompts && prompts + (prompts === 1 ? ' prompt' : ' prompts'),
      ].filter(Boolean)
      return {
        ...entry,
        key,
        expanded,
        collapsed: !expanded,
        summary:
          entry.court_name + ' · ' + flows + (flows === 1 ? ' flow' : ' flows'),
        metaText: metaLines.join('\n') || '—',
        hasFlows: flows > 0,
        flowsHeading: 'Flows (' + flows + ')',
        flows: entry.flows.map((f, i) => ({
          ...f,
          label:
            f.slug +
            ' · ' +
            f.name +
            ((f.forms || []).length
              ? ' · ' +
                f.forms.length +
                (f.forms.length === 1 ? ' form' : ' forms')
              : ''),
          added: !!this.libraryAddedFlashes[key + ':flow:' + i],
          notAdded: !this.libraryAddedFlashes[key + ':flow:' + i],
        })),
      }
    },

    redecorateTopicLibrary() {
      this.topicLibrary = this.topicLibrary.map((t) =>
        this.decorateTopicLibraryEntry(t)
      )
    },

    toggleTopicLibraryEntry(e) {
      const key = e.currentTarget.dataset.topicKey
      this.topicLibraryExpandedKey =
        this.topicLibraryExpandedKey === key ? null : key
      this.redecorateTopicLibrary()
    },

    // Labels of topic fields that are non-blank now and differ from the
    // library version — the "will be overwritten" list.
    topicDiffLabels(existing, entry) {
      const labels = [
        ['Title', existing.title, entry.title],
        ['Subtitle', existing.subtitle, entry.subtitle],
        ['Card description', existing.description, entry.description],
        ['Icon', existing.icon, entry.icon],
        ['Meta description', existing.meta_description, entry.meta_description],
      ]
        .filter(([, current, next]) => {
          const value = (current || '').trim()
          return value && value !== (next || '').trim()
        })
        .map(([label]) => label)
      if (
        (existing.prompts || []).length &&
        JSON.stringify(existing.prompts) !== JSON.stringify(entry.prompts || [])
      ) {
        labels.push('Prompts')
      }
      return labels
    },

    // True when an existing flow's contents match the library flow.
    // Forms compare by slug/name/mappings — PDF bytes aren't comparable.
    sameFlowConfig(existing, row) {
      const norm = (v) => (v || '').trim()
      const packField = (f) => [
        norm(f.name),
        norm(f.label),
        norm(f.data_type) || 'text',
        !!f.required,
        norm(f.help_text),
        norm(f.default),
        (f.choices || []).map((c) => [norm(c.value), norm(c.label)]),
      ]
      const pack = (flow) =>
        JSON.stringify({
          name: norm(flow.name),
          sections: (flow.sections || []).map((s) => [
            norm(s.heading),
            norm(s.content),
          ]),
          field_groups: (flow.field_groups || []).map((g) => [
            norm(g.title),
            norm(g.description),
            (g.fields || []).map(packField),
          ]),
          links: (flow.links || []).map((li) => [norm(li.name), norm(li.url)]),
          deadlines: (flow.deadlines || []).map((d) => [
            norm(d.label),
            norm(d.description),
            Number(d.offset_days) || 0,
            norm(d.offset_from),
          ]),
          forms: (flow.forms || []).map((f) => [
            norm(f.slug),
            norm(f.name),
            (f.mappings || []).map((m) => [
              norm(m.pdf_field),
              norm(m.template),
              norm(m.checked_when),
            ]),
          ]),
        })
      return pack(existing) === pack(row)
    },

    // Add a single library flow — the card key and index ride on the
    // button. A conflict with different contents opens the overwrite
    // modal; an identical flow is a no-op. A missing topic is created.
    async addLibraryFlow(e) {
      const index = e.currentTarget.dataset.index
      const entry = this.topicLibrary.find(
        (t) => t.key === e.currentTarget.dataset.topicKey
      )
      const flow = entry && entry.flows[index]
      if (!flow) return
      const topic = this.kbTopics.find((t) => t.slug === entry.slug)
      const existing = topic && topic.flows.find((f) => f.slug === flow.slug)
      if (existing) {
        if (this.sameFlowConfig(existing, flow)) {
          this.flashLibraryAdded(entry.key, 'flow', index)
          return
        }
        this.libraryModalMode = 'flow'
        this.libraryModalTopicCourt = entry.court_slug
        this.libraryModalTopicSlug = entry.slug
        this.libraryModalFlowSlug = flow.slug
        this.libraryModalTitle = 'Overwrite flow?'
        this.libraryModalIntro =
          'A flow "' +
          flow.slug +
          '" already exists on ' +
          topic.title +
          '. It will be replaced with the library version.'
        this.libraryModalSections = []
        this.libraryModalNote = ''
        this.libraryModalShowPrune = false
        this.libraryModalPrune = false
        this.libraryModalConfirmLabel = 'Overwrite'
        this.libraryError = ''
        this.libraryModalOpen = true
        return
      }
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/library/topics/' +
            entry.court_slug +
            '/' +
            entry.slug +
            '/flows/' +
            flow.slug +
            '/apply/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await this.loadTopics()
        this.flashLibraryAdded(entry.key, 'flow', index)
      } catch (err) {
        console.error('Failed to add library flow:', err)
      }
    },

    askApplyTopicLibrary(e) {
      const entry = this.topicLibrary.find(
        (t) => t.key === e.currentTarget.dataset.topicKey
      )
      if (!entry) return
      const topic = this.kbTopics.find((t) => t.slug === entry.slug)
      const sections = []
      if (topic) {
        const labels = this.topicDiffLabels(topic, entry)
        if (labels.length) {
          sections.push({ heading: 'Topic settings', items: labels })
        }
        const flowHits = entry.flows
          .filter((f) => {
            const existing = topic.flows.find((x) => x.slug === f.slug)
            return existing && !this.sameFlowConfig(existing, f)
          })
          .map((f) => f.slug + ' · ' + f.name)
        if (flowHits.length) {
          sections.push({
            heading: 'Flows to overwrite (' + flowHits.length + ')',
            items: flowHits,
          })
        }
      }
      this.libraryModalMode = 'topic'
      this.libraryModalTopicCourt = entry.court_slug
      this.libraryModalTopicSlug = entry.slug
      this.libraryModalTitle = 'Apply ' + entry.title + '?'
      this.libraryModalSections = sections
      this.libraryModalIntro = sections.length
        ? 'Applying will overwrite the following with the library version:'
        : topic
          ? 'Nothing conflicts with your current knowledge base. The topic settings and flows will be applied.'
          : 'The topic and its flows will be added to your knowledge base.'
      this.libraryModalNote = sections.length
        ? 'Everything else will be added.'
        : ''
      this.libraryModalShowPrune = false
      this.libraryModalPrune = false
      this.libraryModalHasOverwrites = sections.length > 0
      this.libraryModalHasDeletes = false
      this.updateLibraryConfirmLabel()
      this.libraryError = ''
      this.libraryModalOpen = true
    },

    // True when the existing row's contents already match the library row
    // field-for-field — applying it would change nothing.
    sameContact(existing, row) {
      return ['phone', 'email', 'url', 'note'].every(
        (field) => (existing[field] || '') === (row[field] || '')
      )
    },

    sameResource(existing, row) {
      return ['url', 'note'].every(
        (field) => (existing[field] || '') === (row[field] || '')
      )
    },

    // Add a single library contact — the row's slug and index ride on the
    // button. A conflict with different contents opens the overwrite
    // modal; an identical row is a no-op.
    async addLibraryContact(e) {
      const index = e.currentTarget.dataset.index
      const entry = this.library.find(
        (c) => c.slug === e.currentTarget.dataset.librarySlug
      )
      const contact = entry && entry.contacts[index]
      if (!contact) return
      const existing = this.contacts.find((c) => c.name === contact.name)
      if (existing) {
        if (this.sameContact(existing, contact)) {
          this.flashLibraryAdded(entry.slug, 'contact', index)
          return
        }
        this.libraryModalMode = 'contact'
        this.libraryModalTargetId = existing.id
        this.libraryModalPayload = contact
        this.libraryModalTitle = 'Overwrite contact?'
        this.libraryModalIntro =
          'A contact named "' +
          contact.name +
          '" already exists. It will be replaced with the library version.'
        this.libraryModalSections = []
        this.libraryModalNote = ''
        this.libraryModalShowPrune = false
        this.libraryModalPrune = false
        this.libraryModalConfirmLabel = 'Overwrite'
        this.libraryError = ''
        this.libraryModalOpen = true
        return
      }
      try {
        await this.libraryPost('/api/admin/contacts/create/', contact)
        await this.loadContacts()
        this.flashLibraryAdded(entry.slug, 'contact', index)
      } catch (err) {
        console.error('Failed to add library contact:', err)
      }
    },

    // Same for a single library resource.
    async addLibraryResource(e) {
      const index = e.currentTarget.dataset.index
      const entry = this.library.find(
        (c) => c.slug === e.currentTarget.dataset.librarySlug
      )
      const resource = entry && entry.resources[index]
      if (!resource) return
      const existing = this.resources.find((r) => r.label === resource.label)
      if (existing) {
        if (this.sameResource(existing, resource)) {
          this.flashLibraryAdded(entry.slug, 'resource', index)
          return
        }
        this.libraryModalMode = 'resource'
        this.libraryModalTargetId = existing.id
        this.libraryModalPayload = resource
        this.libraryModalTitle = 'Overwrite resource?'
        this.libraryModalIntro =
          'A resource labeled "' +
          resource.label +
          '" already exists. It will be replaced with the library version.'
        this.libraryModalSections = []
        this.libraryModalNote = ''
        this.libraryModalShowPrune = false
        this.libraryModalPrune = false
        this.libraryModalConfirmLabel = 'Overwrite'
        this.libraryError = ''
        this.libraryModalOpen = true
        return
      }
      try {
        await this.libraryPost('/api/admin/resources/create/', resource)
        await this.loadResources()
        this.flashLibraryAdded(entry.slug, 'resource', index)
      } catch (err) {
        console.error('Failed to add library resource:', err)
      }
    },

    askApplyLibrary(e) {
      const entry = this.library.find(
        (c) => c.slug === e.currentTarget.dataset.librarySlug
      )
      if (!entry) return
      // Enumerate exactly what an apply would overwrite: court detail
      // fields and conflicting contacts/resources, but only where the
      // current value actually differs from the library version.
      const filled = [
        ['Court name', this.siteCourtName, entry.court_name],
        [
          'Jurisdiction level',
          this.siteJurisdictionLevel,
          entry.jurisdiction_level,
        ],
        ['State', this.siteState, entry.state],
        ['Official URL', this.siteOfficialUrl, entry.official_url],
        [
          'Official resources URL',
          this.siteOfficialResourcesUrl,
          entry.official_resources_url,
        ],
      ]
        .filter(([, current, next]) => {
          const value = (current || '').trim()
          return value && value !== (next || '').trim()
        })
        .map(([label]) => label)
      const contactHits = entry.contacts
        .filter((c) => {
          const existing = this.contacts.find((x) => x.name === c.name)
          return existing && !this.sameContact(existing, c)
        })
        .map((c) => c.name)
      const resourceHits = entry.resources
        .filter((r) => {
          const existing = this.resources.find((x) => x.label === r.label)
          return existing && !this.sameResource(existing, r)
        })
        .map((r) => r.label)
      const sections = []
      if (filled.length) {
        sections.push({ heading: 'Court details', items: filled })
      }
      if (contactHits.length) {
        sections.push({
          heading: 'Contacts (' + contactHits.length + ')',
          items: contactHits,
        })
      }
      if (resourceHits.length) {
        sections.push({
          heading: 'Resources (' + resourceHits.length + ')',
          items: resourceHits,
        })
      }
      // Site rows outside the config — deleted if the prune box is checked.
      const extraContacts = this.contacts
        .filter((c) => !entry.contacts.some((x) => x.name === c.name))
        .map((c) => c.name)
      const extraResources = this.resources
        .filter((r) => !entry.resources.some((x) => x.label === r.label))
        .map((r) => r.label)
      const deleteSections = []
      if (extraContacts.length) {
        deleteSections.push({
          heading: 'Contacts to delete (' + extraContacts.length + ')',
          items: extraContacts,
        })
      }
      if (extraResources.length) {
        deleteSections.push({
          heading: 'Resources to delete (' + extraResources.length + ')',
          items: extraResources,
        })
      }
      this.libraryModalMode = 'apply'
      this.libraryModalSlug = entry.slug
      this.libraryModalTitle = 'Apply ' + entry.name + '?'
      this.libraryModalSections = sections
      this.libraryModalIntro = sections.length
        ? 'Applying will overwrite the following with the library version:'
        : 'Nothing conflicts with your current settings. Court details will be set, and the contacts and resources added.'
      this.libraryModalNote = sections.length
        ? 'Everything else will be added.'
        : ''
      this.libraryModalShowPrune = true
      this.libraryModalPrune = false
      this.libraryModalDeleteSections = deleteSections
      this.libraryModalDeleteEmpty = deleteSections.length === 0
      this.libraryModalHasOverwrites = sections.length > 0
      this.libraryModalHasDeletes = deleteSections.length > 0
      this.updateLibraryConfirmLabel()
      this.libraryError = ''
      this.libraryModalOpen = true
    },

    // The confirm button says Overwrite whenever the apply would destroy
    // something: an overwrite, or a checked prune with rows to delete.
    updateLibraryConfirmLabel() {
      const destructive =
        this.libraryModalHasOverwrites ||
        (this.libraryModalPrune && this.libraryModalHasDeletes)
      this.libraryModalConfirmLabel = destructive ? 'Overwrite' : 'Apply'
    },

    toggleLibraryPrune(e) {
      this.libraryModalPrune = e.currentTarget.checked
      this.updateLibraryConfirmLabel()
    },

    cancelApplyLibrary() {
      this.libraryModalOpen = false
    },

    async confirmApplyLibrary() {
      try {
        if (this.libraryModalMode === 'apply') {
          if (!this.libraryModalSlug) return
          const body = new FormData()
          body.append('prune', this.libraryModalPrune ? 'true' : 'false')
          body.append('csrfmiddlewaretoken', this.csrfToken())
          const res = await fetch(
            '/api/admin/library/courts/' + this.libraryModalSlug + '/apply/',
            { method: 'POST', body }
          )
          if (!res.ok) {
            const data = await res.json().catch(() => ({}))
            throw new Error(data.error || 'Request failed: ' + res.status)
          }
          // The apply touched the site's court fields, contacts, and
          // resources — refresh everything the settings tab shows.
          await this.loadSite()
          await this.loadContacts()
          await this.loadResources()
        } else if (this.libraryModalMode === 'contact') {
          await this.libraryPost(
            '/api/admin/contacts/' + this.libraryModalTargetId + '/update/',
            this.libraryModalPayload
          )
          await this.loadContacts()
        } else if (this.libraryModalMode === 'resource') {
          await this.libraryPost(
            '/api/admin/resources/' + this.libraryModalTargetId + '/update/',
            this.libraryModalPayload
          )
          await this.loadResources()
        } else if (this.libraryModalMode === 'topic') {
          const body = new FormData()
          body.append('csrfmiddlewaretoken', this.csrfToken())
          const res = await fetch(
            '/api/admin/library/topics/' +
              this.libraryModalTopicCourt +
              '/' +
              this.libraryModalTopicSlug +
              '/apply/',
            { method: 'POST', body }
          )
          if (!res.ok) {
            const data = await res.json().catch(() => ({}))
            throw new Error(data.error || 'Request failed: ' + res.status)
          }
          await this.loadTopics()
        } else if (this.libraryModalMode === 'flow') {
          const body = new FormData()
          body.append('csrfmiddlewaretoken', this.csrfToken())
          const res = await fetch(
            '/api/admin/library/topics/' +
              this.libraryModalTopicCourt +
              '/' +
              this.libraryModalTopicSlug +
              '/flows/' +
              this.libraryModalFlowSlug +
              '/apply/',
            { method: 'POST', body }
          )
          if (!res.ok) {
            const data = await res.json().catch(() => ({}))
            throw new Error(data.error || 'Request failed: ' + res.status)
          }
          await this.loadTopics()
        }
        this.libraryModalOpen = false
      } catch (e) {
        console.error('Failed to apply library content:', e)
        this.libraryError = e.message
      }
    },

    // --- Contacts ---

    async loadContacts() {
      try {
        const res = await fetch('/api/admin/contacts/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.contactConfirmingId = null
        this.contacts = this.decorateContacts(data.contacts || [])
      } catch (e) {
        console.error('Failed to load contacts:', e)
      }
    },

    // Precompute CSP-safe bindings for a contact row.
    decorateContact(c, index, total) {
      return {
        ...c,
        detail: [c.phone, c.email, c.url].filter(Boolean).join(' · '),
        confirmingDelete: c.id === this.contactConfirmingId,
        notConfirmingDelete: c.id !== this.contactConfirmingId,
        moveUpDisabled: index === 0,
        moveDownDisabled: index === total - 1,
      }
    },

    decorateContacts(contacts) {
      return contacts.map((c, i) => this.decorateContact(c, i, contacts.length))
    },

    redecorateContacts() {
      this.contacts = this.decorateContacts(this.contacts)
    },

    // Reorder handler — id and direction ride on the button. Swap locally
    // first, then replace with the server's ordered list.
    async moveContact(e) {
      const contactId = e.currentTarget.dataset.contactId
      const direction = e.currentTarget.dataset.direction
      this.contacts = this.decorateContacts(
        swapRow(this.contacts, contactId, direction)
      )
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/contacts/' + contactId + '/move/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.contacts = this.decorateContacts(data.contacts || [])
      } catch (err) {
        console.error('Failed to move contact:', err)
        await this.loadContacts()
      }
    },

    // Open the editor for the row whose id rides on the element.
    editContact(e) {
      const contact = this.contacts.find(
        (c) => c.id === e.currentTarget.dataset.contactId
      )
      if (!contact) return
      this.contactEditingId = contact.id
      this.contactName = contact.name
      this.contactPhone = contact.phone
      this.contactEmail = contact.email
      this.contactUrl = contact.url
      this.contactNote = contact.note
      this.openContactEditor('Edit contact')
    },

    newContact() {
      this.contactEditingId = null
      this.contactName = ''
      this.contactPhone = ''
      this.contactEmail = ''
      this.contactUrl = ''
      this.contactNote = ''
      this.openContactEditor('New contact')
    },

    openContactEditor(title) {
      this.contactEditorTitle = title
      this.contactError = ''
      this.contactEditorVisible = true
    },

    cancelContactEdit() {
      this.contactEditorVisible = false
    },

    async saveContact() {
      if (!this.contactName.trim()) {
        this.contactError = 'Name is required'
        return
      }
      const url = this.contactEditingId
        ? '/api/admin/contacts/' + this.contactEditingId + '/update/'
        : '/api/admin/contacts/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            name: this.contactName,
            phone: this.contactPhone,
            email: this.contactEmail,
            url: this.contactUrl,
            note: this.contactNote,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.loadContacts()
        this.cancelContactEdit()
      } catch (e) {
        console.error('Failed to save contact:', e)
        this.contactError = e.message
      }
    },

    askDeleteContact(e) {
      this.contactConfirmingId = e.currentTarget.dataset.contactId
      this.redecorateContacts()
    },

    cancelDeleteContact() {
      this.contactConfirmingId = null
      this.redecorateContacts()
    },

    async confirmDeleteContact(e) {
      const contactId = e.currentTarget.dataset.contactId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/contacts/' + contactId + '/delete/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await this.loadContacts()
      } catch (err) {
        console.error('Failed to delete contact:', err)
      }
    },

    // --- Resources ---

    async loadResources() {
      try {
        const res = await fetch('/api/admin/resources/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.resourceConfirmingId = null
        this.resources = this.decorateResources(data.resources || [])
      } catch (e) {
        console.error('Failed to load resources:', e)
      }
    },

    // Precompute CSP-safe bindings for a resource row.
    decorateResource(r, index, total) {
      return {
        ...r,
        confirmingDelete: r.id === this.resourceConfirmingId,
        notConfirmingDelete: r.id !== this.resourceConfirmingId,
        moveUpDisabled: index === 0,
        moveDownDisabled: index === total - 1,
      }
    },

    decorateResources(resources) {
      return resources.map((r, i) =>
        this.decorateResource(r, i, resources.length)
      )
    },

    redecorateResources() {
      this.resources = this.decorateResources(this.resources)
    },

    // Reorder handler — id and direction ride on the button. Swap locally
    // first, then replace with the server's ordered list.
    async moveResource(e) {
      const resourceId = e.currentTarget.dataset.resourceId
      const direction = e.currentTarget.dataset.direction
      this.resources = this.decorateResources(
        swapRow(this.resources, resourceId, direction)
      )
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/resources/' + resourceId + '/move/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.resources = this.decorateResources(data.resources || [])
      } catch (err) {
        console.error('Failed to move resource:', err)
        await this.loadResources()
      }
    },

    // Open the editor for the row whose id rides on the element.
    editResource(e) {
      const resource = this.resources.find(
        (r) => r.id === e.currentTarget.dataset.resourceId
      )
      if (!resource) return
      this.resourceEditingId = resource.id
      this.resourceLabel = resource.label
      this.resourceUrl = resource.url
      this.resourceNote = resource.note
      this.openResourceEditor('Edit resource')
    },

    newResource() {
      this.resourceEditingId = null
      this.resourceLabel = ''
      this.resourceUrl = ''
      this.resourceNote = ''
      this.openResourceEditor('New resource')
    },

    openResourceEditor(title) {
      this.resourceEditorTitle = title
      this.resourceError = ''
      this.resourceEditorVisible = true
    },

    cancelResourceEdit() {
      this.resourceEditorVisible = false
    },

    async saveResource() {
      if (!this.resourceLabel.trim()) {
        this.resourceError = 'Label is required'
        return
      }
      if (!this.resourceUrl.trim()) {
        this.resourceError = 'URL is required'
        return
      }
      const url = this.resourceEditingId
        ? '/api/admin/resources/' + this.resourceEditingId + '/update/'
        : '/api/admin/resources/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            label: this.resourceLabel,
            url: this.resourceUrl,
            note: this.resourceNote,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.loadResources()
        this.cancelResourceEdit()
      } catch (e) {
        console.error('Failed to save resource:', e)
        this.resourceError = e.message
      }
    },

    askDeleteResource(e) {
      this.resourceConfirmingId = e.currentTarget.dataset.resourceId
      this.redecorateResources()
    },

    cancelDeleteResource() {
      this.resourceConfirmingId = null
      this.redecorateResources()
    },

    async confirmDeleteResource(e) {
      const resourceId = e.currentTarget.dataset.resourceId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/resources/' + resourceId + '/delete/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await this.loadResources()
      } catch (err) {
        console.error('Failed to delete resource:', err)
      }
    },

    // --- Knowledge base tab ---

    async loadTopics() {
      try {
        const res = await fetch('/api/admin/topics/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.kbTopics = this.decorateTopics(data.topics || [])
      } catch (e) {
        console.error('Failed to load topics:', e)
      }
    },

    // Precompute CSP-safe bindings for a topic card. Flow rows carry a
    // Draft/Live switch — green when the flow is live on the public site.
    decorateTopic(t, index, total) {
      return {
        ...t,
        flows: (t.flows || []).map((f) => ({
          ...f,
          statusLabel: f.enabled ? 'Live' : 'Draft',
          statusClass: f.enabled ? 'text-green-600' : 'text-greyscale-400',
          toggleClass: f.enabled ? 'bg-green-500/70' : 'bg-greyscale-300',
          knobClass: f.enabled ? 'translate-x-[19px]' : 'translate-x-[3px]',
          toggleAria: (f.enabled ? 'Disable ' : 'Enable ') + f.name,
          ariaChecked: f.enabled ? 'true' : 'false',
        })),
        hasFlows: (t.flows || []).length > 0,
        iconSvg: kbIconSvg(t.icon),
        moveUpDisabled: index === 0,
        moveDownDisabled: index === total - 1,
      }
    },

    decorateTopics(topics) {
      return topics.map((t, i) => this.decorateTopic(t, i, topics.length))
    },

    redecorateTopics() {
      this.kbTopics = this.decorateTopics(this.kbTopics)
    },

    // Reorder handler — id and direction ride on the button. The list is
    // swapped locally first so the UI responds instantly, then replaced
    // with the server's ordered list.
    async moveTopic(e) {
      const topicId = e.currentTarget.dataset.topicId
      const direction = e.currentTarget.dataset.direction
      this.kbTopics = this.decorateTopics(
        swapRow(this.kbTopics, topicId, direction)
      )
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/topics/' + topicId + '/move/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.kbTopics = this.decorateTopics(data.topics || [])
      } catch (err) {
        console.error('Failed to move topic:', err)
        await this.loadTopics()
      }
    },

    updateKbField(e) {
      this[e.currentTarget.dataset.field] = e.currentTarget.value
    },

    // Open the editor for the card whose id rides on the element.
    editTopic(e) {
      const topic = this.kbTopics.find(
        (t) => t.id === e.currentTarget.dataset.topicId
      )
      if (!topic) return
      this.kbEditingId = topic.id
      this.kbTitle = topic.title
      this.kbSubtitle = topic.subtitle
      this.kbDescription = topic.description
      this.kbIcon = KB_ICON_PATHS[topic.icon] ? topic.icon : 'home'
      this.kbMetaDescription = topic.meta_description
      this.kbPrompts = topic.prompts.join('\n')
      this.openKbEditor('Edit topic')
    },

    newTopic() {
      this.kbEditingId = null
      this.kbTitle = ''
      this.kbSubtitle = ''
      this.kbDescription = ''
      this.kbIcon = 'home'
      this.kbMetaDescription = ''
      this.kbPrompts = ''
      this.openKbEditor('New topic')
    },

    openKbEditor(title) {
      this.kbEnterSubview()
      this.kbEditorTitle = title
      this.kbError = ''
      this.kbListVisible = false
      this.kbEditorVisible = true
    },

    cancelTopicEdit() {
      this.kbEditorVisible = false
      this.kbListVisible = true
      this.kbRestoreListScroll()
    },

    async saveTopic() {
      if (!this.kbTitle.trim()) {
        this.kbError = 'Title is required'
        return
      }
      const url = this.kbEditingId
        ? '/api/admin/topics/' + this.kbEditingId + '/update/'
        : '/api/admin/topics/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            title: this.kbTitle,
            subtitle: this.kbSubtitle,
            description: this.kbDescription,
            icon: this.kbIcon,
            meta_description: this.kbMetaDescription,
            prompts: this.kbPrompts.split('\n'),
          }),
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await this.loadTopics()
        this.cancelTopicEdit()
      } catch (e) {
        console.error('Failed to save topic:', e)
        this.kbError = 'Save failed — please try again'
      }
    },

    // Topic deletion — a stern confirmation modal (it takes the topic's
    // flows down with it).
    askDeleteTopic(e) {
      const topic = this.kbTopics.find(
        (t) => t.id === e.currentTarget.dataset.topicId
      )
      if (!topic) return
      const n = topic.flows.length
      this.topicDeleteId = topic.id
      this.topicDeleteTitle = 'Delete "' + topic.title + '"?'
      this.topicDeleteFlowsNote = n
        ? 'This topic has ' +
          (n === 1 ? '1 flow' : n + ' flows') +
          ', which will be deleted with it.'
        : ''
      this.topicDeleteModalOpen = true
    },

    cancelDeleteTopic() {
      this.topicDeleteModalOpen = false
    },

    async confirmDeleteTopic() {
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/topics/' + this.topicDeleteId + '/delete/',
          {
            method: 'POST',
            body,
          }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.topicDeleteModalOpen = false
        await this.loadTopics()
      } catch (err) {
        console.error('Failed to delete topic:', err)
      }
    },

    // Flow deletion — the red button at the bottom of the flow page.
    askDeleteFlow() {
      this.flowDeleteTitle = 'Delete "' + this.flowName + '"?'
      this.flowDeleteModalOpen = true
    },

    cancelDeleteFlow() {
      this.flowDeleteModalOpen = false
    },

    async confirmDeleteFlow() {
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/flows/' + this.flowId + '/delete/',
          {
            method: 'POST',
            body,
          }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.flowDeleteModalOpen = false
        this.closeFlow()
        await this.loadTopics()
      } catch (err) {
        console.error('Failed to delete flow:', err)
      }
    },

    // The knowledge tab's views swap inside one scroll container, so the
    // scroll position must be managed by hand: subviews open at the top,
    // and the list gets its old position back on return.
    kbEnterSubview() {
      const el = document.getElementById('kb-scroll')
      this.kbListScrollTop = el ? el.scrollTop : 0
      this.$nextTick(() => {
        if (el) el.scrollTop = 0
      })
    },

    kbRestoreListScroll() {
      this.$nextTick(() => {
        const el = document.getElementById('kb-scroll')
        if (el) el.scrollTop = this.kbListScrollTop || 0
      })
    },

    // --- Flow viewer / editor ---

    // Copy a flow (by id, from the loaded topics) into the viewer state.
    loadFlowIntoState(flowId) {
      for (const topic of this.kbTopics) {
        const flow = topic.flows.find((f) => f.id === flowId)
        if (flow) {
          this.flowId = flow.id
          this.flowName = flow.name
          this.flowTitle = flow.name
          this.flowContext = topic.title + ' · ' + flow.slug
          this.flowMetaName = flow.name
          this.flowMetaSlug = flow.slug
          this.flowMetaError = ''
          this.flowSections = flow.sections.map((s) => ({
            heading: s.heading,
            content: s.content,
          }))
          // Fields are read-only here — only the deadline modal's
          // "from date field" dropdown reads them.
          this.flowFields = flow.fields.map((f) => ({
            name: f.name,
            label: f.label || '',
            data_type: f.data_type || 'text',
          }))
          this.flowLinks = flow.links.map((li) => ({
            id: li.id,
            name: li.name,
            url: li.url,
          }))
          this.flowDeadlines = (flow.deadlines || []).map((d) => ({
            id: d.id,
            label: d.label,
            description: d.description || '',
            offset_days: Number(d.offset_days) || 0,
            offset_from: d.offset_from || '',
          }))
          this.flowForms = this.flowFormRows(flow)
          this.flowFormConfirmingId = null
          this.builderIntro =
            'The interview pages that collect "' +
            flow.name +
            '" answers from litigants.'
          this.builderGroups = (flow.field_groups || []).map((g) => ({
            id: g.id,
            title: g.title || '',
            description: g.description || '',
            fields: (g.fields || []).map((f) => ({
              id: f.id,
              name: f.name,
              label: f.label || '',
              help_text: f.help_text || '',
              required: !!f.required,
              data_type: f.data_type || 'text',
              choices: f.choices || [],
              default: f.default || '',
            })),
          }))
          this.decorateFlowState()
          return true
        }
      }
      return false
    },

    // Precompute CSP-safe bindings for the flow read view's rows.
    decorateFlowState() {
      const total = this.flowSections.length
      this.flowSections = this.flowSections.map((s, i) => ({
        ...s,
        _k: s._k || ++this.flowUid,
        html: renderFlowMarkdown(s.content),
        moveUpDisabled: i === 0,
        moveDownDisabled: i === total - 1,
      }))
      const linkTotal = this.flowLinks.length
      this.flowLinks = this.flowLinks.map((li, i) => ({
        ...li,
        _k: li._k || ++this.flowUid,
        detail: li.url,
        confirmingDelete: li.id === this.flowLinkConfirmingId,
        notConfirmingDelete: li.id !== this.flowLinkConfirmingId,
        moveUpDisabled: i === 0,
        moveDownDisabled: i === linkTotal - 1,
      }))
      const deadlineTotal = this.flowDeadlines.length
      this.flowDeadlines = this.flowDeadlines.map((d, i) => {
        const days = Number(d.offset_days) || 0
        const offsetLabel =
          (days >= 0 ? '+' : '') +
          days +
          (Math.abs(days) === 1 ? ' day from ' : ' days from ') +
          (d.offset_from || '—')
        return {
          ...d,
          _k: d._k || ++this.flowUid,
          offsetLabel,
          detail: [offsetLabel, d.description].filter(Boolean).join(' · '),
          confirmingDelete: d.id === this.flowDeadlineConfirmingId,
          notConfirmingDelete: d.id !== this.flowDeadlineConfirmingId,
          moveUpDisabled: i === 0,
          moveDownDisabled: i === deadlineTotal - 1,
        }
      })
      const formTotal = this.flowForms.length
      // Every interview field name the flow collects — a mapping is only
      // "linked" if its template actually references one of these.
      const knownFields = new Set(
        (this.builderGroups || []).flatMap((g) =>
          (g.fields || []).map((f) => f.name)
        )
      )
      this.flowForms = this.flowForms.map((f, i) => {
        const mappings = (f.mappings || []).map((m) => {
          const refs = templateFieldRefs(m.template)
          const linked =
            refs.length > 0 && refs.every((r) => knownFields.has(r))
          return {
            ...m,
            _k: m._k || ++this.flowUid,
            // A mapping either writes a template into a text field or ticks a
            // checkbox; the two render as different right-hand columns.
            isCheckbox: !!m.checked_when,
            isText: !m.checked_when,
            templateDisplay: m.template || '—',
            checkedWhenDisplay: m.checked_when,
            linked,
            // Unlinked splits two ways: nothing to fill from, or a template
            // naming a field this flow no longer has (a renamed field, say).
            unlinkedEmpty: !linked && refs.length === 0,
            unlinkedUnknown: !linked && refs.length > 0,
          }
        })
        const linkedCount = mappings.filter((m) => m.linked).length
        const percent = mappings.length
          ? Math.round((linkedCount / mappings.length) * 100)
          : 0
        const expanded = this.flowFormsExpandedIds.includes(f.id)
        return {
          ...f,
          _k: f._k || ++this.flowUid,
          detail: f.file_name,
          moveUpDisabled: i === 0,
          moveDownDisabled: i === formTotal - 1,
          previewUrl: '/api/admin/forms/' + f.id + '/preview/',
          confirmingDelete: f.id === this.flowFormConfirmingId,
          notConfirmingDelete: f.id !== this.flowFormConfirmingId,
          mappings,
          hasMappings: mappings.length > 0,
          noMappings: mappings.length === 0,
          mappingExpanded: expanded,
          mappingCollapsed: !expanded,
          mappingBarStyle: 'width: ' + percent + '%',
          // Full bar goes green, a partial one amber, nothing at all grey.
          // Muted on purpose — a status bar shouldn't outshout the content.
          mappingBarClass: !mappings.length
            ? 'bg-greyscale-300'
            : percent === 100
              ? 'bg-emerald-600/60'
              : 'bg-amber-500/60',
          mappingProgressLabel: mappings.length
            ? linkedCount + '/' + mappings.length + ' linked'
            : 'No mappings',
        }
      })
      this.flowNoSections = total === 0
      // Long content starts truncated behind a fade in the read view.
      const contentLength = this.flowSections.reduce(
        (n, s) => n + (s.content || '').length,
        0
      )
      this.flowContentCollapsible = contentLength > 800 || total > 2
      this.refreshFlowContentCollapse()
      this.refreshFlowDirty()
      this.decorateBuilderState()
    },

    // Map a flow payload's forms into per-row state. Mappings ride along
    // untouched so a rename doesn't wipe them (mapping UI is being redone).
    flowFormRows(flow) {
      return (flow.forms || []).map((f) => ({
        id: f.id,
        slug: f.slug,
        name: f.name,
        file_name: f.file_name,
        mappings: (f.mappings || []).map((m) => ({
          pdf_field: m.pdf_field,
          template: m.template || '',
          checked_when: m.checked_when || '',
        })),
      }))
    },

    // The content editor's dirty check compares the sections against the
    // baseline snapshot taken when editing starts.
    flowSerialize() {
      return JSON.stringify(
        this.flowSections.map((s) => [s.heading, s.content])
      )
    },

    refreshFlowDirty() {
      this.flowDirty = this.flowSerialize() !== this.flowBaseline
      this.flowClean = !this.flowDirty
    },

    // Open the flow whose id rides on the clicked row.
    openFlow(e) {
      this.flowContentExpanded = false
      if (!this.loadFlowIntoState(e.currentTarget.dataset.flowId)) return
      this.kbEnterSubview()
      this.flowError = ''
      this.flowEditing = false
      this.flowNotEditing = true
      this.kbListVisible = false
      this.kbEditorVisible = false
      this.kbFlowVisible = true
      this.refreshKbRail()
    },

    closeFlow() {
      this.kbFlowVisible = false
      this.flowEditing = false
      this.flowNotEditing = true
      this.kbListVisible = true
      this.refreshKbRail()
      // Back-to-topics lands at the top of the list, not the old offset.
      this.$nextTick(() => {
        const el = document.getElementById('kb-scroll')
        if (el) el.scrollTop = 0
      })
    },

    // The knowledge tab's right rail swaps between the topic library and
    // the interview builder depending on whether a flow is open.
    refreshKbRail() {
      this.railKbBuilder = this.showKnowledge && this.kbFlowVisible
      this.railKbLibrary = this.showKnowledge && !this.kbFlowVisible
      this.railHeadLibrary = this.railActive && !this.railKbBuilder
    },

    // Input handler for the name/slug inputs — refreshes the header title
    // and the save bar's dirty state.
    async toggleFlowEnabled(e) {
      const flowId = e.currentTarget.dataset.flowId
      let flow = null
      for (const topic of this.kbTopics) {
        flow = topic.flows.find((f) => f.id === flowId)
        if (flow) break
      }
      if (!flow) return
      const enabled = !flow.enabled
      flow.enabled = enabled
      this.redecorateTopics()
      try {
        const res = await fetch('/api/admin/flows/' + flowId + '/enabled/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({ enabled }),
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
      } catch (err) {
        console.error('Failed to toggle flow:', err)
        flow.enabled = !enabled
        this.redecorateTopics()
      }
    },

    // Open the create-flow modal for the topic whose id rides on the
    // button. A new flow is just a name and a slug — content comes later.
    newFlow(e) {
      this.flowCreateTopicId = e.currentTarget.dataset.topicId
      this.flowCreateName = ''
      this.flowCreateSlug = ''
      this.flowCreateError = ''
      this.flowCreateOpen = true
    },

    cancelFlowCreate() {
      this.flowCreateOpen = false
    },

    async saveFlowCreate() {
      if (!this.flowCreateName.trim()) {
        this.flowCreateError = 'Name is required'
        return
      }
      if (!this.flowCreateSlug.trim()) {
        this.flowCreateError = 'Slug is required'
        return
      }
      try {
        const res = await fetch(
          '/api/admin/topics/' + this.flowCreateTopicId + '/flows/create/',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': this.csrfToken(),
            },
            body: JSON.stringify({
              slug: this.flowCreateSlug,
              name: this.flowCreateName,
              sections: [],
              fields: [],
              links: [],
              deadlines: [],
            }),
          }
        )
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        const data = await res.json()
        this.flowCreateOpen = false
        await this.loadTopics()
        // Land in the new flow so editing can start right away.
        if (this.loadFlowIntoState(data.id)) {
          this.kbEnterSubview()
          this.flowError = ''
          this.flowEditing = false
          this.flowNotEditing = true
          this.kbListVisible = false
          this.kbEditorVisible = false
          this.kbFlowVisible = true
          this.refreshKbRail()
        }
      } catch (err) {
        console.error('Failed to create flow:', err)
        this.flowCreateError = err.message
      }
    },

    // The fade under truncated read-view content, and its toggle.
    refreshFlowContentCollapse() {
      this.flowContentCollapsed =
        this.flowContentCollapsible && !this.flowContentExpanded
      this.flowContentClass = this.flowContentCollapsed
        ? 'max-h-80 overflow-hidden'
        : ''
      this.flowContentToggleLabel = this.flowContentExpanded
        ? 'Show less'
        : 'Show more'
    },

    toggleFlowContent() {
      this.flowContentExpanded = !this.flowContentExpanded
      this.refreshFlowContentCollapse()
    },

    // Open the in-place content editor (the read view's Content Edit).
    startFlowContentEdit() {
      this.flowError = ''
      this.flowEditing = true
      this.flowNotEditing = false
      // The clean reference point for the save bar's dirty check.
      this.flowBaseline = this.flowSerialize()
      this.refreshFlowDirty()
      // Size the content textareas once the edit view is visible —
      // scrollHeight is 0 while they're display:none.
      this.$nextTick(() => {
        for (const el of document.querySelectorAll('[data-flow-autosize]')) {
          autoResize(el)
        }
      })
    },

    // x-init hook for a content textarea (fires on insert/re-render).
    sizeFlowTextarea() {
      autoResize(this.$el)
    },

    cancelFlowEdit() {
      // Discard local edits by re-reading the flow from the loaded topics.
      if (!this.loadFlowIntoState(this.flowId)) {
        this.closeFlow()
        return
      }
      this.flowError = ''
      this.flowEditing = false
      this.flowNotEditing = true
    },

    async reloadFlow() {
      await this.loadTopics()
      this.loadFlowIntoState(this.flowId)
    },

    // --- Interview builder (right rail) ---

    // Precompute CSP-safe bindings for the builder's group/field cards.
    decorateBuilderState() {
      const total = this.builderGroups.length
      this.builderGroups = this.builderGroups.map((g, i) => {
        const fieldTotal = g.fields.length
        return {
          ...g,
          _k: g._k || ++this.flowUid,
          displayTitle: g.title || 'Untitled page',
          descriptionPreview:
            g.description.length > 90
              ? g.description.slice(0, 90).trimEnd() + '…'
              : g.description,
          hasDescription: !!g.description,
          moveUpDisabled: i === 0,
          moveDownDisabled: i === total - 1,
          fields: g.fields.map((f, j) => ({
            ...f,
            _k: f._k || ++this.flowUid,
            displayLabel: f.label || f.name,
            detail:
              f.name + ' · ' + f.data_type + (f.required ? ' · required' : ''),
            moveUpDisabled: j === 0,
            moveDownDisabled: j === fieldTotal - 1,
          })),
        }
      })
    },

    newBuilderGroup() {
      this.builderGroupEditingId = null
      this.builderGroupTitle = ''
      this.builderGroupDescription = ''
      this.builderGroupError = ''
      this.builderGroupEditorTitle = 'New group'
      this.builderGroupEditorVisible = true
    },

    editBuilderGroup(e) {
      const group = this.builderGroups.find(
        (g) => g.id === e.currentTarget.dataset.groupId
      )
      if (!group) return
      this.builderGroupEditingId = group.id
      this.builderGroupTitle = group.title
      this.builderGroupDescription = group.description
      this.builderGroupError = ''
      this.builderGroupEditorTitle = 'Edit group'
      this.builderGroupEditorVisible = true
    },

    cancelBuilderGroupEdit() {
      this.builderGroupEditorVisible = false
    },

    async saveBuilderGroup() {
      if (!this.builderGroupTitle.trim()) {
        this.builderGroupError = 'Title is required'
        return
      }
      const url = this.builderGroupEditingId
        ? '/api/admin/field-groups/' + this.builderGroupEditingId + '/update/'
        : '/api/admin/flows/' + this.flowId + '/field-groups/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            title: this.builderGroupTitle,
            description: this.builderGroupDescription,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.reloadFlow()
        this.builderGroupEditorVisible = false
      } catch (e) {
        console.error('Failed to save group:', e)
        this.builderGroupError = e.message
      }
    },

    async moveBuilderGroup(e) {
      const groupId = e.currentTarget.dataset.groupId
      const direction = e.currentTarget.dataset.direction
      this.builderGroups = swapRow(this.builderGroups, groupId, direction)
      this.decorateBuilderState()
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/field-groups/' + groupId + '/move/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
      } catch (err) {
        console.error('Failed to move group:', err)
      }
      await this.reloadFlow()
    },

    // The modal's type select offers the fixed data types with the
    // current one pre-marked (CSP-safe option flags).
    refreshBuilderFieldTypeOptions() {
      this.builderFieldTypeOptions = FIELD_DATA_TYPES.map((t) => ({
        value: t.value,
        label: t.label,
        selected: t.value === this.builderFieldDataType,
      }))
      this.builderFieldIsChoice = this.builderFieldDataType === 'choice'
    },

    updateBuilderFieldType(e) {
      this.builderFieldDataType = e.currentTarget.value
      this.builderFieldIsChoice = this.builderFieldDataType === 'choice'
    },

    updateBuilderFieldGroup(e) {
      this.builderFieldTargetGroupId = e.currentTarget.value || null
    },

    toggleBuilderFieldRequired(e) {
      this.builderFieldRequired = e.currentTarget.checked
    },

    newBuilderField(e) {
      this.builderFieldEditingId = null
      this.builderFieldGroupId = e.currentTarget.dataset.groupId
      this.builderFieldName = ''
      this.builderFieldLabel = ''
      this.builderFieldHelpText = ''
      this.builderFieldRequired = false
      this.builderFieldDataType = 'text'
      this.builderFieldChoicesText = ''
      this.builderFieldDefault = ''
      this.builderFieldError = ''
      this.refreshBuilderFieldTypeOptions()
      this.builderFieldShowGroupSelect = false
      this.builderFieldGroupOptions = []
      this.builderFieldTargetGroupId = null
      this.builderFieldEditorTitle = 'New field'
      this.builderFieldEditorVisible = true
    },

    editBuilderField(e) {
      const fieldId = e.currentTarget.dataset.fieldId
      let field = null
      let homeGroup = null
      for (const group of this.builderGroups) {
        field = group.fields.find((f) => f.id === fieldId)
        if (field) {
          homeGroup = group
          break
        }
      }
      if (!field) return
      this.builderFieldEditingId = field.id
      this.builderFieldGroupId = null
      this.builderFieldName = field.name
      this.builderFieldLabel = field.label
      this.builderFieldHelpText = field.help_text
      this.builderFieldRequired = field.required
      this.builderFieldDataType = field.data_type
      this.builderFieldChoicesText = choicesToText(field.choices)
      this.builderFieldDefault = field.default
      this.builderFieldError = ''
      this.refreshBuilderFieldTypeOptions()
      // The footer's section select re-homes the field on save. The
      // placeholder (a null target) means "keep the current group", so
      // only the other groups are offered as destinations.
      this.builderFieldTargetGroupId = null
      this.builderFieldGroupOptions = [
        { value: '', label: 'Move to section…', selected: true },
        ...this.builderGroups
          .filter((g) => g.id !== homeGroup.id)
          .map((g) => ({
            value: g.id,
            label: g.displayTitle,
            selected: false,
          })),
      ]
      this.builderFieldShowGroupSelect = this.builderGroups.length > 1
      this.builderFieldEditorTitle = 'Edit field'
      this.builderFieldEditorVisible = true
    },

    cancelBuilderFieldEdit() {
      this.builderFieldEditorVisible = false
    },

    async saveBuilderField() {
      if (!this.builderFieldName.trim()) {
        this.builderFieldError = 'Name is required'
        return
      }
      const choices =
        this.builderFieldDataType === 'choice'
          ? parseChoicesText(this.builderFieldChoicesText)
          : []
      if (this.builderFieldDataType === 'choice' && !choices.length) {
        this.builderFieldError = 'A choice field needs at least one choice'
        return
      }
      const url = this.builderFieldEditingId
        ? '/api/admin/fields/' + this.builderFieldEditingId + '/update/'
        : '/api/admin/field-groups/' +
          this.builderFieldGroupId +
          '/fields/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            name: this.builderFieldName.trim(),
            label: this.builderFieldLabel,
            help_text: this.builderFieldHelpText,
            required: this.builderFieldRequired,
            data_type: this.builderFieldDataType,
            choices,
            default: this.builderFieldDefault,
            group_id: this.builderFieldTargetGroupId,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.reloadFlow()
        this.builderFieldEditorVisible = false
      } catch (e) {
        console.error('Failed to save field:', e)
        this.builderFieldError = e.message
      }
    },

    async moveBuilderField(e) {
      const fieldId = e.currentTarget.dataset.fieldId
      const direction = e.currentTarget.dataset.direction
      this.builderGroups = this.builderGroups.map((g) =>
        g.fields.some((f) => f.id === fieldId)
          ? { ...g, fields: swapRow(g.fields, fieldId, direction) }
          : g
      )
      this.decorateBuilderState()
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/fields/' + fieldId + '/move/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
      } catch (err) {
        console.error('Failed to move field:', err)
      }
      await this.reloadFlow()
    },

    // Group/field deletion — one shared confirmation modal; deleting
    // cascades to litigants' saved answers, hence the stern warning.
    askDeleteBuilderGroup(e) {
      const groupId = e.currentTarget.dataset.groupId
      const group = this.builderGroups.find((g) => g.id === groupId)
      if (!group) return
      this.builderDeleteTargetId = groupId
      this.builderDeleteIsGroup = true
      this.builderDeleteIsField = false
      this.builderDeleteTitle = 'Delete "' + group.displayTitle + '"?'
      this.builderDeleteModalOpen = true
    },

    askDeleteBuilderField(e) {
      const fieldId = e.currentTarget.dataset.fieldId
      let field = null
      for (const group of this.builderGroups) {
        field = group.fields.find((f) => f.id === fieldId)
        if (field) break
      }
      if (!field) return
      this.builderDeleteTargetId = fieldId
      this.builderDeleteIsGroup = false
      this.builderDeleteIsField = true
      this.builderDeleteTitle = 'Delete "' + field.displayLabel + '"?'
      this.builderDeleteModalOpen = true
    },

    cancelBuilderDelete() {
      this.builderDeleteModalOpen = false
    },

    async confirmBuilderDelete() {
      const url = this.builderDeleteIsGroup
        ? '/api/admin/field-groups/' + this.builderDeleteTargetId + '/delete/'
        : '/api/admin/fields/' + this.builderDeleteTargetId + '/delete/'
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(url, { method: 'POST', body })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.builderDeleteModalOpen = false
        await this.reloadFlow()
      } catch (err) {
        console.error('Failed to delete:', err)
      }
    },

    // --- Deadline rows (read view) — mirrors the contacts editor ---

    // The modal's From-field select offers only date-typed fields, with
    // the current selection pre-marked (CSP-safe option flags).
    refreshFlowDeadlineFieldOptions(current) {
      this.flowDeadlineFieldOptions = this.flowFields
        .filter((f) => f.data_type === 'date' || f.data_type === 'datetime')
        .map((f) => ({
          value: f.name,
          label: f.label ? f.label + ' (' + f.name + ')' : f.name,
          selected: f.name === current,
        }))
      this.flowDeadlineHasDateFields = this.flowDeadlineFieldOptions.length > 0
      this.flowDeadlineNoDateFields = !this.flowDeadlineHasDateFields
    },

    newFlowDeadlineRow() {
      this.flowDeadlineEditingId = null
      this.flowDeadlineLabel = ''
      this.flowDeadlineOffsetDays = '0'
      this.flowDeadlineOffsetFrom = ''
      this.flowDeadlineDescription = ''
      this.flowDeadlineError = ''
      this.refreshFlowDeadlineFieldOptions('')
      this.flowDeadlineEditorTitle = 'New deadline'
      this.flowDeadlineEditorVisible = true
    },

    editFlowDeadlineRow(e) {
      const deadline = this.flowDeadlines.find(
        (d) => d.id === e.currentTarget.dataset.deadlineId
      )
      if (!deadline) return
      this.flowDeadlineEditingId = deadline.id
      this.flowDeadlineLabel = deadline.label
      this.flowDeadlineOffsetDays = String(deadline.offset_days)
      this.flowDeadlineOffsetFrom = deadline.offset_from
      this.flowDeadlineDescription = deadline.description
      this.flowDeadlineError = ''
      this.refreshFlowDeadlineFieldOptions(deadline.offset_from)
      this.flowDeadlineEditorTitle = 'Edit deadline'
      this.flowDeadlineEditorVisible = true
    },

    cancelFlowDeadlineRowEdit() {
      this.flowDeadlineEditorVisible = false
    },

    async saveFlowDeadlineRow() {
      if (!this.flowDeadlineLabel.trim()) {
        this.flowDeadlineError = 'Label is required'
        return
      }
      const url = this.flowDeadlineEditingId
        ? '/api/admin/deadlines/' + this.flowDeadlineEditingId + '/update/'
        : '/api/admin/flows/' + this.flowId + '/deadlines/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            label: this.flowDeadlineLabel,
            description: this.flowDeadlineDescription,
            offset_days: Number(this.flowDeadlineOffsetDays) || 0,
            offset_from: this.flowDeadlineOffsetFrom,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.reloadFlow()
        this.flowDeadlineEditorVisible = false
      } catch (e) {
        console.error('Failed to save deadline:', e)
        this.flowDeadlineError = e.message
      }
    },

    askDeleteFlowDeadlineRow(e) {
      this.flowDeadlineConfirmingId = e.currentTarget.dataset.deadlineId
      this.decorateFlowState()
    },

    cancelDeleteFlowDeadlineRow() {
      this.flowDeadlineConfirmingId = null
      this.decorateFlowState()
    },

    async confirmDeleteFlowDeadlineRow(e) {
      const deadlineId = e.currentTarget.dataset.deadlineId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/deadlines/' + deadlineId + '/delete/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.flowDeadlineConfirmingId = null
        await this.reloadFlow()
      } catch (err) {
        console.error('Failed to delete deadline:', err)
      }
    },

    async moveFlowDeadlineRow(e) {
      const deadlineId = e.currentTarget.dataset.deadlineId
      const direction = e.currentTarget.dataset.direction
      this.flowDeadlines = swapRow(this.flowDeadlines, deadlineId, direction)
      this.decorateFlowState()
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/deadlines/' + deadlineId + '/move/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
      } catch (err) {
        console.error('Failed to move deadline:', err)
      }
      await this.reloadFlow()
    },

    // --- Link rows (read view) — mirrors the contacts editor ---

    newFlowLinkRow() {
      this.flowLinkEditingId = null
      this.flowLinkName = ''
      this.flowLinkUrl = ''
      this.flowLinkError = ''
      this.flowLinkEditorTitle = 'New link'
      this.flowLinkEditorVisible = true
    },

    editFlowLinkRow(e) {
      const link = this.flowLinks.find(
        (li) => li.id === e.currentTarget.dataset.linkId
      )
      if (!link) return
      this.flowLinkEditingId = link.id
      this.flowLinkName = link.name
      this.flowLinkUrl = link.url
      this.flowLinkError = ''
      this.flowLinkEditorTitle = 'Edit link'
      this.flowLinkEditorVisible = true
    },

    cancelFlowLinkRowEdit() {
      this.flowLinkEditorVisible = false
    },

    async saveFlowLinkRow() {
      if (!this.flowLinkName.trim()) {
        this.flowLinkError = 'Name is required'
        return
      }
      const url = this.flowLinkEditingId
        ? '/api/admin/links/' + this.flowLinkEditingId + '/update/'
        : '/api/admin/flows/' + this.flowId + '/links/create/'
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken(),
          },
          body: JSON.stringify({
            name: this.flowLinkName,
            url: this.flowLinkUrl,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.reloadFlow()
        this.flowLinkEditorVisible = false
      } catch (e) {
        console.error('Failed to save link:', e)
        this.flowLinkError = e.message
      }
    },

    askDeleteFlowLinkRow(e) {
      this.flowLinkConfirmingId = e.currentTarget.dataset.linkId
      this.decorateFlowState()
    },

    cancelDeleteFlowLinkRow() {
      this.flowLinkConfirmingId = null
      this.decorateFlowState()
    },

    async confirmDeleteFlowLinkRow(e) {
      const linkId = e.currentTarget.dataset.linkId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/links/' + linkId + '/delete/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.flowLinkConfirmingId = null
        await this.reloadFlow()
      } catch (err) {
        console.error('Failed to delete link:', err)
      }
    },

    async moveFlowLinkRow(e) {
      const linkId = e.currentTarget.dataset.linkId
      const direction = e.currentTarget.dataset.direction
      this.flowLinks = swapRow(this.flowLinks, linkId, direction)
      this.decorateFlowState()
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/links/' + linkId + '/move/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
      } catch (err) {
        console.error('Failed to move link:', err)
      }
      await this.reloadFlow()
    },

    // --- Form rows (read view) — mirrors the contacts editor. Create
    // uploads a PDF; edit renames (mappings stay on the legacy editor
    // for now and ride along unchanged). Row deletes reuse the existing
    // askDeleteFlowForm/confirmDeleteFlowForm handlers. ---

    newFlowFormRow() {
      this.flowFormEditingId = null
      this.flowFormRowName = ''
      this.flowFormRowError = ''
      this.flowFormEditorCreating = true
      this.flowFormEditorEditing = false
      this.flowFormPreviewUrl = ''
      this.flowFormEditorTitle = 'New form'
      this.flowFormEditorVisible = true
      this.$nextTick(() => {
        const el = document.getElementById('flow-form-row-file')
        if (el) el.value = ''
      })
    },

    editFlowFormRow(e) {
      const form = this.flowForms.find(
        (f) => f.id === e.currentTarget.dataset.formId
      )
      if (!form) return
      this.flowFormEditingId = form.id
      this.flowFormRowName = form.name
      this.flowFormRowError = ''
      this.flowFormEditorCreating = false
      this.flowFormEditorEditing = true
      this.flowFormPreviewUrl = form.previewUrl
      this.flowFormEditorTitle = 'Edit form'
      this.flowFormEditorVisible = true
    },

    cancelFlowFormRowEdit() {
      this.flowFormEditorVisible = false
    },

    async saveFlowFormRow() {
      if (!this.flowFormRowName.trim()) {
        this.flowFormRowError = 'Name is required'
        return
      }
      try {
        let res
        if (this.flowFormEditingId) {
          const form = this.flowForms.find(
            (f) => f.id === this.flowFormEditingId
          )
          res = await fetch(
            '/api/admin/forms/' + this.flowFormEditingId + '/update/',
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken(),
              },
              body: JSON.stringify({
                name: this.flowFormRowName,
                mappings: ((form && form.mappings) || []).map((m) => ({
                  pdf_field: m.pdf_field,
                  template: m.template || '',
                  checked_when: m.checked_when || '',
                })),
              }),
            }
          )
        } else {
          const fileInput = document.getElementById('flow-form-row-file')
          const file = fileInput && fileInput.files[0]
          if (!file) {
            this.flowFormRowError = 'A PDF file is required'
            return
          }
          const body = new FormData()
          body.append('name', this.flowFormRowName.trim())
          body.append('file', file)
          body.append('csrfmiddlewaretoken', this.csrfToken())
          res = await fetch(
            '/api/admin/flows/' + this.flowId + '/forms/create/',
            { method: 'POST', body }
          )
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        await this.reloadFlow()
        this.flowFormEditorVisible = false
      } catch (e) {
        console.error('Failed to save form:', e)
        this.flowFormRowError = e.message
      }
    },

    async moveFlowFormRow(e) {
      const formId = e.currentTarget.dataset.formId
      const direction = e.currentTarget.dataset.direction
      this.flowForms = swapRow(this.flowForms, formId, direction)
      this.decorateFlowState()
      try {
        const body = new FormData()
        body.append('direction', direction)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/forms/' + formId + '/move/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
      } catch (err) {
        console.error('Failed to move form:', err)
      }
      await this.reloadFlow()
    },

    // Name/slug save — the read view's single-line form, with its own
    // endpoint. Deliberately independent of the legacy full-flow save.
    async saveFlowMeta() {
      if (!this.flowMetaName.trim()) {
        this.flowMetaError = 'Name is required'
        return
      }
      if (!this.flowMetaSlug.trim()) {
        this.flowMetaError = 'Slug is required'
        return
      }
      try {
        const res = await fetch(
          '/api/admin/flows/' + this.flowId + '/details/',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': this.csrfToken(),
            },
            body: JSON.stringify({
              name: this.flowMetaName,
              slug: this.flowMetaSlug,
            }),
          }
        )
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        const data = await res.json()
        await this.loadTopics()
        this.loadFlowIntoState(data.id)
      } catch (e) {
        console.error('Failed to save flow details:', e)
        this.flowMetaError = e.message
      }
    },

    // Save the flow's content sections to their own endpoint.
    async saveFlowContent() {
      if (!this.flowDirty) return
      try {
        const res = await fetch(
          '/api/admin/flows/' + this.flowId + '/content/',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': this.csrfToken(),
            },
            body: JSON.stringify({
              sections: this.flowSections.map((s) => ({
                heading: s.heading,
                content: s.content,
              })),
            }),
          }
        )
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        const data = await res.json()
        await this.loadTopics()
        this.loadFlowIntoState(data.id)
        this.flowError = ''
        this.flowEditing = false
        this.flowNotEditing = true
      } catch (e) {
        console.error('Failed to save flow content:', e)
        this.flowError = e.message
      }
    },

    // Input handlers — the row index and property ride on the element.
    updateFlowSection(e) {
      const row = this.flowSections[e.currentTarget.dataset.index]
      if (row) row[e.currentTarget.dataset.key] = e.currentTarget.value
      if (e.currentTarget.tagName === 'TEXTAREA') {
        autoResize(e.currentTarget)
      }
      this.refreshFlowDirty()
    },

    moveFlowSection(e) {
      const index = Number(e.currentTarget.dataset.index)
      const swap =
        e.currentTarget.dataset.direction === 'up' ? index - 1 : index + 1
      if (swap < 0 || swap >= this.flowSections.length) return
      const next = this.flowSections.slice()
      ;[next[index], next[swap]] = [next[swap], next[index]]
      this.flowSections = next
      this.decorateFlowState()
    },

    insertFlowSection(e) {
      const index = Number(e.currentTarget.dataset.index)
      this.flowSections.splice(index + 1, 0, { heading: '', content: '' })
      this.decorateFlowState()
    },

    addFlowSection() {
      this.flowSections.push({ heading: '', content: '' })
      this.decorateFlowState()
    },

    deleteFlowSection(e) {
      this.flowSections.splice(Number(e.currentTarget.dataset.index), 1)
      this.decorateFlowState()
    },

    toggleFlowFormMappings(e) {
      const formId = e.currentTarget.dataset.formId
      const open = this.flowFormsExpandedIds
      this.flowFormsExpandedIds = open.includes(formId)
        ? open.filter((id) => id !== formId)
        : [...open, formId]
      this.decorateFlowState()
    },

    askDeleteFlowForm(e) {
      this.flowFormConfirmingId = e.currentTarget.dataset.formId
      this.decorateFlowState()
    },

    cancelDeleteFlowForm() {
      this.flowFormConfirmingId = null
      this.decorateFlowState()
    },

    async confirmDeleteFlowForm(e) {
      const formId = e.currentTarget.dataset.formId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/forms/' + formId + '/delete/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.flowFormConfirmingId = null
        this.flowForms = this.flowForms.filter((f) => f.id !== formId)
        this.decorateFlowState()
        await this.loadTopics()
      } catch (err) {
        console.error('Failed to delete form:', err)
      }
    },

    searchUsers(e) {
      this.usersQuery = e.target.value.trim()
      this.usersPage = 1
      this.loadUsers()
    },

    usersPrevPage() {
      if (this.usersPage > 1) {
        this.usersPage -= 1
        this.loadUsers()
      }
    },

    usersNextPage() {
      if (this.usersPage < this.usersNumPages) {
        this.usersPage += 1
        this.loadUsers()
      }
    },

    async loadUsers() {
      // Sequence guard: a stale response (slow earlier fetch) must not
      // clobber the results of a newer one.
      const seq = ++this.usersFetchSeq
      const params = new URLSearchParams({ page: this.usersPage })
      if (this.usersQuery) params.set('q', this.usersQuery)
      try {
        const res = await fetch('/api/admin/users/?' + params, {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        if (seq !== this.usersFetchSeq) return
        this.users = (data.users || []).map((u) => this.decorateUser(u))
        this.usersPage = data.page
        this.usersNumPages = data.num_pages
        this.usersEmpty = data.total === 0
        this.usersNoPrev = data.page <= 1
        this.usersNoNext = data.page >= data.num_pages
        this.usersPageLabel = data.page + ' / ' + data.num_pages
        this.usersCountLabel =
          data.total + ' user' + (data.total === 1 ? '' : 's')
      } catch (e) {
        console.error('Failed to load users:', e)
      }
    },

    // Precompute the CSP-safe bindings for a user row's toggles.
    decorateUser(u) {
      return {
        ...u,
        notAdmin: !u.is_admin,
        notStaff: !u.is_developer,
        adminToggleClass: u.is_admin ? PILL_ON : PILL_OFF,
        devToggleClass: u.is_developer ? PILL_ON : PILL_OFF,
        // Self-revocation guard mirrors the server: you can't drop your
        // own highest permission, so those toggles render disabled.
        adminToggleDisabled: !u.can_toggle_admin,
        devToggleDisabled: !u.can_toggle_developer,
      }
    },

    // Patch one user row in place after a toggle round-trips.
    patchUser(userId, fields) {
      this.users = this.users.map((u) =>
        String(u.id) === String(userId)
          ? this.decorateUser({ ...u, ...fields })
          : u
      )
    },

    // Toggle membership (admin access).
    async toggleUserAdmin(e) {
      const userId = e.currentTarget.dataset.userId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/users/' + userId + '/admin/toggle/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.patchUser(userId, { is_admin: data.is_admin })
      } catch (err) {
        console.error('Failed to toggle admin access:', err)
      }
    },

    // Toggle the developer (staff) flag.
    async toggleUserDeveloper(e) {
      const userId = e.currentTarget.dataset.userId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/users/' + userId + '/developer/toggle/',
          { method: 'POST', body }
        )
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.patchUser(userId, { is_developer: data.is_developer })
      } catch (err) {
        console.error('Failed to toggle developer status:', err)
      }
    },
  }))
})
