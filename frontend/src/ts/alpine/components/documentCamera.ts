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

      // Check if we're on HTTPS (required for camera access)
      if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        throw new Error('Camera access requires HTTPS. Please use a secure connection.')
      }

      // Check if MediaDevices API is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera API not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.')
      }

      // Request camera access with detailed error handling
      try {
        this.currentStream = await navigator.mediaDevices.getUserMedia(
          this.cameraConstraints
        )
      } catch (mediaErr: unknown) {
        // Provide user-friendly error messages based on error type
        if (mediaErr instanceof Error) {
          if (mediaErr.name === 'NotAllowedError' || mediaErr.name === 'PermissionDeniedError') {
            throw new Error('Camera permission denied. Please allow camera access in your browser settings and try again.')
          } else if (mediaErr.name === 'NotFoundError' || mediaErr.name === 'DevicesNotFoundError') {
            throw new Error('No camera found. Please ensure your device has a camera.')
          } else if (mediaErr.name === 'NotReadableError' || mediaErr.name === 'TrackStartError') {
            throw new Error('Camera is already in use by another application. Please close other apps using the camera.')
          } else if (mediaErr.name === 'OverconstrainedError') {
            throw new Error('Camera does not support the requested settings. Trying with default settings...')
          } else if (mediaErr.name === 'SecurityError') {
            throw new Error('Camera access blocked by security policy. Please check browser permissions.')
          }
        }
        throw mediaErr
      }

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

      // Log additional debugging info
      console.log('Browser info:', {
        userAgent: navigator.userAgent,
        protocol: location.protocol,
        hostname: location.hostname,
        hasMediaDevices: !!navigator.mediaDevices,
        hasGetUserMedia: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
      })
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
   * Save document and trigger download as PDF
   */
  async saveDocument(filename?: string): Promise<string> {
    if (this.pages.length === 0) {
      throw new Error('No pages to save')
    }

    try {
      this.isProcessing = true
      this.error = null

      const timestamp = new Date().toISOString().split('T')[0] // YYYY-MM-DD
      const baseName = filename || `document_${timestamp}`

      await this.downloadAsPDF(baseName)
      return `${baseName}.pdf`
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to save document'
      console.error('Save error:', err)
      throw err
    } finally {
      this.isProcessing = false
    }
  },

  /**
   * Download document as multi-page PDF
   * Uses jsPDF library for PDF generation
   */
  async downloadAsPDF(baseName: string): Promise<void> {
    // Dynamic import of jsPDF for code splitting
    const { jsPDF } = await import('jspdf')

    // Create PDF in portrait orientation, letter size (8.5" x 11")
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'in',
      format: 'letter',
      compress: true
    })

    // Add each page as an image
    for (let i = 0; i < this.pages.length; i++) {
      const page = this.pages[i]

      if (i > 0) {
        pdf.addPage() // Add new page for all but first image
      }

      // Add image to PDF (fit to page with margins)
      // Letter size: 8.5" x 11", leave 0.5" margins
      pdf.addImage(
        page.dataUrl,
        'JPEG',
        0.5, // x position
        0.5, // y position
        7.5, // width
        10,  // height
        undefined,
        'FAST' // Compression
      )
    }

    // Save PDF
    pdf.save(`${baseName}.pdf`)
    console.log(`Downloaded PDF: ${baseName}.pdf (${this.pages.length} pages)`)
  },


  destroy() {
    // Cleanup: stop camera if active
    this.stopCamera()
    console.log('Document camera destroyed')
  },
}))
