#!/usr/bin/env python3
"""Executavel PDFtoMD.

Coloque arquivos .pdf na raiz desta pasta e rode este script (ou de dois
cliques em run.bat / run.sh). Cada .pdf e convertido em Markdown e salvo
em MDs/, e o .pdf original tambem e movido para MDs/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mdconverter.jobs import run_pdf_to_md  # noqa: E402

if __name__ == "__main__":
    run_pdf_to_md()
