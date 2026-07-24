import io
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from pypdf import PdfReader
import httpx


@dataclass(slots=True)
class TextPassage:
    text: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None


@dataclass(slots=True)
class DownloadedDocument:
    content: bytes
    content_type: str
    final_url: str


def download_open_access_document(url: str, max_bytes: int = 25_000_000) -> DownloadedDocument:
    """Download a declared OA location with a strict size cap; never attempts authentication bypass."""
    headers = {"User-Agent": "audhd-research-platform/0.1", "Accept": "application/pdf,text/html,application/xhtml+xml"}
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=45) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0].lower()
        if content_type not in {"application/pdf", "text/html", "application/xhtml+xml"}:
            raise ValueError(f"Unsupported full-text content type: {content_type}")
        content = bytearray()
        for block in response.iter_bytes():
            content.extend(block)
            if len(content) > max_bytes:
                raise ValueError("Full-text document exceeds configured size limit")
        return DownloadedDocument(bytes(content), content_type, str(response.url))


def parse_downloaded_document(document: DownloadedDocument) -> list[TextPassage]:
    if document.content_type == "application/pdf":
        return parse_pdf(document.content)
    return parse_html(document.content.decode("utf-8", errors="replace"))


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def parse_pdf(content: bytes) -> list[TextPassage]:
    reader = PdfReader(io.BytesIO(content))
    return [
        TextPassage(text=text, page_start=index, page_end=index)
        for index, page in enumerate(reader.pages, start=1)
        if (text := (page.extract_text() or "").strip())
    ]


def parse_html(content: str) -> list[TextPassage]:
    parser = _VisibleTextParser()
    parser.feed(content)
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return [TextPassage(text=text)] if text else []


def chunk_passages(passages: list[TextPassage], max_chars: int = 5000) -> list[TextPassage]:
    chunks: list[TextPassage] = []
    for passage in passages:
        paragraphs = re.split(r"\n\s*\n", passage.text)
        buffer = ""
        for paragraph in paragraphs:
            if buffer and len(buffer) + len(paragraph) + 2 > max_chars:
                chunks.append(TextPassage(buffer, passage.page_start, passage.page_end, passage.section))
                buffer = ""
            buffer = f"{buffer}\n\n{paragraph}".strip()
        if buffer:
            chunks.append(TextPassage(buffer, passage.page_start, passage.page_end, passage.section))
    return chunks
