// Admin dashboard — sidebar tab switching. The CSP Alpine build can't
// evaluate inline expressions, so per-tab flags are precomputed here. Tab
// styling lives in the template via data-active variants; Alpine only
// toggles the data-active attribute, so the server-rendered default
// (settings active) paints correctly before Alpine loads.
const ADMIN_TABS = ['settings', 'users', 'knowledge', 'simulate']
// On/off pill styles for the per-user permission toggles.
const PILL_ON = 'bg-primary-100 text-primary-700 hover:bg-primary-200'
const PILL_OFF = 'bg-greyscale-100 text-greyscale-500 hover:bg-greyscale-200'

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
    // Site settings
    sites: [],
    siteId: null,
    siteName: '',
    siteCourtName: '',
    siteJurisdictionLevel: '',
    siteState: '',
    siteOfficialUrl: '',
    siteOfficialResourcesUrl: '',
    siteFastModel: '',
    siteAssistantModel: '',
    activeSiteName: '',
    siteMenuOpen: false,
    siteSaved: false,
    siteError: '',
    // Knowledge base tab
    kbTopics: [],
    kbListVisible: true,
    kbEditorVisible: false,
    kbEditorTitle: '',
    kbEditingId: null,
    kbConfirmingId: null,
    kbTitle: '',
    kbSubtitle: '',
    kbDescription: '',
    kbIcon: '',
    kbMetaDescription: '',
    kbPrompts: '',
    kbError: '',
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
      this.loadSites()
      this.loadUsers()
      this.loadTopics()
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
    },

    // --- Site settings ---

    async loadSites() {
      try {
        const res = await fetch('/api/admin/sites/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.sites = data.sites || []
        const active = this.sites.find((s) => s.active)
        this.siteId = active ? active.id : null
        this.siteName = active ? active.name : ''
        this.siteCourtName = active ? active.court_name : ''
        this.siteJurisdictionLevel = active ? active.jurisdiction_level : ''
        this.siteState = active ? active.state : ''
        this.siteOfficialUrl = active ? active.official_url : ''
        this.siteOfficialResourcesUrl = active
          ? active.official_resources_url
          : ''
        this.siteFastModel = (active && active.fast_model) || ''
        this.siteAssistantModel = (active && active.assistant_model) || ''
        this.activeSiteName = active ? active.name : ''
      } catch (e) {
        console.error('Failed to load site settings:', e)
      }
    },

    // Input handler for every settings field — the target property name
    // rides on the element's data-field attribute.
    updateSiteField(e) {
      this[e.currentTarget.dataset.field] = e.currentTarget.value
      this.siteSaved = false
      this.siteError = ''
    },

    async saveSite() {
      if (!this.siteId || !this.siteName.trim()) return
      try {
        const body = new FormData()
        body.append('name', this.siteName.trim())
        body.append('court_name', this.siteCourtName.trim())
        body.append('jurisdiction_level', this.siteJurisdictionLevel)
        body.append('state', this.siteState.trim().toUpperCase())
        body.append('official_url', this.siteOfficialUrl.trim())
        body.append(
          'official_resources_url',
          this.siteOfficialResourcesUrl.trim()
        )
        body.append('fast_model', this.siteFastModel)
        body.append('assistant_model', this.siteAssistantModel)
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch(
          '/api/admin/sites/' + this.siteId + '/update/',
          { method: 'POST', body }
        )
        if (!res.ok) {
          // Surface the server's validation message next to Save.
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || 'Request failed: ' + res.status)
        }
        this.siteSaved = true
        this.siteError = ''
        await this.loadSites()
      } catch (e) {
        console.error('Failed to save site settings:', e)
        this.siteError = e.message
      }
    },

    toggleSiteMenu() {
      this.siteMenuOpen = !this.siteMenuOpen
    },

    closeSiteMenu() {
      this.siteMenuOpen = false
    },

    // Click handler for a switcher row — the site id rides on the element.
    async activateSite(e) {
      const siteId = e.currentTarget.dataset.siteId
      this.siteMenuOpen = false
      if (!siteId || siteId === this.siteId) return
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/sites/' + siteId + '/activate/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        this.siteSaved = false
        await this.loadSites()
        // Topics belong to the active site — refresh the knowledge base.
        await this.loadTopics()
      } catch (e) {
        console.error('Failed to activate site:', e)
      }
    },

    csrfToken() {
      const input = document.querySelector('[name=csrfmiddlewaretoken]')
      return input ? input.value : ''
    },

    // --- Knowledge base tab ---

    async loadTopics() {
      try {
        const res = await fetch('/api/admin/topics/', {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        const data = await res.json()
        this.kbConfirmingId = null
        this.kbTopics = (data.topics || []).map((t) => this.decorateTopic(t))
      } catch (e) {
        console.error('Failed to load topics:', e)
      }
    },

    // Precompute CSP-safe bindings for a topic card.
    decorateTopic(t) {
      const prompts = t.prompts.length
      return {
        ...t,
        iconSvg: kbIconSvg(t.icon),
        countsLabel: prompts + (prompts === 1 ? ' prompt' : ' prompts'),
        confirmingDelete: t.id === this.kbConfirmingId,
        notConfirmingDelete: t.id !== this.kbConfirmingId,
      }
    },

    redecorateTopics() {
      this.kbTopics = this.kbTopics.map((t) => this.decorateTopic(t))
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
      this.kbIcon = topic.icon
      this.kbMetaDescription = topic.meta_description
      this.kbPrompts = topic.prompts.join('\n')
      this.openKbEditor('Edit topic')
    },

    newTopic() {
      this.kbEditingId = null
      this.kbTitle = ''
      this.kbSubtitle = ''
      this.kbDescription = ''
      this.kbIcon = ''
      this.kbMetaDescription = ''
      this.kbPrompts = ''
      this.openKbEditor('New topic')
    },

    openKbEditor(title) {
      this.kbEditorTitle = title
      this.kbError = ''
      this.kbListVisible = false
      this.kbEditorVisible = true
    },

    cancelTopicEdit() {
      this.kbEditorVisible = false
      this.kbListVisible = true
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

    askDeleteTopic(e) {
      this.kbConfirmingId = e.currentTarget.dataset.topicId
      this.redecorateTopics()
    },

    cancelDeleteTopic() {
      this.kbConfirmingId = null
      this.redecorateTopics()
    },

    async confirmDeleteTopic(e) {
      const topicId = e.currentTarget.dataset.topicId
      try {
        const body = new FormData()
        body.append('csrfmiddlewaretoken', this.csrfToken())
        const res = await fetch('/api/admin/topics/' + topicId + '/delete/', {
          method: 'POST',
          body,
        })
        if (!res.ok) throw new Error('Request failed: ' + res.status)
        await this.loadTopics()
      } catch (err) {
        console.error('Failed to delete topic:', err)
      }
    },

    // --- Users tab ---

    // Debounced input handler — no submit button; each keystroke (after
    // the pause) refetches page 1 with the new email filter.
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
        notStaff: !u.is_staff,
        adminToggleClass: u.is_admin ? PILL_ON : PILL_OFF,
        devToggleClass: u.is_staff ? PILL_ON : PILL_OFF,
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

    // Toggle membership (admin access) in the active site.
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
        this.patchUser(userId, { is_staff: data.is_staff })
      } catch (err) {
        console.error('Failed to toggle developer status:', err)
      }
    },
  }))
})
