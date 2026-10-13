"""Converte arquivos PDF em Markdown (.md) legivel e compacto.

O objetivo principal e reduzir o consumo de tokens ao enviar o conteudo
para uma LLM, entao priorizamos texto limpo em vez de reproduzir o
layout do PDF pixel a pixel. Usamos o PyMuPDF para:

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

import pymupdf

_BULLET_PREFIXES = ("- ", "* ", "• ", "● ", "▪ ", "◦ ", "○ ", "▫ ")
_BULLET_ONLY_RE = re.compile(r"^[\-\*•●○◦▪▫■❖‣∙·]+$")
_BULLET_STRIP_CHARS = "-*•●○◦▪▫ "
_ORDERED_LIST_RE = re.compile(r"^(\d{1,3})[.)]\s+(.*)$")
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(p[aá]gina|page|pg\.?)?\s*\d{1,4}\s*(/|de|of)?\s*\d{0,4}\s*$",
    re.IGNORECASE,
)
_MONOSPACE_HINTS = ("mono", "courier", "consolas", "menlo", "cascadia")


def _dominant_font_size(doc: "pymupdf.Document") -> float:
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


def _extract_tables(page: "pymupdf.Page") -> list[tuple[pymupdf.Rect, str]]:
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
            tables_out.append((pymupdf.Rect(table.bbox), markdown_table))
    return tables_out


def _flush_code_buffer(out_lines: list[str], code_buffer: list[str]) -> None:
    if not code_buffer:
        return
    out_lines.append("```")
    out_lines.extend(code_buffer)
    out_lines.append("```")
    code_buffer.clear()


def _page_to_markdown(page: "pymupdf.Page", body_size: float) -> str:
    tables = _extract_tables(page)
    table_rects = [rect for rect, _ in tables]

    page_height = page.rect.height
    footer_zone = page_height * 0.93
    header_zone = page_height * 0.06

    # Junta linhas de texto e tabelas num unico fluxo de eventos ordenado
    # pela posicao vertical, para que as tabelas apareçam no meio do texto
    # (onde estavam no PDF) em vez de sempre irem parar no final da pagina.
    events: list[tuple[float, int, str, object]] = []
    for table_rect, table_md in tables:
        events.append((table_rect.y0, 0, "table", table_md))

    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block.get("type") != 0:
            continue
        block_rect = pymupdf.Rect(block["bbox"])
        if any(block_rect.intersects(rect) for rect in table_rects):
            continue  # sera inserida como evento "table" separadamente

        for line in block["lines"]:
            text, size, is_bold, is_mono = _line_to_text(line)
            if not text:
                continue
            events.append((line["bbox"][1], 1, "line", (text, size, is_bold, is_mono, line["bbox"][0])))

    events.sort(key=lambda e: (e[0], e[1]))

    out_lines: list[str] = []
    code_buffer: list[str] = []
    pending_bullet = False
    code_base_x0: float | None = None
    list_stack: list[float] = []  # x0 de cada nivel de lista ativo

    def list_indent(x0: float) -> str:
        while list_stack and x0 < list_stack[-1] - 2:
            list_stack.pop()
        if not list_stack or x0 > list_stack[-1] + 2:
            list_stack.append(x0)
        return "  " * (len(list_stack) - 1)

    for y0, _, kind, payload in events:
        if kind == "table":
            _flush_code_buffer(out_lines, code_buffer)
            code_base_x0 = None
            pending_bullet = False
            list_stack = []
            out_lines.append("\n" + payload + "\n")
            continue

        text, size, is_bold, is_mono, x0 = payload

        if (y0 >= footer_zone or y0 <= header_zone) and _PAGE_NUMBER_RE.match(text):
            continue  # provavel numero de pagina / cabecalho repetido

        if _BULLET_ONLY_RE.match(text):
            pending_bullet = True
            continue

        if not is_mono:
            _flush_code_buffer(out_lines, code_buffer)
            code_base_x0 = None

        heading_lvl = 0 if is_mono else _heading_level(size, body_size)
        if heading_lvl:
            out_lines.append(f"\n{'#' * heading_lvl} {text}\n")
            pending_bullet = False
            list_stack = []
            continue

        if is_mono:
            if code_base_x0 is None:
                code_base_x0 = x0
            char_width = max(size * 0.55, 1.0)
            indent = max(0, round((x0 - code_base_x0) / char_width))
            code_buffer.append(" " * indent + text)
            continue

        stripped = text.lstrip()
        ordered_match = _ORDERED_LIST_RE.match(stripped)
        if ordered_match:
            num, rest = ordered_match.groups()
            out_lines.append(f"{list_indent(x0)}{num}. {rest.strip()}")
            pending_bullet = False
            continue

        if pending_bullet or stripped[:2] in _BULLET_PREFIXES or (
            stripped[:1] in ("-", "*") and stripped[1:2] == " "
        ):
            out_lines.append(f"{list_indent(x0)}- {stripped.lstrip(_BULLET_STRIP_CHARS).strip()}")
            pending_bullet = False
            continue

        list_stack = []
        if is_bold:
            out_lines.append(f"**{text}**")
        else:
            out_lines.append(text)

    _flush_code_buffer(out_lines, code_buffer)

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
        if stripped.startswith("-") or _ORDERED_LIST_RE.match(stripped):
            flush()
            list_lines = [line.rstrip()]
            i += 1
            while i < len(lines) and (
                lines[i].strip().startswith("-") or _ORDERED_LIST_RE.match(lines[i].strip())
            ):
                list_lines.append(lines[i].rstrip())
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
    doc = pymupdf.open(str(input_path))
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
        try:
            markdown_text, page_count = extract_markdown(path)
        except Exception as exc:  # noqa: BLE001 - um PDF ruim nao deve travar o lote inteiro
            sections.append(f"## {path.stem}\n\n_Nao foi possivel converter este arquivo: {exc}_")
            continue
        total_pages += page_count
        sections.append(f"## {path.stem}\n\n{markdown_text}".strip())

    merged = "# Documentos combinados\n\n" + "\n\n---\n\n".join(sections) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")
    return total_pages
