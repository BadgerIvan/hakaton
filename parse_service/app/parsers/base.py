from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    markdown: str
    title: str | None = None
    pages: int | None = None
    warnings: list[str] = field(default_factory=list)


class BaseParser(ABC):
    # Extend with a list of suffixes, e.g. (".epub",)
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: Path) -> ParseResult:
        """Return semantic Markdown; do NOT generate YAML frontmatter here."""
