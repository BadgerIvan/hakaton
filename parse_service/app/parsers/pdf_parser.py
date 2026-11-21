from pathlib import Path
import re
import fitz
from .base import BaseParser, ParseResult


class PDFParser(BaseParser):
    extensions = (".pdf",)

    def parse(self, path: Path) -> ParseResult:
        pages_out = []
        with fitz.open(path) as pdf:
            count = len(pdf)
            for number, page in enumerate(pdf, start=1):
                text = page.get_text("text", sort=True)
                lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
                lines = [x for x in lines if x]
                if not lines:
                    pages_out.append(f"## Страница {number}\n\n[Текст не извлечён: возможен скан, нужен OCR]")
                    continue
                # PDF has no reliable structural heading tags. Preserve page boundaries
                # and reading order, but do not invent headings or merge unrelated lines.
                pages_out.append(f"## Страница {number}\n\n" + "\n".join(lines))
        if not pages_out:
            raise ValueError("Пустой PDF")
        if all("[Текст не извлечён" in p for p in pages_out):
            raise ValueError("PDF содержит только изображения/сканы; нужен OCR")
        return ParseResult(markdown="\n\n".join(pages_out) + "\n", title=path.stem, pages=count)
