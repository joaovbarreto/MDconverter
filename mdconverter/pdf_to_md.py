"""Converte arquivos PDF em Markdown (.md) legivel e compacto.

O objetivo principal e reduzir o consumo de tokens ao enviar o conteudo
para uma LLM, entao priorizamos texto limpo em vez de reproduzir o
layout do PDF pixel a pixel. Usamos o PyMuPDF (fitz) para:

- extrair o texto por blocos, junto do tamanho de fonte de cada trecho;
- inferir titulos (#, ##, ###) comparando o tamanho da fonte com o corpo
  do texto do documento;
- detectar texto em negrito e listas com marcadores;
- extrair tabelas (quando o PyMuPDF consegue identifica-las) e converter
  para tabelas Markdown.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

_BULLET_PREFIXES = ("- ", "* ", "• ", "● ", "▪ ")
_BULLET_ONLY_RE = re.compile(r"^[\-\*•●○▪■❖‣∙·]+$")
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(p[aá]gina|page|pg\.?)?\s*\d{1,4}\s*(/|de|of)?\s*\d{0,4}\s*$",
    re.IGNORECASE,
)
_MONOSPACE_HINTS = ("mono", "courier", "consolas", "menlo", "cascadia")


def _dominant_font_size(doc: "fitz.Document") -> float:
    sizes: Counter[float] = Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip():
                        sizes[round(span["size"], 1)] += len(span["text"])
    if not sizes:
        return 11.0
    return sizes.most_common(1)[0][0]


def _heading_level(size: float, body_size: float) -> int:
    ratio = size / body_size if body_size else 1.0
    if ratio >= 1.7:
        return 1
    if ratio >= 1.4:
        return 2
    if ratio >= 1.15:
        return 3
    return 0


def _line_to_text(line: dict) -> tuple[str, float, bool, bool]:
    """Junta os spans de uma linha e retorna (texto, tamanho_max, negrito, monoespacado)."""
    parts = []
    max_size = 0.0
    bold_chars = 0
    mono_chars = 0
    total_chars = 0
    for span in line["spans"]:
        text = span["text"]
        if not text:
            continue
        max_size = max(max_size, span["size"])
        total_chars += len(text)
        if span["flags"] & 2**4:  # bit de negrito no PyMuPDF
            bold_chars += len(text)
        if any(hint in span.get("font", "").lower() for hint in _MONOSPACE_HINTS):
            mono_chars += len(text)
        parts.append(text)
    text = "".join(parts).strip()
    is_bold = total_chars > 0 and bold_chars / total_chars > 0.6
    is_mono = total_chars > 0 and mono_chars / total_chars > 0.6
    return text, max_size, is_bold, is_mono


def _table_to_markdown(table_rows: list[list[str]]) -> str:
    rows = [[(cell or "").strip().replace("\n", " ") for cell in row] for row in table_rows]
    if not rows:
        return ""
    header, *body = rows
    width = len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in body:
        row = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(row[:width]) + " |")
    return "\n".join(lines)


def _extract_tables(page: "fitz.Page") -> list[tuple[fitz.Rect, str]]:
    tables_out = []
    finder = getattr(page, "find_tables", None)
    if finder is None:
        return tables_out
    try:
        result = finder()
    except Exception:
        return tables_out
    for table in getattr(result, "tables", []):
        try:
            rows = table.extract()
        except Exception:
            continue
        if len(rows) < 2 or len(rows[0]) < 2:
            continue  # provavelmente um falso positivo (linhas/bordas soltas)
        markdown_table = _table_to_markdown(rows)
        if markdown_table:
            tables_out.append((fitz.Rect(table.bbox), markdown_table))
    return tables_out


def _flush_code_buffer(out_lines: list[str], code_buffer: list[str]) -> None:
    if not code_buffer:
        return
    out_lines.append("```")
    out_lines.extend(code_buffer)
    out_lines.append("```")
    code_buffer.clear()


def _page_to_markdown(page: "fitz.Page", body_size: float) -> str:
    tables = _extract_tables(page)
    table_rects = [rect for rect, _ in tables]

    page_height = page.rect.height
    footer_zone = page_height * 0.93
    header_zone = page_height * 0.06

    out_lines: list[str] = []
    code_buffer: list[str] = []
    pending_bullet = False

    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block.get("type") != 0:
            continue
        block_rect = fitz.Rect(block["bbox"])
        if any(block_rect.intersects(rect) for rect in table_rects):
            continue  # sera inserido separadamente, na posicao das tabelas

        for line in block["lines"]:
            text, size, is_bold, is_mono = _line_to_text(line)
            if not text:
                continue

            line_top = line["bbox"][1]
            if (line_top >= footer_zone or line_top <= header_zone) and _PAGE_NUMBER_RE.match(text):
                continue  # provavel numero de pagina / cabecalho repetido

            if _BULLET_ONLY_RE.match(text):
                pending_bullet = True
                continue

            if not is_mono:
                _flush_code_buffer(out_lines, code_buffer)

            level = 0 if is_mono else _heading_level(size, body_size)
            if level:
                out_lines.append(f"\n{'#' * level} {text}\n")
                pending_bullet = False
                continue

            if is_mono:
                code_buffer.append(text)
                continue

            stripped = text.lstrip()
            if pending_bullet or stripped[:2] in _BULLET_PREFIXES or (
                stripped[:1] in ("-", "*") and stripped[1:2] == " "
            ):
                out_lines.append(f"- {stripped.lstrip('-*•●▪ ').strip()}")
                pending_bullet = False
                continue

            if is_bold:
                out_lines.append(f"**{text}**")
            else:
                out_lines.append(text)

    _flush_code_buffer(out_lines, code_buffer)

    # Insere as tabelas ao final do texto da pagina, na ordem em que aparecem.
    for _, table_md in tables:
        out_lines.append("\n" + table_md + "\n")

    return "\n".join(out_lines)


def _merge_paragraphs(raw_lines: str) -> str:
    """Junta linhas soltas em paragrafos, preservando titulos/listas/tabelas/codigo."""
    lines = raw_lines.splitlines()
    paragraphs: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            paragraphs.append(" ".join(buffer).strip())
            buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            code_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                code_lines.append("```")
            paragraphs.append("\n".join(code_lines))
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue
        if stripped.startswith("-"):
            flush()
            list_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("-"):
                list_lines.append(lines[i].strip())
                i += 1
            paragraphs.append("\n".join(list_lines))
            continue
        if stripped.startswith("|"):
            flush()
            table_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            paragraphs.append("\n".join(table_lines))
            continue
        if stripped.startswith("#"):
            flush()
            paragraphs.append(stripped)
            i += 1
            continue
        buffer.append(stripped)
        i += 1
    flush()

    return "\n\n".join(p for p in paragraphs if p)


def extract_markdown(input_path: Path, *, page_separators: bool = False) -> tuple[str, int]:
    """Extrai o Markdown de um PDF. Retorna (texto_markdown, numero_de_paginas).

    Nao inclui titulo de arquivo nem grava nada em disco -- isso fica por
    conta de quem chama (convert_pdf_file ou uma fusao de varios PDFs).
    """
    doc = fitz.open(str(input_path))
    try:
        body_size = _dominant_font_size(doc)
        pages_md = []
        for page in doc:
            raw = _page_to_markdown(page, body_size)
            pages_md.append(_merge_paragraphs(raw))

        separator = "\n\n---\n\n" if page_separators else "\n\n"
        markdown_text = separator.join(p for p in pages_md if p.strip()).strip()
        return markdown_text, doc.page_count
    finally:
        doc.close()


def convert_pdf_file(input_path: Path, output_path: Path, *, page_separators: bool = False) -> int:
    """Converte um PDF em Markdown. Retorna o numero de paginas processadas."""
    markdown_text, page_count = extract_markdown(input_path, page_separators=page_separators)
    if not markdown_text.startswith("# "):
        markdown_text = f"# {input_path.stem}\n\n{markdown_text}"
    markdown_text = markdown_text.strip() + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_text, encoding="utf-8")
    return page_count


def merge_pdfs_to_markdown(input_paths: list[Path], output_path: Path) -> int:
    """Converte varios PDFs e junta tudo em um unico arquivo Markdown.

    Cada PDF vira uma secao "## <nome do arquivo>" dentro do documento
    final, na ordem em que os arquivos forem passados. Retorna o total de
    paginas processadas somando todos os PDFs.
    """
    sections = []
    total_pages = 0
    for path in input_paths:
        markdown_text, page_count = extract_markdown(path)
        total_pages += page_count
        sections.append(f"## {path.stem}\n\n{markdown_text}".strip())

    merged = "# Documentos combinados\n\n" + "\n\n---\n\n".join(sections) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")
    return total_pages
