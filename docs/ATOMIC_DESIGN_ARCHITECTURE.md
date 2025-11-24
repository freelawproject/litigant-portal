# Litigant Portal - Atomic Design Architecture Plan

**Date**: November 23, 2025
**Status**: Planning Document
**Stack**: Django Cotton + AlpineJS + Tailwind CSS

---

## Executive Summary

This document outlines the atomic design architecture for the Litigant Portal, designed for mobile-first development with WCAG AA accessibility compliance. The architecture leverages Django Cotton for server-side components, AlpineJS for lightweight reactivity, and Tailwind CSS for utility-first styling.

**Key Decisions**:
- Full atomic design hierarchy (atoms → organisms → templates → pages)
- Django-pattern-library for component documentation (not Storybook)
- WCAG AA compliance baked into all components
- Reusable single-question form pattern for mobile UX
- Django manages state, Alpine provides reactivity
- Mobile-first responsive design throughout

---

## Proposed Directory Structure

```
templates/
├── atoms/                          # Base UI primitives
│   ├── button.html                 # Primary, secondary, text variants
│   ├── input.html                  # Text, email, tel, number
│   ├── label.html                  # Form labels with required indicators
│   ├── icon.html                   # SVG icon wrapper
│   ├── badge.html                  # Status indicators
│   └── link.html                   # Text links, nav links
│
├── molecules/                      # Simple component combinations
│   ├── form_field.html             # Label + input + error message
│   ├── dropdown.html               # (existing) Button + menu
│   ├── card.html                   # Container with header/body/footer slots
│   ├── alert.html                  # Icon + message + dismiss
│   ├── progress_indicator.html     # Step X of Y
│   └── file_upload.html            # Input + preview + actions
│
├── organisms/                      # Complex, standalone components
│   ├── document_camera.html        # (existing) Full camera interface
│   ├── mobile_header.html          # Logo + menu + notifications
│   ├── case_card.html              # Complete case summary
│   ├── payment_form.html           # Full payment capture flow
│   ├── fee_waiver_check.html       # Eligibility questionnaire
│   └── single_question_form.html   # One question per screen pattern
│
├── templates/                      # Page layouts
│   ├── base.html                   # Root layout (existing)
│   ├── mobile_base.html            # Mobile-optimized variant
│   ├── single_column.html          # For forms, simple pages
│   ├── dashboard.html              # Two-column with sidebar
│   └── fullscreen.html             # For camera, maps
│
└── pages/                          # Complete page compositions
    ├── index.html
    ├── case_filing_wizard.html
    ├── dashboard.html
    └── payment_flow.html
```

### Naming Conventions

- **Files**: `snake_case.html` (Python/Django convention)
- **Cotton components**: `<c-component-name>` (kebab-case)
- **AlpineJS data**: `x-data="componentName"` (camelCase)
- **CSS classes**: Tailwind utilities only at component level

---

## Component Library: Django Pattern Library

**Problem**: Storybook doesn't natively support Django templates.

**Solution**: Use [django-pattern-library](https://github.com/torchbox/django-pattern-library)

### Why Django Pattern Library?

- Built specifically for Django templates
- Works with Django template tags (including Cotton)
- Live component preview with props
- YAML-based fixture data
- Mobile responsive preview
- Used by Wagtail CMS team (production-tested)

### Setup Example

```yaml
# pattern-library/patterns/atoms/button/button.yml
name: Button
context:
  label: "Submit"
  variant: "primary"
  type: "submit"
  disabled: false
```

```html
<!-- templates/atoms/button.html -->
<c-vars variant="primary" type="button" disabled="false" />
<button
  type="{{ type }}"
  {% if disabled %}disabled{% endif %}
  class="
    {% if variant == 'primary' %}
      bg-blue-600 text-white hover:bg-blue-700
    {% elif variant == 'secondary' %}
      bg-gray-200 text-gray-900 hover:bg-gray-300
    {% endif %}
    px-4 py-2 rounded-lg font-medium
    disabled:opacity-50 disabled:cursor-not-allowed
    focus:outline-none focus:ring-2 focus:ring-offset-2
  ">
  {{ label }}
</button>
```

Access at: `http://localhost:8000/pattern-library/atoms/button/`

---

## WCAG AA Compliance Patterns

### Required for All Components

**1. Keyboard Navigation**
```html
<!-- All interactive elements must be keyboard accessible -->
<button
  tabindex="0"
  @keydown.enter="handleAction"
  @keydown.space.prevent="handleAction">
```

**2. Focus Indicators**
```css
/* Tailwind classes for all focusable elements */
focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
```

**3. Color Contrast**
- Text: 4.5:1 minimum (Tailwind's default grays meet this)
- Large text (18pt+): 3:1 minimum
- Use [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

**4. ARIA Labels**
```html
<!-- For icon-only buttons -->
<button aria-label="Close dialog">
  <c-icon name="x" />
</button>

<!-- For form fields (already labeled) -->
<input
  id="email"
  aria-describedby="email-error"
  aria-invalid="{{ 'true' if errors else 'false' }}">
<div id="email-error" role="alert">{{ error_message }}</div>
```

**5. Form Validation**
```html
<!-- Required field indicator -->
<label for="case-type">
  Case Type
  <span aria-label="required" class="text-red-600">*</span>
</label>
```

**6. Mobile Touch Targets**
```css
/* Minimum 44x44px touch target (WCAG 2.5.5) */
min-h-[44px] min-w-[44px]
```

---

## Reusable Single-Question Form Pattern

### Component: `templates/organisms/single_question_form.html`

```html
<c-vars
  question=""
  help_text=""
  field_type="text"
  field_name=""
  current_step="1"
  total_steps="12"
  next_url=""
  prev_url=""
  initial_value=""
/>

<div class="min-h-screen flex flex-col" x-data="singleQuestionForm">

  <!-- Progress Indicator -->
  <c-progress-indicator
    :current="{{ current_step }}"
    :total="{{ total_steps }}" />

  <!-- Question -->
  <main class="flex-1 px-4 py-8">
    <h1 class="text-2xl font-bold mb-2">{{ question }}</h1>

    {% if help_text %}
    <p class="text-gray-600 mb-6">{{ help_text }}</p>
    {% endif %}

    <!-- Form Field -->
    <form method="post" action="{{ next_url }}" @submit="handleSubmit">
      {% csrf_token %}

      <c-form-field
        name="{{ field_name }}"
        type="{{ field_type }}"
        value="{{ initial_value }}"
        autofocus="true" />

      <!-- Navigation -->
      <div class="fixed bottom-0 left-0 right-0 bg-white border-t p-4 flex gap-3">
        {% if prev_url %}
        <c-button
          variant="secondary"
          label="Back"
          @click="window.location='{{ prev_url }}'" />
        {% endif %}

        <c-button
          variant="primary"
          type="submit"
          label="{% if current_step == total_steps %}Submit{% else %}Next{% endif %}"
          class="flex-1" />
      </div>
    </form>
  </main>

  <!-- Auto-save indicator -->
  <div
    x-show="saving"
    class="fixed top-4 right-4 bg-blue-100 text-blue-800 px-3 py-1 rounded-lg text-sm">
    Saving...
  </div>
</div>
```

### AlpineJS Component

```typescript
// frontend/src/ts/alpine/components/singleQuestionForm.ts
export default () => ({
  saving: false,

  init() {
    // Auto-save on input change (debounced)
    this.$watch('value', () => {
      this.autoSave();
    });
  },

  autoSave: debounce(async function(this: any) {
    this.saving = true;

    await fetch('/api/save-draft/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCsrfToken(),
      },
      body: JSON.stringify({
        field_name: this.$el.querySelector('input').name,
        value: this.$el.querySelector('input').value,
      }),
    });

    this.saving = false;
  }, 1000),

  handleSubmit(e: Event) {
    // Validate before submission
    if (!this.isValid()) {
      e.preventDefault();
      return;
    }
  },

  getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  },
});
```

---

## Django → Alpine State Flow

### Pattern: Server-Rendered State Injection

**Django View**:
```python
# portal/views.py
def case_filing_step(request, step_number):
    # Get state from Django session/database
    filing_data = request.session.get('filing_data', {})

    context = {
        'question': QUESTIONS[step_number]['text'],
        'field_name': QUESTIONS[step_number]['field'],
        'current_step': step_number,
        'total_steps': len(QUESTIONS),
        'initial_value': filing_data.get(QUESTIONS[step_number]['field'], ''),

        # Pass structured data to Alpine
        'alpine_state': json.dumps({
            'all_answers': filing_data,
            'validation_rules': QUESTIONS[step_number]['validation'],
        }),
    }

    return render(request, 'organisms/single_question_form.html', context)
```

**Template**:
```html
<!-- Inject Django state into Alpine component -->
<div
  x-data="singleQuestionForm"
  x-init="initWithState({{ alpine_state|safe }})">

  <!-- Component content -->
</div>
```

**Alpine Component**:
```typescript
export default () => ({
  allAnswers: {},
  validationRules: {},

  initWithState(state: any) {
    this.allAnswers = state.all_answers;
    this.validationRules = state.validation_rules;
  },

  isValid() {
    // Use server-provided validation rules
    if (this.validationRules.required && !this.value) {
      return false;
    }
    // ... more validation
    return true;
  },
});
```

### Pattern: Django Template Variables → Alpine Props

```html
<!-- Django Cotton component receives Django context -->
<c-case-card
  case_number="{{ case.docket_number }}"
  status="{{ case.status }}"
  :next_hearing="{{ case.next_hearing|date:'c' }}"
  x-data="{
    expanded: false,
    statusColor: '{{ case.status }}' === 'active' ? 'green' : 'gray'
  }">

  <!-- AlpineJS can reference both Django vars and Alpine state -->
  <div :class="`text-${statusColor}-600`">
    {{ case.status }}
  </div>
</c-case-card>
```

---

## Mobile-First Implementation Strategy

### Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    screens: {
      'sm': '640px',   // Small tablets
      'md': '768px',   // Tablets
      'lg': '1024px',  // Desktops
      'xl': '1280px',  // Large desktops
    },
  },
  // Enable touch-friendly utilities
  plugins: [
    require('@tailwindcss/forms'),  // Better form defaults
  ],
}
```

### Component Example: Mobile-First Card

```html
<!-- templates/molecules/card.html -->
<c-vars title="" />

<article class="
  <!-- Mobile first: full width, minimal padding -->
  bg-white rounded-lg shadow p-4

  <!-- Tablet: more padding -->
  md:p-6

  <!-- Desktop: max width, centered -->
  lg:max-w-2xl lg:mx-auto lg:p-8
">
  <h2 class="
    text-lg font-bold
    md:text-xl
    lg:text-2xl
  ">
    {{ title }}
  </h2>

  <div class="mt-4">
    <c-slot />
  </div>
</article>
```

---

## Critical Atomic Components for MVP

Based on requirements, prioritize building these:

### Atoms (Week 1)
- `button.html` - Primary, secondary, text, icon variants
- `input.html` - Text, email, tel, number, date
- `label.html` - With required indicator
- `icon.html` - Lucide/Heroicons wrapper
- `link.html` - Navigation links

### Molecules (Week 2)
- `form_field.html` - Label + input + error + help text
- `alert.html` - Success, error, warning, info
- `progress_indicator.html` - Step X of Y
- `card.html` - Basic container
- `badge.html` - Status indicators (filed, pending, etc.)

### Organisms (Week 3-4)
- `single_question_form.html` - Core form pattern
- `mobile_header.html` - Logo + menu + user
- `document_camera.html` - (Already exists on branch)
- `payment_form.html` - Credit card/ACH capture
- `case_summary_card.html` - Dashboard case item

### Templates (Week 5)
- `mobile_base.html` - Mobile-optimized layout
- `form_wizard.html` - Multi-step form container
- `dashboard.html` - User case dashboard

---

## Accessibility Testing Workflow

### 1. Automated Testing (CI/CD)

```bash
# Add to package.json
"scripts": {
  "test:a11y": "pa11y-ci --config .pa11yci.json"
}
```

```json
// .pa11yci.json
{
  "defaults": {
    "standard": "WCAG2AA",
    "runners": ["axe", "htmlcs"]
  },
  "urls": [
    "http://localhost:8000/pattern-library/atoms/button/",
    "http://localhost:8000/pattern-library/molecules/form-field/"
  ]
}
```

### 2. Manual Testing Checklist

For each component:
- [ ] Keyboard navigation (Tab, Enter, Space, Arrows)
- [ ] Screen reader announcements (VoiceOver on iOS, TalkBack on Android)
- [ ] Color contrast 4.5:1 for text
- [ ] Touch targets minimum 44x44px
- [ ] Form labels properly associated
- [ ] Error messages announced to screen readers
- [ ] Focus indicators visible

### 3. Browser DevTools

- Chrome Lighthouse (Accessibility audit)
- Firefox Accessibility Inspector
- WAVE browser extension

---

## Recommended Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
1. Install `django-pattern-library`
2. Set up atomic design directory structure
3. Build 5 core atoms (button, input, label, icon, link)
4. Document components in pattern library
5. Set up pa11y automated testing

### Phase 2: Core Components (Weeks 3-4)
1. Build 5 critical molecules (form_field, alert, progress, card, badge)
2. Create `single_question_form` organism
3. Build mobile header
4. Implement auto-save functionality
5. Add keyboard navigation to all components

### Phase 3: Integration (Weeks 5-6)
1. Build form wizard template
2. Create dashboard template
3. Integrate document camera component
4. Build payment form organism
5. Complete WCAG AA compliance testing

### Phase 4: Polish (Weeks 7-8)
1. Performance optimization (reduce Alpine bundle)
2. Add loading states and transitions
3. Implement offline support (service worker)
4. Mobile device testing on real devices
5. User testing with accessibility needs

---

## Critical Success Metrics

Track these to validate atomic design approach:

1. **Component Reuse Rate**: >80% of UI uses atoms/molecules
2. **Development Velocity**: New pages built in <2 days using existing components
3. **Accessibility Score**: Lighthouse score >90 on all pages
4. **Mobile Completion Rate**: Form completion on mobile ≥ desktop
5. **Bundle Size**: Total JS <50KB gzipped (Alpine is 15KB baseline)

---

## Current State Assessment

### Existing Foundation (from `feat/util/document-camera` branch)

**Strengths**:
- Professional tooling setup (Ruff, Prettier, ESLint, djlint)
- Testing infrastructure (pytest, Vitest, GitHub Actions)
- Pre-commit hooks configured
- TypeScript with type checking
- Proper separation of concerns
- CSP security considerations
- Mobile-first design philosophy documented

**Components Already Built**:
- `dropdown.html` - Basic dropdown component
- `select_dropdown.html` - Dropdown with selection state
- `document_camera.html` - Full camera capture component (~320 lines)
  - Mobile-optimized
  - OCR-optimized 2048x2732px resolution
  - Multi-page support
  - Storage abstraction (localStorage/AWS S3)
  - Comprehensive tests (~490 lines)

**Gaps to Fill**:
- No atoms layer yet (buttons, inputs, labels)
- No standard form field molecules
- No page layout templates
- No component documentation/pattern library
- No WCAG compliance testing workflow

---

## Next Steps

When ready to implement:

1. **Create sample implementations** of core atomic components (button, form_field, single_question_form)
2. **Set up django-pattern-library** with configuration files
3. **Build specific components** (mobile header, payment form)
4. **Create WCAG AA testing checklist** as workflow document

---

## References

- [Django Pattern Library](https://github.com/torchbox/django-pattern-library)
- [Django Cotton Documentation](https://django-cotton.com/)
- [AlpineJS Documentation](https://alpinejs.dev/)
- [WCAG 2.1 AA Guidelines](https://www.w3.org/WAI/WCAG21/quickref/?currentsidebar=%23col_customize&levels=aaa)
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [CourtListener Frontend Architecture](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)
