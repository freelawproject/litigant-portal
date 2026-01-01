import logging

from django.db import connection
from django.db.models import Q, QuerySet

from chat.models import Document

logger = logging.getLogger(__name__)

# PostgreSQL-specific imports (optional)
try:
    from django.contrib.postgres.search import SearchQuery, SearchRank

    HAS_POSTGRES_SEARCH = connection.vendor == "postgresql"
except ImportError:
    HAS_POSTGRES_SEARCH = False
    SearchQuery = None
    SearchRank = None


class KeywordSearchService:
    """Service for keyword-based document search (fallback for AI chat)."""

    def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> QuerySet[Document]:
        """
        Search documents using best available method.

        Uses PostgreSQL full-text search if available, otherwise
        falls back to simple icontains search for SQLite.

        Args:
            query: The search query string.
            category: Optional category to filter by.
            limit: Maximum number of results to return.

        Returns:
            QuerySet of matching documents ordered by relevance.
        """
        if not query.strip():
            return Document.objects.none()

        # Use simple search (works with SQLite and PostgreSQL)
        queryset = Document.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

        if category:
            queryset = queryset.filter(category=category)

        return queryset[:limit]

    def search_simple(
        self,
        query: str,
        limit: int = 10,
    ) -> QuerySet[Document]:
        """
        Simple search using icontains for SQLite compatibility.

        This is used when PostgreSQL full-text search is not available
        (e.g., local development with SQLite).

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            QuerySet of matching documents.
        """
        if not query.strip():
            return Document.objects.none()

        # Simple title and content search
        return (
            Document.objects.filter(title__icontains=query)
            | Document.objects.filter(content__icontains=query)[:limit]
        )

    def get_categories(self) -> list[str]:
        """
        Get all unique document categories.

        Returns:
            List of category names.
        """
        return list(
            Document.objects.values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )


# Singleton instance
search_service = KeywordSearchService()
