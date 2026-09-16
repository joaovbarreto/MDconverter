#!/usr/bin/env python3
"""Executavel allPDFtoMD.

Diferente de PDFtoMD (1 PDF -> 1 .md), esta pasta junta TODOS os .pdf que
estiverem na raiz em um unico arquivo Markdown, um atras do outro (cada
PDF vira uma secao "## <nome do arquivo>"). Util para consolidar varios
documentos relacionados antes de mandar para uma LLM.

Coloque os .pdf na raiz desta pasta e rode este script (ou de dois
cliques em run.bat / run.sh). O .md combinado e os .pdf originais sao
movidos para MDs/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mdconverter.jobs import run_all_pdf_to_md  # noqa: E402

if __name__ == "__main__":
    run_all_pdf_to_md()
