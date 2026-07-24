import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass(slots=True)
class Citation:
    label: str
    title: str
    doi: str | None
    url: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def render_scientific_pdf(
    output_path: Path,
    title: str,
    abstract: str,
    sections: list[tuple[str, str]],
    citations: list[Citation],
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(output_path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm
    )
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 8 * mm)]
    story.extend([Paragraph("Abstract", styles["Heading1"]), Paragraph(escape(abstract), styles["BodyText"])])
    for heading, body in sections:
        story.extend([Spacer(1, 4 * mm), Paragraph(escape(heading), styles["Heading1"]), Paragraph(escape(body), styles["BodyText"])])
    story.extend([PageBreak(), Paragraph("References", styles["Heading1"])])
    for citation in citations:
        doi = f" https://doi.org/{citation.doi}" if citation.doi else ""
        story.append(Paragraph(escape(f"{citation.label}. {citation.title}.{doi}"), styles["BodyText"]))
    document.build(story)
    reader = PdfReader(str(output_path))
    return {"path": str(output_path), "sha256": sha256_file(output_path), "pages": len(reader.pages)}


def render_bar_chart_svg(output_path: Path, title: str, values: dict[str, float], provenance: dict) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height, margin = 900, 520, 80
    maximum = max(values.values(), default=1) or 1
    bar_width = max(20, (width - 2 * margin) / max(len(values), 1) * 0.65)
    gap = (width - 2 * margin) / max(len(values), 1)
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#f8faf8"/>', f'<text x="{margin}" y="45" font-family="Arial" font-size="26" font-weight="bold">{escape(title)}</text>']
    for index, (label, value) in enumerate(values.items()):
        x = margin + index * gap + (gap - bar_width) / 2
        bar_height = (height - 2 * margin) * value / maximum
        y = height - margin - bar_height
        elements.extend([
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="#2D5A3D"/>',
            f'<text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-family="Arial" font-size="16">{value:g}</text>',
            f'<text x="{x + bar_width / 2:.1f}" y="{height - margin + 24}" text-anchor="middle" font-family="Arial" font-size="14">{escape(label)}</text>',
        ])
    elements.append("</svg>")
    output_path.write_text("\n".join(elements), encoding="utf-8")
    provenance_path = output_path.with_suffix(".provenance.json")
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    return {"path": str(output_path), "sha256": sha256_file(output_path), "provenance": str(provenance_path)}
