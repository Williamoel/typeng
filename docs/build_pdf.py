"""Render docs/dictionary_setup.zh-CN.md into a Chinese PDF (词典安装指南.pdf).

This is a lightweight Markdown-subset renderer aimed only at the dictionary
setup guide: headings (#/##/###), paragraphs, bullet lists, tables, code/quote
blocks, and horizontal rules. It uses fpdf2 with a CJK-capable TrueType font.

Usage:
    python docs/build_pdf.py [output.pdf]

Font resolution order (first that exists wins):
    1. $TYPENG_PDF_FONT
    2. bundled docs/fonts/*.ttf
    3. common Linux Noto/WenQuanYi paths
    4. Windows fonts (incl. WSL /mnt/c) - SimHei / MSYH
Falls back with a clear error if no CJK font is found.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from fpdf import FPDF

DOC_DIR = Path(__file__).resolve().parent
SOURCE_MD = DOC_DIR / "dictionary_setup.zh-CN.md"

FONT_CANDIDATES = [
    os.environ.get("TYPENG_PDF_FONT", ""),
    *[str(p) for p in DOC_DIR.glob("fonts/*.ttf")],
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/mnt/c/Windows/Fonts/simhei.ttf",
    "/mnt/c/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]


def find_font() -> str:
    for candidate in FONT_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit(
        "No CJK font found. Set TYPENG_PDF_FONT to a .ttf/.ttc with Chinese "
        "glyphs, or drop one into docs/fonts/."
    )


def strip_inline(text: str) -> str:
    """Reduce inline markdown to plain text for the PDF body."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"`(.+?)`", r"\1", text)  # inline code
    # [label](url) -> label (url)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1 (\2)", text)
    return text


class GuidePDF(FPDF):
    def __init__(self, font_path: str):
        super().__init__(format="A4")
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(18, 16, 18)
        self.add_font("cjk", "", font_path)
        self.add_page()

    def _full_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def heading(self, level: int, text: str):
        sizes = {1: 20, 2: 15, 3: 13}
        self.ln(3 if self.get_y() > 20 else 0)
        self.set_x(self.l_margin)
        self.set_font("cjk", size=sizes.get(level, 12))
        self.multi_cell(self._full_width(), sizes.get(level, 12) * 0.7 + 4, text,
                        new_x="LMARGIN", new_y="NEXT")
        if level == 1:
            y = self.get_y() + 1
            self.line(18, y, 192, y)
        self.ln(2)

    def paragraph(self, text: str):
        self.set_font("cjk", size=11)
        self.set_x(self.l_margin)
        self.multi_cell(self._full_width(), 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def bullet(self, text: str, indent: int = 0):
        self.set_font("cjk", size=11)
        x = self.l_margin + indent * 6
        self.set_x(x)
        self.multi_cell(self._full_width() - indent * 6, 7, f"■  {text}",
                        new_x="LMARGIN", new_y="NEXT")

    def mono_block(self, lines: list[str]):
        self.set_font("cjk", size=9)
        self.set_fill_color(244, 246, 249)
        width = self.w - self.l_margin - self.r_margin
        for line in lines:
            self.set_x(self.l_margin)
            self.multi_cell(width, 5.5, line if line else " ", fill=True,
                            new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def table(self, rows: list[list[str]]):
        self.set_font("cjk", size=9.5)
        col_count = max(len(r) for r in rows)
        usable = 174
        widths = [usable / col_count] * col_count
        for ri, row in enumerate(rows):
            # compute row height by wrapping each cell
            self.set_fill_color(235, 240, 246) if ri == 0 else self.set_fill_color(255, 255, 255)
            line_h = 5.5
            # measure lines per cell
            heights = []
            for ci in range(col_count):
                cell = row[ci] if ci < len(row) else ""
                n = max(1, len(self.multi_cell(widths[ci], line_h, cell, dry_run=True, output="LINES")))
                heights.append(n)
            row_h = max(heights) * line_h
            x0 = 18
            y0 = self.get_y()
            if y0 + row_h > self.h - 16:
                self.add_page()
                y0 = self.get_y()
            for ci in range(col_count):
                cell = row[ci] if ci < len(row) else ""
                self.set_xy(x0, y0)
                self.multi_cell(widths[ci], line_h, cell, border=1, fill=(ri == 0),
                                max_line_height=line_h)
                x0 += widths[ci]
            self.set_xy(18, y0 + row_h)
        self.ln(2)


def parse_table(block: list[str]) -> list[list[str]]:
    rows = []
    for line in block:
        cells = [strip_inline(c.strip()) for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    # drop the |---|---| separator row
    return [r for r in rows if not all(re.fullmatch(r"-{2,}|:?-+:?", c or "-") for c in r)]


def render(md_path: Path, out_path: Path, font_path: str):
    pdf = GuidePDF(font_path)
    lines = md_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # code / fenced block
        if stripped.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            pdf.mono_block(block)
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}", stripped):
            y = pdf.get_y() + 1
            pdf.set_draw_color(200, 200, 200)
            pdf.line(18, y, 192, y)
            pdf.set_draw_color(0, 0, 0)
            pdf.ln(4)
            i += 1
            continue

        # table (a line with | that is followed by a |---| separator)
        if stripped.startswith("|") and i + 1 < len(lines) and re.search(r"\|\s*:?-{2,}", lines[i + 1]):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            pdf.table(parse_table(block))
            continue

        # headings
        m = re.match(r"(#{1,3})\s+(.*)", stripped)
        if m:
            pdf.heading(len(m.group(1)), strip_inline(m.group(2)))
            i += 1
            continue

        # bullets (support one level of nesting by leading spaces)
        m = re.match(r"^(\s*)[-*]\s+(.*)", line)
        if m:
            indent = len(m.group(1)) // 2
            pdf.bullet(strip_inline(m.group(2)), indent=indent)
            i += 1
            continue

        # quote
        if stripped.startswith(">"):
            pdf.set_text_color(90, 90, 90)
            pdf.paragraph(strip_inline(stripped.lstrip("> ").strip()))
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        # ordered list item -> keep the number
        m = re.match(r"^(\s*)(\d+)\.\s+(.*)", line)
        if m:
            indent = len(m.group(1)) // 2
            pdf.set_font("cjk", size=11)
            x = pdf.l_margin + indent * 6
            pdf.set_x(x)
            pdf.multi_cell(pdf._full_width() - indent * 6, 7,
                           f"{m.group(2)}.  {strip_inline(m.group(3))}",
                           new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # default paragraph
        pdf.paragraph(strip_inline(stripped))
        i += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    print(f"Wrote {out_path} ({out_path.stat().st_size // 1024} KB) using font {font_path}")


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DOC_DIR / "词典安装指南.pdf"
    render(SOURCE_MD, out, find_font())


if __name__ == "__main__":
    main()
