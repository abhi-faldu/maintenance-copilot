"""PDF -> sections with heading paths, page numbers, paragraphs and whole tables.

Design notes
- Headings are found by font size and weight relative to the body text, not by a TOC,
  because many shop-floor PDFs have no bookmarks. Numbered headings ("7.2.1 Symptoms",
  "Appendix A ...") give the level; unnumbered heading-styled lines get the level of the
  numbered headings printed at the same size.
- Tables are detected with PyMuPDF's ruling-line finder, but cell text is re-read with a
  clip rectangle per cell: `Table.extract()` drops spaces on some generators.
- A table that breaks across pages is stitched back together when the next page starts
  with a table of the same width and either no bold header row or a repeated copy of it.
- Running headers and footers are removed by finding lines that repeat on most pages in
  the top or bottom band (digits are normalised so "Page 3 of 19" matches "Page 4 of 19").
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from ingest.models import Block, ParsedDocument, Section

# Expand ligatures (ﬁ -> fi) so BM25 and exact-code matching work on the extracted text.
TEXT_FLAGS = (
    pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_LIGATURES & ~pymupdf.TEXT_PRESERVE_IMAGES
)
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st"})

NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+\S")
APPENDIX = re.compile(r"^(?:Appendix|Anhang)\s+([A-Z])\b", re.IGNORECASE)
APPENDIX_SUB = re.compile(r"^([A-Z](?:\.\d+)+)\s+\S")
LIST_ITEM = re.compile(r"^(?:\d{1,2}\.|[•▪–-])\s+\S")

MARGIN_BAND = 0.10  # top/bottom fraction of the page searched for running headers/footers


@dataclass
class _Line:
    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool
    block_no: int


@dataclass
class _Table:
    page: int
    y0: float
    rows: list[list[str]]
    has_header: bool


def _clean(text: str) -> str:
    return " ".join(text.translate(LIGATURES).split())


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & pymupdf.TEXT_FONT_BOLD) or "bold" in span["font"].lower()


def _dominant_style(spans: list[dict]) -> tuple[float, bool]:
    weight: Counter[tuple[float, bool]] = Counter()
    for s in spans:
        weight[(round(s["size"], 1), _is_bold(s))] += len(s["text"].strip())
    if not weight:
        return 0.0, False
    return weight.most_common(1)[0][0]


@dataclass
class _Span:
    text: str
    rect: pymupdf.Rect
    bold: bool


@dataclass
class _PageText:
    lines: list[_Line]
    spans: list[_Span]  # reading order; used to fill table cells without re-extracting


def _page_text(page: pymupdf.Page) -> _PageText:
    lines, spans = [], []
    data = page.get_text("dict", flags=TEXT_FLAGS)
    for b_no, block in enumerate(data["blocks"]):
        for line in block.get("lines", []):
            for s in line["spans"]:
                if s["text"].strip():
                    spans.append(_Span(s["text"], pymupdf.Rect(s["bbox"]), _is_bold(s)))
            text = _clean("".join(s["text"] for s in line["spans"]))
            if not text:
                continue
            size, bold = _dominant_style(line["spans"])
            x0, y0, x1, y1 = line["bbox"]
            lines.append(_Line(text, page.number + 1, x0, y0, x1, y1, size, bold, b_no))
    return _PageText(lines, spans)


def _cell_spans(pt: _PageText, cell) -> list[_Span]:
    if cell is None:
        return []
    r = pymupdf.Rect(cell)
    out = []
    for s in pt.spans:
        cx, cy = (s.rect.x0 + s.rect.x1) / 2, (s.rect.y0 + s.rect.y1) / 2
        if r.x0 <= cx <= r.x1 and r.y0 <= cy <= r.y1:
            out.append(s)
    return out


def _page_tables(page: pymupdf.Page, pt: _PageText) -> tuple[list[_Table], list[pymupdf.Rect]]:
    tables, rects = [], []
    # Ruling-line detection only: the ML layout gate (PyMuPDF >= 2) costs seconds per page
    # and adds nothing for ruled tables.
    for t in page.find_tables(use_layout=False).tables:
        rows: list[list[str]] = []
        for row in t.rows:
            # Uneven cell heights produce "phantom" rows with no text: drop them.
            cells = [_clean(" ".join(s.text for s in _cell_spans(pt, c))) for c in row.cells]
            if not any(cells):
                continue
            rows.append(cells)
        if not rows:
            continue
        header_spans = [s for c in t.rows[0].cells for s in _cell_spans(pt, c)]
        has_header = bool(header_spans) and all(s.bold for s in header_spans)
        tables.append(_Table(page.number + 1, t.bbox[1], rows, has_header))
        rects.append(pymupdf.Rect(t.bbox))
    return tables, rects


def _in_margin_band(line: _Line, page_height: float) -> bool:
    return line.y1 < page_height * MARGIN_BAND or line.y0 > page_height * (1 - MARGIN_BAND)


def _running_key(line: _Line) -> str:
    return re.sub(r"\d+", "#", line.text)


def _running_lines(pages: list[tuple[pymupdf.Page, _PageText]]) -> set[str]:
    """Normalised texts that repeat in the header/footer band on most pages."""
    if len(pages) < 3:
        return set()
    seen: Counter[str] = Counter()
    for page, pt in pages:
        h = page.rect.height
        keys = set()
        for line in pt.lines:
            if _in_margin_band(line, h):
                keys.add(_running_key(line))
        seen.update(keys)
    threshold = max(2, int(0.5 * len(pages)))
    return {k for k, n in seen.items() if n >= threshold}


def _table_markdown(rows: list[list[str]], has_header: bool) -> str:
    def fmt(r: list[str]) -> str:
        return "| " + " | ".join(c.replace("|", "/") for c in r) + " |"

    lines = []
    if has_header:
        lines.append(fmt(rows[0]))
        lines.append("|" + "---|" * len(rows[0]))
        body = rows[1:]
    else:
        body = rows
    lines.extend(fmt(r) for r in body)
    return "\n".join(lines)


def _heading_id(text: str) -> tuple[str, int] | None:
    """Return (section_id, level) for a numbered heading, else None."""
    if m := APPENDIX.match(text):
        return m.group(1).upper(), 1
    if m := APPENDIX_SUB.match(text):
        return m.group(1), m.group(1).count(".") + 1
    if m := NUMBERED.match(text):
        sid = m.group(1)
        return sid, sid.count(".") + 1
    return None


def _join_lines(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif LIST_ITEM.match(ln):
            out = f"{out}\n{ln}"  # keep procedure steps on their own lines
        elif re.search(r"[A-Za-zÄÖÜäöüß]-$", out) and ln[:1].islower():
            out = out[:-1] + ln  # de-hyphenate "lubri-" + "cation"
        else:
            out = f"{out} {ln}"
    return out


def _doc_meta(path: Path, doc: pymupdf.Document) -> tuple[str, str, str]:
    stem = path.stem
    doc_id = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    title = (doc.metadata or {}).get("title") or stem
    lang = "unknown"
    subject = (doc.metadata or {}).get("subject") or ""
    if m := re.search(r"lang=([a-z]{2})", subject):
        lang = m.group(1)
    elif m := re.search(r"[_-](EN|DE)$", stem, re.IGNORECASE):
        lang = m.group(1).lower()
    return doc_id, title, lang


def parse_pdf(path: str | Path) -> ParsedDocument:
    path = Path(path)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    doc = pymupdf.open("pdf", data)
    doc_id, title, lang = _doc_meta(path, doc)
    pages = [(page, _page_text(page)) for page in doc]
    running = _running_lines(pages)

    # 1. Collect page elements (lines outside tables, tables) in reading order.
    elements: list[tuple[int, float, str, object]] = []  # (page, y, kind, payload)
    all_lines: list[_Line] = []
    for page, pt in pages:
        tables, rects = _page_tables(page, pt)
        for line in pt.lines:
            # Only drop running text where it was learned: in the header/footer band.
            if _in_margin_band(line, page.rect.height) and _running_key(line) in running:
                continue
            cx, cy = (line.x0 + line.x1) / 2, (line.y0 + line.y1) / 2
            if any(r.x0 - 1 <= cx <= r.x1 + 1 and r.y0 - 1 <= cy <= r.y1 + 1 for r in rects):
                continue  # inside a table; its text comes from the cells
            all_lines.append(line)
            elements.append((line.page, line.y0, "line", line))
        for t in tables:
            elements.append((t.page, t.y0, "table", t))
    elements.sort(key=lambda e: (e[0], e[1]))

    # 2. Body size = most common size by character count; headings are clearly larger.
    sizes: Counter[float] = Counter()
    for ln in all_lines:
        sizes[ln.size] += len(ln.text)
    body = sizes.most_common(1)[0][0] if sizes else 10.0

    def is_heading_style(ln: _Line) -> bool:
        return (ln.size >= body + 1.5 and ln.bold) or ln.size >= body * 1.35

    size_level: dict[float, int] = {}
    for ln in all_lines:
        if is_heading_style(ln) and (hid := _heading_id(ln.text)):
            size_level[ln.size] = min(size_level.get(ln.size, 99), hid[1])

    # 3. Walk elements, building sections.
    front = Section("", title, [title], 0, 1, 1)
    sections: list[Section] = [front]
    stack: list[Section] = []
    current = front
    seen_numbered = False
    para: list[_Line] = []

    def flush_para() -> None:
        nonlocal para
        if not para:
            return
        text = _join_lines([p.text for p in para])
        prev = current.blocks[-1] if current.blocks else None
        # Sentence broken by a page break: continue the previous paragraph. Requires the
        # previous text to stop mid-sentence AND the new text to not start like a new
        # sentence or list item ("gap must be", "7-day average" continue; "The next",
        # "1. Stop" do not), so a caption at the foot of a page is not glued on.
        first = para[0].text
        if (
            prev is not None
            and prev.kind == "text"
            and prev.page_end == para[0].page - 1
            and not re.search(r"[.:!?)]$", prev.text)
            and not first[:1].isupper()
            and not LIST_ITEM.match(first)
        ):
            prev.text = _join_lines([prev.text, text])
            prev.page_end = para[-1].page
        else:
            current.blocks.append(Block("text", text, para[0].page, para[-1].page))
        current.page_end = max(current.page_end, para[-1].page)
        para = []

    i = 0
    while i < len(elements):
        page_no, _, kind, item = elements[i]

        if kind == "table":
            flush_para()
            t: _Table = item  # type: ignore[assignment]
            prev = current.blocks[-1] if current.blocks else None
            first_on_page = i == 0 or elements[i - 1][0] != page_no
            # Continuation of a table from the previous page: either no header row, or a
            # repeated copy of the previous table's header (common in OEM manuals).
            repeated_header = (
                t.has_header
                and prev is not None
                and prev.rows is not None
                and (prev.has_header and t.rows[0] == prev.rows[0])
            )
            if (
                prev is not None
                and prev.kind == "table"
                and first_on_page
                and (not t.has_header or repeated_header)
                and prev.page_end == page_no - 1
                and prev.n_cols == len(t.rows[0])
            ):
                prev.rows.extend(t.rows[1:] if repeated_header else t.rows)
                prev.page_end = page_no
                prev.text = _table_markdown(prev.rows, prev.has_header)
            else:
                current.blocks.append(
                    Block(
                        "table",
                        _table_markdown(t.rows, t.has_header),
                        page_no,
                        page_no,
                        rows=[list(r) for r in t.rows],
                        has_header=t.has_header,
                    )
                )
            current.page_end = max(current.page_end, page_no)
            i += 1
            continue

        ln: _Line = item  # type: ignore[assignment]
        hid = _heading_id(ln.text) if is_heading_style(ln) else None
        unnumbered_heading = is_heading_style(ln) and hid is None and seen_numbered

        if hid or unnumbered_heading:
            flush_para()
            # A heading may wrap onto several lines of the same style.
            text = ln.text
            j = i + 1
            while j < len(elements) and elements[j][2] == "line":
                nxt: _Line = elements[j][3]  # type: ignore[assignment]
                if (
                    nxt.page == ln.page
                    and nxt.size == ln.size
                    and nxt.bold == ln.bold
                    and nxt.block_no == ln.block_no
                ):
                    text = f"{text} {nxt.text}"
                    j += 1
                else:
                    break
            if hid:
                sid, level = hid
                seen_numbered = True
            else:
                sid, level = "", size_level.get(ln.size, 1)
            while stack and stack[-1].level >= level:
                stack.pop()
            hpath = [s.title for s in stack] + [text]
            current = Section(sid, text, hpath, level, ln.page, ln.page)
            sections.append(current)
            stack.append(current)
            i = j
            continue

        # Body line: new paragraph when the PDF block changes.
        if para and (ln.block_no != para[-1].block_no or ln.page != para[-1].page):
            flush_para()
        para.append(ln)
        i += 1

    flush_para()
    page_count = doc.page_count
    doc.close()

    sections = [s for s in sections if s.blocks or s is not front]
    return ParsedDocument(
        doc_id=doc_id,
        title=title,
        lang=lang,
        source=path.name,
        sha256=sha,
        page_count=page_count,
        sections=sections,
    )
