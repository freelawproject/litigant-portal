/**
 * Vanilla JS Component Registry
 *
 * Replaces Alpine.js with a lightweight factory + registry pattern.
 * Each component is a factory function receiving its root DOM element.
 *
 * Usage:
 *   registerComponent('name', (el) => { ... })
 *   <div data-component="name">
 *
 * Components own state as a plain object and call update() to sync DOM.
 * data-ref="name" replaces x-ref (queried via el.querySelector).
 */

const _registry = {}

/**
 * Register a component factory.
 * @param {string} name - Component name (matches data-component="name")
 * @param {(el: HTMLElement) => void} factory - Receives root element
 */
function registerComponent(name, factory) {
  _registry[name] = factory
}

/**
 * Initialize all data-component elements within root.
 * @param {HTMLElement|Document} [root=document]
 */
function initComponents(root = document) {
  root.querySelectorAll('[data-component]').forEach((el) => {
    const name = el.dataset.component
    if (el._componentInit) return // already initialized
    const factory = _registry[name]
    if (!factory) {
      console.warn(`Component "${name}" not registered`)
      return
    }
    el._componentInit = true
    factory(el)
  })
}

/**
 * Query a data-ref element within a root.
 * @param {HTMLElement} root
 * @param {string} name
 * @returns {HTMLElement|null}
 */
function ref(root, name) {
  return root.querySelector(`[data-ref="${name}"]`)
}

/**
 * Render a list from data into a container using a <template> element.
 *
 * @param {HTMLElement} container - Element that holds rendered items
 * @param {string} templateSelector - CSS selector for the <template>
 * @param {Array} items - Data array
 * @param {(clone: DocumentFragment, item: Object, index: number) => void} bindItem - Bind data to cloned template
 */
function renderList(container, templateSelector, items, bindItem) {
  const tpl = container.querySelector(templateSelector)
    || document.querySelector(templateSelector)
  if (!tpl) return

  // Remove all children except the template itself
  const children = Array.from(container.children)
  for (const child of children) {
    if (child !== tpl && child.tagName !== 'TEMPLATE') {
      container.removeChild(child)
    }
  }

  for (let i = 0; i < items.length; i++) {
    const clone = tpl.content.cloneNode(true)
    bindItem(clone, items[i], i)
    container.appendChild(clone)
  }
}

/**
 * Scroll an element to the bottom if near bottom already.
 * @param {HTMLElement} el
 * @param {boolean} [force=false]
 */
function scrollToBottom(el, force = false) {
  if (!el) return
  requestAnimationFrame(() => {
    const isNearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 150
    if (force || isNearBottom) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// Initialize all components on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  initComponents()
})
