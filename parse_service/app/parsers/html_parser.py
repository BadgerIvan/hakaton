from pathlib import Path
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from .base import BaseParser, ParseResult


def extract_markdown(html: str, base_url: str = "") -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup.select("script, style, noscript, nav, footer, header, form, aside, iframe, button, .to-cart, .left-side-menu, .cookies-modal-backdrop, .cookies-banner, .cookies-message, .expanded-menu, .accounts-panel, .breadcrumbs, .breadcrumb, .back-link"):
        tag.decompose()
    # CFT and the education portal place the actual document in .content.
    root = soup.select_one("main") or soup.select_one(".content") or soup.select_one("article") or soup.body or soup
    for node in root.select('.top-info .format'):
        node.string='Форма: '+node.get_text(' ',strip=True)
    for node in root.select('.top-info .duration'):
        node.string='Продолжительность (значение сайта; единица не указана в HTML): '+node.get_text(' ',strip=True)
    if base_url:
        from urllib.parse import urljoin
        for link in root.select("a[href]"):
            link['href'] = urljoin(base_url, link['href'])
    for tag in root.select('a'):
        if tag.get_text(' ',strip=True) in ('Вернуться назад', 'Наверх'):
            tag.decompose()
    result = md(str(root), heading_style="ATX", bullets="-", strip=["img"])
    import re
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in result.splitlines())).strip()
    if not result:
        raise ValueError("HTML не содержит читаемого текста")
    return result, title


class HTMLParser(BaseParser):
    extensions = (".html", ".htm")

    def parse(self, path: Path) -> ParseResult:
        data = path.read_bytes()
        from charset_normalizer import from_bytes
        decoded = from_bytes(data).best()
        html = str(decoded) if decoded else data.decode("utf-8", errors="replace")
        import json
        sidecar = path.with_name(path.name + '.meta.json')
        meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
        result, title = extract_markdown(html, meta.get('source_url',''))
        return ParseResult(markdown=result + "\n", title=title)
