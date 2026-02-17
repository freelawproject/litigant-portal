import logging

from django.db.models import Q, QuerySet

from chat.models import Document

logger = logging.getLogger(__name__)


class KeywordSearchService:
    """Service for keyword-based document search (fallback for AI chat)."""

    def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> QuerySet[Document]:
        """
        Search documents using keyword matching (icontains).

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
