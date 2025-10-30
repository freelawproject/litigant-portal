/**
 * Tests for the dropdown Alpine component
 *
 * Example showing how to test Alpine components with Vitest
 */

import { describe, it, expect, beforeEach } from 'vitest'
import type { DropdownComponent } from '../../types/alpine'

// Mock the Alpine component behavior
const createDropdown = (): DropdownComponent => ({
  open: false,
  toggle() {
    this.open = !this.open
  },
  close() {
    this.open = false
  },
})

describe('Dropdown Component', () => {
  let dropdown: DropdownComponent

  beforeEach(() => {
    dropdown = createDropdown()
  })

  it('should start closed', () => {
    expect(dropdown.open).toBe(false)
  })

  it('should toggle open and closed', () => {
    dropdown.toggle()
    expect(dropdown.open).toBe(true)

    dropdown.toggle()
    expect(dropdown.open).toBe(false)
  })

  it('should close when calling close()', () => {
    dropdown.open = true
    dropdown.close()
    expect(dropdown.open).toBe(false)
  })
})
