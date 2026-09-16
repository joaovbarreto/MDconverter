"""Converte arquivos Markdown (.md) em PDF com um layout bem cuidado.

Estrategia:
1. Markdown -> HTML (com suporte a tabelas, code blocks, listas, etc).
2. HTML + CSS -> PDF.

Para o passo 2 tentamos primeiro o WeasyPrint (melhor tipografia e CSS,
mas depende de bibliotecas nativas como Pango/Cairo -- no Windows exige o
runtime do GTK instalado). Se ele nao estiver disponivel, caimos para o
xhtml2pdf, que e puro Python e sempre funciona, com um resultado mais
simples porem ainda assim organizado.
"""

from __future__ import annotations

import datetime as _dt
import html
from pathlib import Path

import markdown as _markdown

STYLES_DIR = Path(__file__).parent / "styles"
DEFAULT_CSS = STYLES_DIR / "default.css"
FALLBACK_CSS = STYLES_DIR / "fallback.css"

_MD_EXTENSIONS = [
    "extra",  # tabelas, listas de definicao, fenced code, etc.
    "sane_lists",
    "smarty",
    "toc",
    "codehilite",
]

_MD_EXTENSION_CONFIG = {
    "codehilite": {"guess_lang": False, "noclasses": True},
}

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="generator" content="MDconverter">
<meta name="date" content="{date}">
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def _markdown_to_html(markdown_text: str, title: str, css_path: Path) -> str:
    md = _markdown.Markdown(
        extensions=_MD_EXTENSIONS,
        extension_configs=_MD_EXTENSION_CONFIG,
        output_format="html5",
    )
    body_html = md.convert(markdown_text)
    css = css_path.read_text(encoding="utf-8")
    return _HTML_TEMPLATE.format(
        title=html.escape(title),
        css=css,
        date=_dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        body=body_html,
    )


def _guess_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _render_with_weasyprint(html_text: str, output_path: Path) -> None:
    from weasyprint import HTML  # import tardio: dependencia opcional

    HTML(string=html_text, base_url=str(output_path.parent)).write_pdf(str(output_path))


def _render_with_xhtml2pdf(html_text: str, output_path: Path) -> None:
    from xhtml2pdf import pisa  # import tardio: dependencia opcional

    with output_path.open("wb") as f:
        result = pisa.CreatePDF(src=html_text, dest=f)
    if result.err:
        raise RuntimeError(f"xhtml2pdf falhou ao gerar {output_path.name}")


def convert_markdown_file(input_path: Path, output_path: Path) -> str:
    """Converte um arquivo .md em PDF.

    Retorna o nome do motor de renderizacao usado ("weasyprint" ou
    "xhtml2pdf"), util para log/depuracao.
    """
    markdown_text = input_path.read_text(encoding="utf-8")
    title = _guess_title(markdown_text, fallback=input_path.stem)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        html_text = _markdown_to_html(markdown_text, title, DEFAULT_CSS)
        _render_with_weasyprint(html_text, output_path)
        return "weasyprint"
    except Exception:
        html_text = _markdown_to_html(markdown_text, title, FALLBACK_CSS)
        _render_with_xhtml2pdf(html_text, output_path)
        return "xhtml2pdf"
