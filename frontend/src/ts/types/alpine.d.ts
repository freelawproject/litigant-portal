/**
 * TypeScript type definitions for Alpine components
 *
 * Define interfaces for your Alpine components here
 */

import type { AlpineInstance } from './alpinejs'

/**
 * Base interface for Alpine component data
 * Extend this for your specific components
 */
export interface AlpineComponent {
  init?(): void
  destroy?(): void
}

/**
 * Example: Dropdown component interface
 */
export interface DropdownComponent extends AlpineComponent {
  open: boolean
  toggle(): void
  close(): void
}

/**
 * Document Camera component interfaces
 */
export interface CapturedPage {
  id: string
  blob: Blob
  dataUrl: string
  timestamp: string
  width: number
  height: number
}

export interface CameraConstraints {
  video: {
    facingMode: { ideal: string }
    width: { ideal: number }
    height: { ideal: number }
    aspectRatio: { ideal: number }
  }
  audio: boolean
}

export interface DocumentCameraComponent extends AlpineComponent {
  // State
  cameraActive: boolean
  pages: CapturedPage[]
  currentStream: MediaStream | null
  error: string | null
  isProcessing: boolean
  $refs: Record<string, HTMLElement>

  // Configuration
  cameraConstraints: CameraConstraints

  // Methods
  startCamera(): Promise<void>
  stopCamera(): void
  captureImage(): Promise<void>
  removePage(pageId: string): void
  clearPages(): void
  saveDocument(filename?: string): Promise<string>
  getStorageService(): Promise<StorageService>
  exportAsPDF(): Promise<Blob>
}

/**
 * Storage service interface (abstraction for local/cloud storage)
 */
export interface StorageDocument {
  filename: string
  pages: CapturedPage[]
}

export interface StorageService {
  saveDocument(document: StorageDocument): Promise<string>
  loadDocument(path: string): Promise<StorageDocument>
  deleteDocument(path: string): Promise<void>
  listDocuments(): Promise<string[]>
}

declare global {
  interface Window {
    Alpine: AlpineInstance
  }
}
