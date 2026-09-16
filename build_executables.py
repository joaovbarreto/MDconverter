#!/usr/bin/env python3
"""Gera executaveis standalone (.exe no Windows) para quem nao quer ter
Python instalado para usar o MDconverter no dia a dia.

Requer `pip install pyinstaller` e deve ser rodado no mesmo sistema
operacional para o qual voce quer gerar o executavel (o PyInstaller nao
faz cross-compilation).

Uso:
    python build_executables.py

O binario final e copiado para dentro de MDtoPDF/, PDFtoMD/, allPDFtoMD/
e da raiz (watch_all), prontos para uso (basta apagar/ignorar o
convert.py / watch_all.py se preferir usar so o executavel).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = [
    ("MDtoPDF", ROOT / "MDtoPDF" / "convert.py", "MDtoPDF"),
    ("PDFtoMD", ROOT / "PDFtoMD" / "convert.py", "PDFtoMD"),
    ("allPDFtoMD", ROOT / "allPDFtoMD" / "convert.py", "allPDFtoMD"),
    ("watch_all", ROOT / "watch_all.py", "."),
]


def build(name: str, entry_point: Path, dest_dir: Path) -> None:
    print(f"\n=== Gerando executavel para {name} ===")
    work_dir = ROOT / "build" / name
    dist_dir = ROOT / "dist" / name
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        name,
        "--paths",
        str(ROOT),
        "--add-data",
        f"{ROOT / 'mdconverter' / 'styles' / 'default.css'}{';' if sys.platform.startswith('win') else ':'}mdconverter/styles",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(work_dir),
        str(entry_point),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)

    built = dist_dir / (f"{name}.exe" if sys.platform.startswith("win") else name)
    final = dest_dir / built.name
    shutil.copy2(built, final)
    print(f"Executavel pronto em: {final}")


def main() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller nao encontrado. Rode: pip install pyinstaller")

    for name, entry_point, dest in TARGETS:
        build(name, entry_point, ROOT / dest)


if __name__ == "__main__":
    main()
