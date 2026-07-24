import io
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from pypdf import PdfReader


@dataclass(slots=True)
class TextPassage:
    text: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None


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
