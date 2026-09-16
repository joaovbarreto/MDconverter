#!/usr/bin/env python3
"""Executavel MDtoPDF.

Coloque arquivos .md na raiz desta pasta e rode este script (ou de dois
cliques em run.bat / run.sh). Cada .md e convertido em PDF e salvo em
PDFs/, e o .md original tambem e movido para PDFs/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mdconverter.jobs import run_md_to_pdf  # noqa: E402

if __name__ == "__main__":
    run_md_to_pdf()
