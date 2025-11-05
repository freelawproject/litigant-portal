/**
 * Local Filesystem Storage Service
 *
 * Implements storage interface for local development/testing.
 * In production, this would be replaced with a cloud storage service (AWS S3, etc.)
 *
 * Storage strategy:
 * - Save document metadata and page info to localStorage as JSON
 * - Keep image blobs in memory (referenced by data URLs)
 * - For production cloud storage, this would upload blobs to S3 and store references
 */

import type { StorageService, StorageDocument } from '../../types/alpine'

const STORAGE_PREFIX = 'doc_camera_'
const METADATA_KEY = `${STORAGE_PREFIX}metadata`

interface DocumentMetadata {
  id: string
  filename: string
  pageCount: number
  totalSize: number
  createdAt: string
  path: string
}

class LocalStorageService implements StorageService {
  /**
   * Save document to local storage
   * Returns the storage path/identifier
   */
  async saveDocument(document: StorageDocument): Promise<string> {
    try {
      const documentId = crypto.randomUUID()
      const path = `${STORAGE_PREFIX}${documentId}`

      // Calculate total size
      const totalSize = document.pages.reduce((sum, page) => sum + page.blob.size, 0)

      // Create metadata entry
      const metadata: DocumentMetadata = {
        id: documentId,
        filename: document.filename,
        pageCount: document.pages.length,
        totalSize,
        createdAt: new Date().toISOString(),
        path,
      }

      // Store document data (without blobs, as they're too large for localStorage)
      // In a real implementation, blobs would be uploaded to cloud storage
      const documentData = {
        filename: document.filename,
        pages: document.pages.map(page => ({
          id: page.id,
          dataUrl: page.dataUrl, // Keep data URL for local preview
          timestamp: page.timestamp,
          width: page.width,
          height: page.height,
          size: page.blob.size,
        })),
      }

      // Store document data
      localStorage.setItem(path, JSON.stringify(documentData))

      // Update metadata index
      this.addToMetadataIndex(metadata)

      console.log(`Document saved locally: ${path}`)
      return path
    } catch (err) {
      console.error('Failed to save document:', err)
      throw new Error('Failed to save document to local storage')
    }
  }

  /**
   * Load document from local storage
   */
  async loadDocument(path: string): Promise<StorageDocument> {
    try {
      const data = localStorage.getItem(path)
      if (!data) {
        throw new Error(`Document not found: ${path}`)
      }

      const documentData = JSON.parse(data)

      // Validate document structure
      if (!documentData.filename || !Array.isArray(documentData.pages)) {
        throw new Error('Invalid or corrupted document data')
      }

      // Convert data URLs back to blobs
      const pages = await Promise.all(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        documentData.pages.map(async (pageData: any) => {
          const blob = await this.dataUrlToBlob(pageData.dataUrl)
          return {
            id: pageData.id,
            blob,
            dataUrl: pageData.dataUrl,
            timestamp: pageData.timestamp,
            width: pageData.width,
            height: pageData.height,
          }
        })
      )

      return {
        filename: documentData.filename,
        pages,
      }
    } catch (err) {
      console.error('Failed to load document:', err)
      throw new Error('Failed to load document from local storage')
    }
  }

  /**
   * Delete document from local storage
   */
  async deleteDocument(path: string): Promise<void> {
    try {
      localStorage.removeItem(path)
      this.removeFromMetadataIndex(path)
      console.log(`Document deleted: ${path}`)
    } catch (err) {
      console.error('Failed to delete document:', err)
      throw new Error('Failed to delete document from local storage')
    }
  }

  /**
   * List all documents in local storage
   */
  async listDocuments(): Promise<string[]> {
    try {
      const metadata = this.getMetadataIndex()
      return metadata.map(m => m.path)
    } catch (err) {
      console.error('Failed to list documents:', err)
      return []
    }
  }

  /**
   * Get metadata for all documents
   */
  getMetadataIndex(): DocumentMetadata[] {
    try {
      const data = localStorage.getItem(METADATA_KEY)
      return data ? JSON.parse(data) : []
    } catch (err) {
      console.error('Failed to get metadata index:', err)
      return []
    }
  }

  /**
   * Add document to metadata index
   */
  private addToMetadataIndex(metadata: DocumentMetadata): void {
    const index = this.getMetadataIndex()
    index.push(metadata)
    localStorage.setItem(METADATA_KEY, JSON.stringify(index))
  }

  /**
   * Remove document from metadata index
   */
  private removeFromMetadataIndex(path: string): void {
    const index = this.getMetadataIndex()
    const filtered = index.filter(m => m.path !== path)
    localStorage.setItem(METADATA_KEY, JSON.stringify(filtered))
  }

  /**
   * Convert data URL to Blob
   */
  private async dataUrlToBlob(dataUrl: string): Promise<Blob> {
    const response = await fetch(dataUrl)
    return response.blob()
  }
}

// Export singleton instance
export default new LocalStorageService()
