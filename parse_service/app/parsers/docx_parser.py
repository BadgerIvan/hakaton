from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from .base import BaseParser, ParseResult


def cell_text(cell) -> str:
    return " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip()).replace("|", "\\|")


class DOCXParser(BaseParser):
    extensions = (".docx",)

    def parse(self, path: Path) -> ParseResult:
        doc = Document(path)
        lines: list[str] = []
        detected_title = (doc.core_properties.title or "").strip() or None
        for block in doc.iter_inner_content():
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                style = block.style.name.lower() if block.style else ""
                if style == "title" or style == "название":
                    detected_title = detected_title or text
                    lines.append(f"# {text}")
                elif style.startswith("heading") or style.startswith("заголовок"):
                    digits = "".join(c for c in style if c.isdigit())
                    level = min(max((int(digits) + 1) if digits else 2, 2), 6)
                    lines.append(f'{"#" * level} {text}')
                elif "list bullet" in style or "маркирован" in style:
                    lines.append(f"- {text}")
                elif "list number" in style or "нумерован" in style:
                    lines.append(f"1. {text}")
                else:
                    lines.append(text)
                lines.append("")
            elif isinstance(block, Table):
                rows = [[cell_text(c) for c in row.cells] for row in block.rows]
                if rows:
                    width = max(len(r) for r in rows)
                    rows = [r + [""] * (width-len(r)) for r in rows]
                    lines.append("| " + " | ".join(rows[0]) + " |")
                    lines.append("| " + " | ".join(["---"] * width) + " |")
                    for r in rows[1:]:
                        lines.append("| " + " | ".join(r) + " |")
                    lines.append("")
        result = "\n".join(lines).strip()
        if not result:
            raise ValueError("DOCX не содержит извлекаемого текста")
        return ParseResult(markdown=result + "\n", title=detected_title or path.stem)
