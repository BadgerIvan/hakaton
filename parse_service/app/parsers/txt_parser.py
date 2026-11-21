from pathlib import Path
from .base import BaseParser, ParseResult


class TextParser(BaseParser):
    extensions = (".txt", ".md", ".markdown")

    def parse(self, path: Path) -> ParseResult:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            from charset_normalizer import from_bytes
            match = from_bytes(raw).best()
            if match is None:
                raise ValueError("Не удалось определить кодировку файла")
            text = str(match)
        normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
        return ParseResult(markdown=normalized.strip() + "\n", title=path.stem)
