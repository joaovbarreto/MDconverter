#!/usr/bin/env python3
"""Executavel ALLtoMD.

Como o PDFtoMD, mas aceita varios formatos de entrada em vez de so PDF:
.pdf, .docx, .xlsx, .csv, .html/.htm, .txt e .rtf. Coloque os arquivos na
raiz desta pasta e rode este script (ou de dois cliques em run.bat /
run.sh). Cada arquivo vira um .md e e movido, junto do original, para
MDs/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mdconverter.jobs import run_all_to_md  # noqa: E402

if __name__ == "__main__":
    run_all_to_md()
