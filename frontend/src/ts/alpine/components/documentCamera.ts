/**
 * Document Camera Alpine Component
 *
 * Captures high-quality images from mobile cameras for legal document scanning.
 * Features:
 * - Multi-page document capture with stitching support
 * - Optimized resolution for OCR (300 DPI equivalent)
 * - Local storage with cloud-ready abstraction
 * - CSP-compliant implementation
 *
 * Usage in templates:
 * <div x-data="documentCamera">
 *   <button x-on:click="startCamera">Start Camera</button>
 *   <video x-ref="video" x-show="cameraActive"></video>
 *   <canvas x-ref="canvas" style="display:none"></canvas>
 *   <button x-on:click="captureImage" x-show="cameraActive">Capture</button>
 *   <div x-show="pages.length > 0">
 *     <template x-for="(page, index) in pages" :key="index">
 *       <img :src="page.dataUrl" :alt="'Page ' + (index + 1)">
 *     </template>
 *   </div>
 * </div>
 */

import Alpine from 'alpinejs'
import type { DocumentCameraComponent, CapturedPage } from '../../types/alpine'

// Optimal settings for OCR: 300 DPI equivalent on standard document
// For 8.5" x 11" page at 300 DPI = 2550 x 3300 pixels
// We'll use slightly lower for mobile performance: 2048 x 2732 (iPad Pro ratio)
const OCR_OPTIMAL_WIDTH = 2048
const OCR_OPTIMAL_HEIGHT = 2732

// JPEG quality: 0.85 balances quality and file size for document scanning
const JPEG_QUALITY = 0.85

Alpine.data('documentCamera', (): DocumentCameraComponent => ({
  // State
  cameraActive: false,
  pages: [],
  currentStream: null,
  error: null,
  isProcessing: false,

  // Camera constraints optimized for document capture
  cameraConstraints: {
    video: {
      facingMode: { ideal: 'environment' }, // Prefer back camera
      width: { ideal: OCR_OPTIMAL_WIDTH },
      height: { ideal: OCR_OPTIMAL_HEIGHT },
      aspectRatio: { ideal: OCR_OPTIMAL_HEIGHT / OCR_OPTIMAL_WIDTH },
    },
    audio: false,
  },

  init() {
    console.log('Document camera initialized')
  },

  /**
   * Start the camera stream
   */
  async startCamera() {
    try {
      this.error = null

      // Check if MediaDevices API is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera API not supported in this browser')
      }

      // Request camera access
      this.currentStream = await navigator.mediaDevices.getUserMedia(
        this.cameraConstraints
      )

      // Attach stream to video element
      const video = this.$refs.video as HTMLVideoElement
      if (video) {
        video.srcObject = this.currentStream
        await video.play()
        this.cameraActive = true
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to access camera'
      console.error('Camera error:', err)
    }
  },

  /**
   * Stop the camera stream
   */
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

  /**
   * Capture current video frame as an image
   */
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

      // Set canvas dimensions to OCR-optimal size
      canvas.width = OCR_OPTIMAL_WIDTH
      canvas.height = OCR_OPTIMAL_HEIGHT

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        throw new Error('Failed to get canvas context')
      }

      // Calculate scaling to fit video into canvas while maintaining aspect ratio
      // Validate video dimensions before calculating aspect ratio
      if (video.videoWidth === 0 || video.videoHeight === 0) {
        throw new Error('Video stream not ready. Please wait and try again.')
      }

      const videoAspect = video.videoWidth / video.videoHeight
      const canvasAspect = OCR_OPTIMAL_WIDTH / OCR_OPTIMAL_HEIGHT

      let sourceX = 0
      let sourceY = 0
      let sourceWidth = video.videoWidth
      let sourceHeight = video.videoHeight

      if (videoAspect > canvasAspect) {
        // Video is wider - crop sides
        sourceWidth = video.videoHeight * canvasAspect
        sourceX = (video.videoWidth - sourceWidth) / 2
      } else {
        // Video is taller - crop top/bottom
        sourceHeight = video.videoWidth / canvasAspect
        sourceY = (video.videoHeight - sourceHeight) / 2
      }

      // Draw video frame to canvas with optimal sizing
      ctx.drawImage(
        video,
        sourceX, sourceY, sourceWidth, sourceHeight,
        0, 0, OCR_OPTIMAL_WIDTH, OCR_OPTIMAL_HEIGHT
      )

      // Convert canvas to blob for storage
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (blob) => {
            if (blob) resolve(blob)
            else reject(new Error('Failed to create image blob'))
          },
          'image/jpeg',
          JPEG_QUALITY
        )
      })

      // Create data URL for preview
      const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY)

      // Add page to collection
      const page: CapturedPage = {
        id: crypto.randomUUID(),
        blob,
        dataUrl,
        timestamp: new Date().toISOString(),
        width: OCR_OPTIMAL_WIDTH,
        height: OCR_OPTIMAL_HEIGHT,
      }

      this.pages.push(page)
      console.log(`Captured page ${this.pages.length}, size: ${(blob.size / 1024).toFixed(1)}KB`)
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to capture image'
      console.error('Capture error:', err)
    } finally {
      this.isProcessing = false
    }
  },

  /**
   * Remove a page from the collection
   */
  removePage(pageId: string) {
    const index = this.pages.findIndex(p => p.id === pageId)
    if (index !== -1) {
      this.pages.splice(index, 1)
    }
  },

  /**
   * Clear all captured pages
   */
  clearPages() {
    this.pages = []
  },

  /**
   * Save document to storage (local filesystem or cloud)
   * Returns the storage path/URL
   */
  async saveDocument(filename?: string): Promise<string> {
    if (this.pages.length === 0) {
      throw new Error('No pages to save')
    }

    try {
      this.isProcessing = true
      this.error = null

      const docFilename = filename || `document_${Date.now()}.json`

      // Use storage service (abstracted for future cloud integration)
      const storageService = await this.getStorageService()
      const documentPath = await storageService.saveDocument({
        filename: docFilename,
        pages: this.pages,
      })

      console.log(`Document saved: ${documentPath}`)
      return documentPath
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to save document'
      console.error('Save error:', err)
      throw err
    } finally {
      this.isProcessing = false
    }
  },

  /**
   * Get storage service (abstraction layer for local/cloud storage)
   * This allows easy migration to AWS S3 or other cloud services
   */
  async getStorageService() {
    // For now, use local filesystem storage
    // In production, this would check environment and return appropriate service
    // (e.g., S3StorageService, AzureStorageService, etc.)
    return (await import('../../services/storage/localStorageService')).default
  },

  /**
   * Export document as multi-page PDF (future enhancement)
   * This would stitch pages together into a single PDF
   */
  async exportAsPDF(): Promise<Blob> {
    // TODO: Implement PDF generation using a library like jsPDF
    // For now, throw not implemented
    throw new Error('PDF export not yet implemented')
  },

  destroy() {
    // Cleanup: stop camera if active
    this.stopCamera()
    console.log('Document camera destroyed')
  },
}))
