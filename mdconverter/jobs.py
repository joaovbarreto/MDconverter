"""Definicoes dos "trabalhos" de conversao.

Cada funcao aqui processa a raiz de uma das pastas (MDtoPDF/, PDFtoMD/,
allPDFtoMD/, ALLtoMD/) e retorna quantos arquivos converteu. Sao usadas
tanto pelos executaveis individuais (`MDtoPDF/convert.py`, etc.) quanto
pelo monitor unico (`watch_all.py`, na raiz do repositorio), que roda
todas elas em loop.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from .all_to_md import SUPPORTED_SUFFIXES as ALL_TO_MD_SUFFIXES
from .all_to_md import convert_any_to_md
from .folder_runner import avoid_overwrite, process_folder
from .md_to_pdf import convert_markdown_file
from .pdf_to_md import convert_pdf_file, merge_pdfs_to_markdown

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_md_to_pdf(announce_empty: bool = True) -> int:
    root = REPO_ROOT / "MDtoPDF"
    return process_folder(
        root=root,
        output_dir=root / "PDFs",
        source_suffix=".md",
        target_suffix=".pdf",
        convert_fn=convert_markdown_file,
        label="MDtoPDF",
        announce_empty=announce_empty,
    )


def run_pdf_to_md(announce_empty: bool = True) -> int:
    root = REPO_ROOT / "PDFtoMD"
    return process_folder(
        root=root,
        output_dir=root / "MDs",
        source_suffix=".pdf",
        target_suffix=".md",
        convert_fn=lambda src, dest: f"{convert_pdf_file(src, dest)} pagina(s)",
        label="PDFtoMD",
        announce_empty=announce_empty,
    )


def run_all_pdf_to_md(announce_empty: bool = True) -> int:
    """Junta todos os .pdf soltos na raiz de allPDFtoMD/ em um unico .md."""
    root = REPO_ROOT / "allPDFtoMD"
    output_dir = root / "MDs"
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdf_files:
        if announce_empty:
            print(f"[allPDFtoMD] Nenhum arquivo .pdf encontrado em {root}.")
        return 0

    print(f"[allPDFtoMD] {len(pdf_files)} arquivo(s) encontrado(s). Juntando em um unico .md...\n")
    for p in pdf_files:
        print(f"  - {p.name}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = avoid_overwrite(output_dir / f"combinado_{timestamp}.md")

    try:
        total_pages = merge_pdfs_to_markdown(pdf_files, dest)
    except Exception as exc:  # noqa: BLE001 - segue sem travar o monitor
        print(f"\n[allPDFtoMD] ERRO ao combinar os PDFs: {exc}")
        if dest.exists():
            dest.unlink()
        return 0

    for src in pdf_files:
        moved = avoid_overwrite(output_dir / src.name)
        shutil.move(str(src), str(moved))

    print(f"\n[allPDFtoMD] Concluido: {dest.name} ({total_pages} pagina(s) no total).")
    return len(pdf_files)


def run_all_to_md(announce_empty: bool = True) -> int:
    """Converte qualquer arquivo suportado (PDF, .docx, .xlsx, .csv, .html,
    .txt, .rtf) solto na raiz de ALLtoMD/ para Markdown, um .md por arquivo.
    """
    root = REPO_ROOT / "ALLtoMD"

    def dispatch(src: Path, dest: Path) -> str:
        if src.suffix.lower() == ".pdf":
            return f"{convert_pdf_file(src, dest)} pagina(s)"
        return convert_any_to_md(src, dest)

    return process_folder(
        root=root,
        output_dir=root / "MDs",
        source_suffix=ALL_TO_MD_SUFFIXES,
        target_suffix=".md",
        convert_fn=dispatch,
        label="ALLtoMD",
        announce_empty=announce_empty,
    )


ALL_JOBS = (run_md_to_pdf, run_pdf_to_md, run_all_pdf_to_md, run_all_to_md)
