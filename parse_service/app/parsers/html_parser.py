from pathlib import Path
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from .base import BaseParser, ParseResult


class HTMLParser(BaseParser):
    extensions = (".html", ".htm")

    def parse(self, path: Path) -> ParseResult:
        data = path.read_bytes()
        from charset_normalizer import from_bytes
        decoded = from_bytes(data).best()
        html = str(decoded) if decoded else data.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else path.stem
        for tag in soup.select("script, style, noscript, nav, footer, header, form, aside, iframe"):
            tag.decompose()
        root = soup.select_one("main") or soup.select_one("article") or soup.body or soup
        text = md(str(root), heading_style="ATX", bullets="-", strip=["img"])
        lines = [line.rstrip() for line in text.splitlines()]
        result = "\n".join(lines).strip()
        if not result:
            raise ValueError("HTML не содержит читаемого текста")
        return ParseResult(markdown=result + "\n", title=title)
