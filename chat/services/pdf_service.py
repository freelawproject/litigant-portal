"""PDF text extraction service using pdfplumber."""

import logging
from dataclasses import dataclass

from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

# Limits
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}
TEXT_PREVIEW_LENGTH = 500


@dataclass
class PDFExtractionResult:
    """Result of PDF text extraction."""

    success: bool
    page_count: int = 0
    text: str = ""
    text_preview: str = ""
    error: str | None = None


class PDFService:
    """Service for extracting text from PDF documents."""

    def validate_upload(
        self, file: InMemoryUploadedFile
    ) -> tuple[bool, str | None]:
        """
        Validate an uploaded PDF file.

        Args:
            file: The uploaded file to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        # Check content type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            return False, "Only PDF files are allowed"

        # Check file size
        if file.size > MAX_FILE_SIZE_BYTES:
            return False, f"File size exceeds {MAX_FILE_SIZE_MB}MB limit"

        # Check filename extension
        if not file.name.lower().endswith(".pdf"):
            return False, "File must have .pdf extension"

        return True, None

    def extract_text(self, file: InMemoryUploadedFile) -> PDFExtractionResult:
        """
        Extract text from an uploaded PDF file.

        Args:
            file: The uploaded PDF file (InMemoryUploadedFile).

        Returns:
            PDFExtractionResult with extracted text or error.
        """
        # Validate first
        is_valid, error = self.validate_upload(file)
        if not is_valid:
            return PDFExtractionResult(success=False, error=error)

        try:
            import pdfplumber

            # Open PDF from file-like object
            # pdfplumber can read from file-like objects directly
            with pdfplumber.open(file) as pdf:
                page_count = len(pdf.pages)

                if page_count == 0:
                    return PDFExtractionResult(
                        success=False,
                        error="PDF contains no pages",
                    )

                # Extract text from all pages
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                full_text = "\n\n".join(text_parts)

                if not full_text.strip():
                    return PDFExtractionResult(
                        success=False,
                        page_count=page_count,
                        error="Could not extract text from PDF. "
                        "The document may be scanned or image-based.",
                    )

                # Create preview (first N characters)
                text_preview = full_text[:TEXT_PREVIEW_LENGTH]
                if len(full_text) > TEXT_PREVIEW_LENGTH:
                    text_preview += "..."

                return PDFExtractionResult(
                    success=True,
                    page_count=page_count,
                    text=full_text,
                    text_preview=text_preview,
                )

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return PDFExtractionResult(
                success=False,
                error="Failed to process PDF file. Please try again.",
            )


# Singleton instance
pdf_service = PDFService()
