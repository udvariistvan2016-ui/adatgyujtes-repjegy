from __future__ import annotations

from abc import ABC, abstractmethod

from farewatch.models import SearchRequest, SearchResult


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def search(self, request: SearchRequest) -> SearchResult:
        """Egy keresés: OW vagy RT. Hiányzó járatnál status=empty, ne dobjon."""
