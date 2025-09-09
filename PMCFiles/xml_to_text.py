"""Convert JATS XML articles (as downloaded from PMC) into plain text files
ready for GraphRAG ingestion.

Usage (run from repo root):
  python3 synthbio_practice/processing/xml_to_text.py \
      --source synthbio_practice/tiny_corpus \
      --dest   synthbio_practice/rag_workspace/input

The script extracts:
  - Article title
  - DOI (if present)
  - Abstract(s)
  - Section titles & paragraphs from the body

Each output .txt file is named after the PMCID (or original filename stem)
and placed in --dest. Existing files are overwritten.

This is intentionally lightweight (stdlib only) so it runs without extra deps.
Refinements (future): figure/legend capture, table text, keyword list, refs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


def clean_cell(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_table(el: ET.Element, table_format: str = "markdown") -> list[str]:
    """Extract a JATS <table> or <table-wrap> into a list of formatted text lines.

    table_format: markdown | tsv | csv
    """
    # Inside table-wrap there may be a label, caption and the table element
    caption_parts = []
    label_el = el.find('.//label')
    if label_el is not None and label_el.text:
        caption_parts.append(clean_cell("".join(label_el.itertext())))
    cap_el = el.find('.//caption')
    if cap_el is not None:
        # Prefer title inside caption if present
        title_el = cap_el.find('.//title')
        if title_el is not None:
            caption_parts.append(clean_cell("".join(title_el.itertext())))
        else:
            caption_parts.append(clean_cell("".join(cap_el.itertext())))

    table_node = el.find('.//table') if el.tag != 'table' else el
    if table_node is None:
        return []

    def row_cells(tr: ET.Element) -> list[str]:
        cells = []
        for cell in list(tr):
            if cell.tag in {"td", "th"}:
                cells.append(clean_cell("".join(cell.itertext())))
        # filter trailing empty cells
        while cells and not cells[-1]:
            cells.pop()
        return cells

    headers: list[str] = []
    thead = table_node.find('thead')
    if thead is not None:
        first_tr = thead.find('tr')
        if first_tr is not None:
            headers = row_cells(first_tr)
    # Sometimes headers are in first tbody row if no thead
    body = table_node.find('tbody')
    body_rows: list[list[str]] = []
    if body is not None:
        for tr in body.findall('tr'):
            cells = row_cells(tr)
            if cells:
                body_rows.append(cells)
    # Basic heuristic: if no thead but first row looks like headers (all short words)
    if not headers and body_rows:
        candidate = body_rows[0]
        if all(len(c) <= 20 for c in candidate):
            headers = candidate
            body_rows = body_rows[1:]

    lines: list[str] = []
    if caption_parts:
        lines.append(f"Table: {' - '.join(caption_parts)}")

    if table_format == 'markdown':
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(['---'] * len(headers)) + " |")
        for row in body_rows:
            # pad row if shorter than headers
            if headers and len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            lines.append("| " + " | ".join(row) + " |")
    else:
        sep = '\t' if table_format == 'tsv' else ','
        if headers:
            lines.append(sep.join(headers))
        for row in body_rows:
            lines.append(sep.join(row))

    lines.append("")  # blank line after table
    return lines


def extract_text(xml_path: Path, table_format: str = "markdown") -> str:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Helper to get concatenated text content of an element
    def text_of(el):
        return "".join(el.itertext()).strip()

    lines: list[str] = []

    # Title
    titles = [text_of(t) for t in root.findall('.//article-title')]
    if titles:
        main_title = max(titles, key=len)
        lines.append(f"Title: {main_title}")

    # DOI
    dois = [t.text.strip() for t in root.findall('.//article-id[@pub-id-type="doi"]') if t.text]
    if dois:
        lines.append(f"DOI: {dois[0]}")

    # PMCID
    pmcids = [t.text.strip() for t in root.findall('.//article-id[@pub-id-type="pmcid"]') if t.text]
    if pmcids:
        lines.append(f"PMCID: {pmcids[0]}")

    # Abstract(s)
    abstracts = root.findall('.//abstract')
    for idx, abs_el in enumerate(abstracts, start=1):
        # Skip graphical or other non-text heavy abstracts by checking for paragraphs
        paras = [text_of(p) for p in abs_el.findall('.//p')]
        if not paras:
            # fallback to whole abstract text
            raw = text_of(abs_el)
            if raw:
                lines.append(f"Abstract {idx}:\n{raw}")
        else:
            lines.append(f"Abstract {idx}:")
            for p in paras:
                if p:
                    lines.append(p)

    # Body sections with inline table handling
    body = root.find('.//body')
    if body is not None:
        # Depth-first over sections to keep original order
        def paragraph_non_table_text(p: ET.Element) -> str:
            parts: list[str] = []
            if p.text:
                parts.append(p.text)
            for sub in p:
                if sub.tag in {'table-wrap', 'table'}:
                    # skip its internal text (will be extracted separately) but keep its tail
                    if sub.tail:
                        parts.append(sub.tail)
                else:
                    parts.append("".join(sub.itertext()))
                    if sub.tail:
                        parts.append(sub.tail)
            text = " ".join(s.strip() for s in parts if s and s.strip())
            # normalize whitespace
            return re.sub(r"\s+", " ", text).strip()

        def walk_sec(sec: ET.Element):
            title_el = sec.find('title')
            if title_el is not None:
                title_text = text_of(title_el)
                if title_text:
                    lines.append(f"## {title_text}")
            for child in list(sec):
                tag = child.tag
                if tag == 'title':
                    continue
                if tag == 'p':
                    # extract nested tables first
                    nested_tables = child.findall('.//table-wrap') + child.findall('.//table')
                    p_txt = paragraph_non_table_text(child)
                    if p_txt:
                        lines.append(p_txt)
                    for nt in nested_tables:
                        lines.extend(extract_table(nt, table_format))
                elif tag in {'table-wrap', 'table'}:
                    lines.extend(extract_table(child, table_format))
                elif tag == 'sec':
                    walk_sec(child)
        for top_sec in body.findall('sec'):
            walk_sec(top_sec)

    content = "\n\n".join(lines).strip() + "\n"

    # Basic cleanup: collapse excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def process_dir(source: Path, dest: Path, table_format: str) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for xml_file in sorted(source.glob('*.xml')):
        try:
            txt = extract_text(xml_file, table_format=table_format)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Failed to parse {xml_file.name}: {e}", file=sys.stderr)
            continue
        # Derive output name
        pmcid_match = re.search(r'(PMC\d+)', xml_file.stem)
        out_name = (pmcid_match.group(1) if pmcid_match else xml_file.stem) + '.txt'
        (dest / out_name).write_text(txt, encoding='utf-8')
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Convert PMC JATS XML to plain text for GraphRAG.")
    parser.add_argument('--source', required=True, type=Path, help='Directory containing .xml files')
    parser.add_argument('--dest', required=True, type=Path, help='Destination directory for .txt outputs')
    parser.add_argument('--table-format', choices=['markdown','tsv','csv'], default='markdown', help='Formatting style for tables (default: markdown)')
    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"Source directory not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    count = process_dir(args.source, args.dest, args.table_format)
    print(f"Converted {count} XML file(s) -> {args.dest}")


if __name__ == '__main__':  # pragma: no cover
    main()
