"""Logica compartilhada dos executaveis MDtoPDF e PDFtoMD.

Regra combinada com o usuario: tudo que estiver na RAIZ da pasta do
executavel (MDtoPDF/ ou PDFtoMD/) e convertido, e tanto o arquivo
original quanto o resultado da conversao sao movidos para a subpasta de
saida (PDFs/ ou MDs/), deixando a raiz limpa para o proximo lote.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

ConvertFn = Callable[[Path, Path], object]


def process_folder(
    root: Path,
    output_dir: Path,
    source_suffix: str | tuple[str, ...],
    target_suffix: str,
    convert_fn: ConvertFn,
    label: str,
    announce_empty: bool = True,
) -> int:
    """Converte todo arquivo com uma das extensoes em `source_suffix` na
    raiz de `root` (aceita uma unica extensao ou uma tupla de extensoes).

    O arquivo de saida e escrito em `output_dir`, e o arquivo de origem e
    movido para `output_dir` logo apos uma conversao bem-sucedida.
    Retorna quantos arquivos foram convertidos com sucesso.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    suffixes = (source_suffix,) if isinstance(source_suffix, str) else source_suffix
    source_files = sorted(
        p for p in root.iterdir() if p.is_file() and p.suffix.lower() in suffixes
    )

    if not source_files:
        if announce_empty:
            print(f"[{label}] Nenhum arquivo {'/'.join(suffixes)} encontrado em {root}.")
        return 0

    print(f"[{label}] {len(source_files)} arquivo(s) encontrado(s). Convertendo...\n")

    ok, failed = 0, 0
    for src in source_files:
        dest = output_dir / (src.stem + target_suffix)
        dest = avoid_overwrite(dest)
        try:
            info = convert_fn(src, dest)
            moved_src = avoid_overwrite(output_dir / src.name)
            shutil.move(str(src), str(moved_src))
            extra = f" ({info})" if info else ""
            print(f"  OK  {src.name} -> {dest.name}{extra}")
            ok += 1
        except Exception as exc:  # noqa: BLE001 - queremos seguir para o proximo arquivo
            print(f"  ERRO {src.name}: {exc}")
            if dest.exists():
                dest.unlink()  # nao deixa PDF/MD incompleto para tras
            failed += 1

    print(f"\n[{label}] Concluido: {ok} convertido(s), {failed} com erro.")
    return ok


def avoid_overwrite(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
