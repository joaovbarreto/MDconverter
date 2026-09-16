#!/usr/bin/env python3
"""Monitor unico do MDconverter.

Fica rodando na raiz do repositorio e observa TODAS as pastas de
conversao (MDtoPDF/, PDFtoMD/, allPDFtoMD/, e quaisquer outras
registradas em mdconverter.jobs.ALL_JOBS), rodando a conversao
automaticamente assim que aparece um arquivo novo -- sem precisar entrar
em cada pasta e rodar o convert.py na mao.

Uso:
    python watch_all.py            # fica rodando, checando a cada 3s
    python watch_all.py --once     # roda uma unica passada e sai
    python watch_all.py --interval 10   # muda o intervalo de checagem
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mdconverter.jobs import ALL_JOBS  # noqa: E402


def run_once() -> int:
    """Roda uma passada em todas as pastas registradas. Retorna o total convertido."""
    return sum(job(announce_empty=True) for job in ALL_JOBS)


def watch(interval: float) -> None:
    print("MDconverter - monitorando MDtoPDF/, PDFtoMD/ e allPDFtoMD/")
    print(f"Checando a cada {interval:.0f}s. Ctrl+C para parar.\n")
    try:
        while True:
            for job in ALL_JOBS:
                job(announce_empty=False)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitor encerrado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor unico do MDconverter.")
    parser.add_argument("--once", action="store_true", help="roda uma unica passada e sai")
    parser.add_argument(
        "--interval", type=float, default=3.0, help="intervalo entre checagens, em segundos (padrao: 3)"
    )
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        watch(args.interval)


if __name__ == "__main__":
    main()
