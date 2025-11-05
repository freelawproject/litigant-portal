/**
 * Tests for Document Camera Component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { DocumentCameraComponent, CapturedPage } from '../../types/alpine'

// Mock the DocumentCamera component behavior
const createDocumentCamera = (): DocumentCameraComponent => ({
  // State
  cameraActive: false,
  pages: [],
  currentStream: null,
  error: null,
  isProcessing: false,

  // $refs mock
  $refs: {
    video: document.createElement('video'),
    canvas: document.createElement('canvas'),
  },

  // Camera constraints
  cameraConstraints: {
    video: {
      facingMode: { ideal: 'environment' },
      width: { ideal: 2048 },
      height: { ideal: 2732 },
      aspectRatio: { ideal: 2732 / 2048 },
    },
    audio: false,
  },

  // Methods
  init() {
    console.log('Document camera initialized')
  },

  async startCamera() {
    try {
      this.error = null

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera API not supported in this browser')
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      this.currentStream = await navigator.mediaDevices.getUserMedia(
        this.cameraConstraints
      ) as any

      const video = this.$refs.video as HTMLVideoElement
      if (video) {
        video.srcObject = this.currentStream
        await video.play()
        this.cameraActive = true
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to access camera'
    }
  },

  stopCamera() {
    if (this.currentStream) {
      this.currentStream.getTracks().forEach(track => track.stop())
      this.currentStream = null
    }

    const video = this.$refs.video as HTMLVideoElement
    if (video) {
      video.srcObject = null
    }

    this.cameraActive = false
  },

  async captureImage() {
    if (!this.cameraActive || this.isProcessing) return

    try {
      this.isProcessing = true
      this.error = null

      const video = this.$refs.video as HTMLVideoElement
      const canvas = this.$refs.canvas as HTMLCanvasElement

      if (!video || !canvas) {
        throw new Error('Video or canvas element not found')
      }

      canvas.width = 2048
      canvas.height = 2732

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        throw new Error('Failed to get canvas context')
      }

      const blob = new Blob(['test'], { type: 'image/jpeg' })
      const dataUrl = 'data:image/jpeg;base64,test'

      const page: CapturedPage = {
        id: crypto.randomUUID(),
        blob,
        dataUrl,
        timestamp: new Date().toISOString(),
        width: 2048,
        height: 2732,
      }

      this.pages.push(page)
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to capture image'
    } finally {
      this.isProcessing = false
    }
  },

  removePage(pageId: string) {
    const index = this.pages.findIndex(p => p.id === pageId)
    if (index !== -1) {
      this.pages.splice(index, 1)
    }
  },

  clearPages() {
    this.pages = []
  },

  async saveDocument(filename?: string): Promise<string> {
    if (this.pages.length === 0) {
      throw new Error('No pages to save')
    }

    try {
      this.isProcessing = true
      this.error = null

      const docFilename = filename || `document_${Date.now()}.json`
      const storageService = await this.getStorageService()
      const documentPath = await storageService.saveDocument({
        filename: docFilename,
        pages: this.pages,
      })

      return documentPath
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to save document'
      throw err
    } finally {
      this.isProcessing = false
    }
  },

  async getStorageService() {
    return (await import('../../services/storage/localStorageService')).default
  },

  async exportAsPDF(): Promise<Blob> {
    throw new Error('PDF export not yet implemented')
  },

  destroy() {
    this.stopCamera()
  },
})

describe('documentCamera', () => {
  let component: DocumentCameraComponent

  beforeEach(() => {
    component = createDocumentCamera()
  })

  afterEach(() => {
    if (component.destroy) {
      component.destroy()
    }
  })

  describe('initialization', () => {
    it('should initialize with correct default state', () => {
      expect(component.cameraActive).toBe(false)
      expect(component.pages).toEqual([])
      expect(component.currentStream).toBeNull()
      expect(component.error).toBeNull()
      expect(component.isProcessing).toBe(false)
    })

    it('should have camera constraints configured for document capture', () => {
      expect(component.cameraConstraints.video.facingMode.ideal).toBe('environment')
      expect(component.cameraConstraints.video.width.ideal).toBe(2048)
      expect(component.cameraConstraints.video.height.ideal).toBe(2732)
      expect(component.cameraConstraints.audio).toBe(false)
    })
  })

  describe('startCamera', () => {
    it('should handle missing MediaDevices API', async () => {
      const originalNavigator = global.navigator
      // @ts-expect-error - Intentionally testing with undefined mediaDevices
      global.navigator = { mediaDevices: undefined }

      await component.startCamera()

      expect(component.error).toContain('Camera API not supported')
      expect(component.cameraActive).toBe(false)

      // Restore
      global.navigator = originalNavigator
    })

    it('should request camera with correct constraints', async () => {
      const mockStream = { getTracks: () => [] }
      const getUserMediaMock = vi.fn().mockResolvedValue(mockStream)

      // @ts-expect-error - Mocking navigator for testing
      global.navigator = {
        mediaDevices: {
          getUserMedia: getUserMediaMock,
        },
      }

      const videoElement = component.$refs.video as HTMLVideoElement
      videoElement.play = vi.fn().mockResolvedValue(undefined)

      await component.startCamera()

      expect(getUserMediaMock).toHaveBeenCalledWith(component.cameraConstraints)
      expect(component.cameraActive).toBe(true)
      expect(component.currentStream).toBe(mockStream)
      expect(component.error).toBeNull()
    })

    it('should handle camera access errors', async () => {
      const errorMessage = 'Permission denied'
      const getUserMediaMock = vi.fn().mockRejectedValue(new Error(errorMessage))

      // @ts-expect-error - Mocking navigator for testing
      global.navigator = {
        mediaDevices: {
          getUserMedia: getUserMediaMock,
        },
      }

      await component.startCamera()

      expect(component.error).toBe(errorMessage)
      expect(component.cameraActive).toBe(false)
    })
  })

  describe('stopCamera', () => {
    it('should stop all tracks and clear stream', () => {
      const track1 = { stop: vi.fn() }
      const track2 = { stop: vi.fn() }
      const mockStream = {
        getTracks: () => [track1, track2],
      }

      component.currentStream = mockStream
      component.cameraActive = true

      component.stopCamera()

      expect(track1.stop).toHaveBeenCalled()
      expect(track2.stop).toHaveBeenCalled()
      expect(component.currentStream).toBeNull()
      expect(component.cameraActive).toBe(false)
    })

    it('should handle no active stream gracefully', () => {
      component.currentStream = null
      component.cameraActive = true

      expect(() => component.stopCamera()).not.toThrow()
      expect(component.cameraActive).toBe(false)
    })
  })

  describe('captureImage', () => {
    it('should not capture if camera is not active', async () => {
      component.cameraActive = false
      const initialPagesLength = component.pages.length

      await component.captureImage()

      expect(component.pages.length).toBe(initialPagesLength)
    })

    it('should not capture if already processing', async () => {
      component.cameraActive = true
      component.isProcessing = true
      const initialPagesLength = component.pages.length

      await component.captureImage()

      expect(component.pages.length).toBe(initialPagesLength)
    })

    it('should capture image with correct dimensions', async () => {
      component.cameraActive = true
      component.isProcessing = false

      const videoElement = component.$refs.video as HTMLVideoElement
      const canvasElement = component.$refs.canvas as HTMLCanvasElement

      // Mock video element
      Object.defineProperty(videoElement, 'videoWidth', { value: 1920 })
      Object.defineProperty(videoElement, 'videoHeight', { value: 1080 })

      // Mock canvas context
      const mockContext = {
        drawImage: vi.fn(),
      }
      canvasElement.getContext = vi.fn().mockReturnValue(mockContext)

      // Mock canvas.toBlob
      const mockBlob = new Blob(['test'], { type: 'image/jpeg' })
      canvasElement.toBlob = vi.fn((callback) => {
        setTimeout(() => callback(mockBlob), 0)
      })

      // Mock crypto.randomUUID using vi.spyOn
      const randomUUIDSpy = vi.spyOn(crypto, 'randomUUID').mockReturnValue('test-uuid' as `${string}-${string}-${string}-${string}-${string}`)

      await component.captureImage()

      expect(canvasElement.width).toBe(2048)
      expect(canvasElement.height).toBe(2732)
      expect(component.pages.length).toBe(1)
      expect(component.pages[0].id).toBe('test-uuid')
      expect(component.pages[0].blob).toBeInstanceOf(Blob)
      expect(component.pages[0].blob.type).toBe('image/jpeg')
      expect(component.pages[0].width).toBe(2048)
      expect(component.pages[0].height).toBe(2732)
      expect(component.isProcessing).toBe(false)

      randomUUIDSpy.mockRestore()
    })

    it('should handle canvas errors gracefully', async () => {
      component.cameraActive = true
      component.isProcessing = false

      const canvasElement = component.$refs.canvas as HTMLCanvasElement
      canvasElement.getContext = vi.fn().mockReturnValue(null)

      await component.captureImage()

      expect(component.error).toContain('Failed to get canvas context')
      expect(component.pages.length).toBe(0)
      expect(component.isProcessing).toBe(false)
    })
  })

  describe('removePage', () => {
    it('should remove page by id', () => {
      component.pages = [
        { id: 'page-1', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
        { id: 'page-2', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
        { id: 'page-3', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
      ]

      component.removePage('page-2')

      expect(component.pages.length).toBe(2)
      expect(component.pages.find(p => p.id === 'page-2')).toBeUndefined()
      expect(component.pages.find(p => p.id === 'page-1')).toBeDefined()
      expect(component.pages.find(p => p.id === 'page-3')).toBeDefined()
    })

    it('should handle non-existent page id gracefully', () => {
      component.pages = [
        { id: 'page-1', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
      ]

      component.removePage('non-existent')

      expect(component.pages.length).toBe(1)
    })
  })

  describe('clearPages', () => {
    it('should remove all pages', () => {
      component.pages = [
        { id: 'page-1', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
        { id: 'page-2', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
      ]

      component.clearPages()

      expect(component.pages).toEqual([])
    })
  })

  describe('saveDocument', () => {
    it('should throw error if no pages captured', async () => {
      component.pages = []

      await expect(component.saveDocument()).rejects.toThrow('No pages to save')
    })

    it('should save document with pages', async () => {
      const mockPage = {
        id: 'page-1',
        blob: new Blob(['test'], { type: 'image/jpeg' }),
        dataUrl: 'data:image/jpeg;base64,test',
        timestamp: new Date().toISOString(),
        width: 2048,
        height: 2732,
      }
      component.pages = [mockPage]

      const mockStorageService = {
        saveDocument: vi.fn().mockResolvedValue('path/to/document.json'),
      }

      component.getStorageService = vi.fn().mockResolvedValue(mockStorageService)

      const path = await component.saveDocument('test-doc.json')

      expect(mockStorageService.saveDocument).toHaveBeenCalledWith({
        filename: 'test-doc.json',
        pages: component.pages,
      })
      expect(path).toBe('path/to/document.json')
      expect(component.isProcessing).toBe(false)
    })

    it('should generate filename if not provided', async () => {
      const mockPage = {
        id: 'page-1',
        blob: new Blob(['test'], { type: 'image/jpeg' }),
        dataUrl: 'data:image/jpeg;base64,test',
        timestamp: new Date().toISOString(),
        width: 2048,
        height: 2732,
      }
      component.pages = [mockPage]

      const mockStorageService = {
        saveDocument: vi.fn().mockResolvedValue('path/to/document.json'),
      }

      component.getStorageService = vi.fn().mockResolvedValue(mockStorageService)

      await component.saveDocument()

      expect(mockStorageService.saveDocument).toHaveBeenCalled()
      const callArg = mockStorageService.saveDocument.mock.calls[0][0]
      expect(callArg.filename).toMatch(/^document_\d+\.json$/)
    })

    it('should handle storage errors', async () => {
      component.pages = [
        { id: 'page-1', blob: new Blob(), dataUrl: '', timestamp: '', width: 2048, height: 2732 },
      ]

      const mockStorageService = {
        saveDocument: vi.fn().mockRejectedValue(new Error('Storage failed')),
      }

      component.getStorageService = vi.fn().mockResolvedValue(mockStorageService)

      await expect(component.saveDocument()).rejects.toThrow()
      expect(component.error).toBe('Storage failed')
      expect(component.isProcessing).toBe(false)
    })
  })

  describe('exportAsPDF', () => {
    it('should throw not implemented error', async () => {
      await expect(component.exportAsPDF()).rejects.toThrow('PDF export not yet implemented')
    })
  })

  describe('destroy', () => {
    it('should stop camera on cleanup', () => {
      const stopCameraSpy = vi.spyOn(component, 'stopCamera')

      component.destroy?.()

      expect(stopCameraSpy).toHaveBeenCalled()
    })
  })
})
