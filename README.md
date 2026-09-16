# MDconverter

Ferramenta local e offline para converter **PDF ⇄ Markdown**, com um
layout de PDF cuidado (tipografia, cores, tabelas, blocos de codigo,
numeracao de pagina).

Motivacao: enviar `.md` para uma LLM consome muito menos tokens do que
enviar `.pdf`, e quando alguem pede um documento "bonito" para ler, e
melhor gerar o `.md` com a LLM e converter para PDF localmente do que
pedir para a LLM tentar gerar o PDF direto.

## Estrutura de pastas

```
MDconverter/
├── MDtoPDF/             <- solte .md aqui e rode o conversor
│   ├── convert.py
│   ├── run.bat / run.sh
│   └── PDFs/             <- saida: PDF gerado + .md original movidos para ca
├── PDFtoMD/              <- solte .pdf aqui e rode o conversor (1 PDF -> 1 .md)
│   ├── convert.py
│   ├── run.bat / run.sh
│   └── MDs/               <- saida: .md gerado + PDF original movidos para ca
├── allPDFtoMD/           <- solte varios .pdf aqui e rode o conversor
│   ├── convert.py         <- junta TODOS os pdfs da raiz em 1 unico .md
│   ├── run.bat / run.sh
│   └── MDs/               <- saida: .md combinado + PDFs originais movidos para ca
├── watch_all.py           <- monitor unico: fica na raiz observando as 3 pastas acima
├── watch_all.bat / .sh
├── mdconverter/           <- pacote com a logica de conversao (compartilhada)
├── requirements.txt
├── install.bat / install.sh
└── build_executables.py   <- opcional: gera .exe/binario standalone
```

Regra fixa: **tudo que estiver na raiz de `MDtoPDF/` ou `PDFtoMD/`** e
convertido quando voce roda o script, e tanto o arquivo original quanto o
resultado vao parar juntos na subpasta de saida (`PDFs/` ou `MDs/`),
deixando a raiz limpa para o proximo lote.

## Instalacao

Requer Python 3.10+.

```bash
# Windows: clique duas vezes em install.bat
# Linux/Mac:
./install.sh
```

Isso instala:
- `Markdown` + `Pygments` — parser de Markdown com tabelas, code blocks, etc.
- `PyMuPDF` — extracao de texto/tabelas do PDF.
- `weasyprint` — motor principal de geracao de PDF (melhor tipografia).
- `xhtml2pdf` — motor de fallback, puro Python, usado automaticamente se o
  WeasyPrint nao conseguir carregar (ex.: falta o runtime do GTK no Windows).

> **Nota Windows/WeasyPrint:** o WeasyPrint depende de bibliotecas nativas
> (Pango/Cairo/GDK-Pixbuf). Se voce nao instalar o
> [GTK runtime](https://weasyprint.readthedocs.io/en/stable/first_steps.html#windows),
> o programa detecta isso automaticamente e usa o `xhtml2pdf` no lugar —
> o layout fica mais simples, mas tudo continua funcionando sem precisar
> instalar nada extra.

## Uso

### Markdown → PDF

1. Coloque arquivos `.md` na raiz de `MDtoPDF/`.
2. Rode `MDtoPDF/run.bat` (Windows) ou `MDtoPDF/run.sh` (Linux/Mac), ou
   `python MDtoPDF/convert.py`.
3. Os PDFs (com layout, tabelas, code blocks e numeracao de pagina) e os
   `.md` originais aparecem em `MDtoPDF/PDFs/`.

### PDF → Markdown (um arquivo por vez)

1. Coloque arquivos `.pdf` na raiz de `PDFtoMD/`.
2. Rode `PDFtoMD/run.bat`, `PDFtoMD/run.sh` ou `python PDFtoMD/convert.py`.
3. Os `.md` (titulos, listas, tabelas e blocos de codigo detectados
   automaticamente) e os `.pdf` originais aparecem em `PDFtoMD/MDs/`.

### Vários PDFs → um único Markdown (allPDFtoMD)

Quando voce quer consolidar varios PDFs relacionados em um so `.md` (por
exemplo, para mandar tudo de uma vez para uma LLM):

1. Coloque os `.pdf` na raiz de `allPDFtoMD/`.
2. Rode `allPDFtoMD/run.bat`, `allPDFtoMD/run.sh` ou
   `python allPDFtoMD/convert.py`.
3. Um unico `combinado_<data>_<hora>.md` e os `.pdf` originais aparecem em
   `allPDFtoMD/MDs/`. Cada PDF vira uma secao `## <nome do arquivo>`
   dentro do Markdown final, na ordem alfabetica dos nomes de arquivo.

### Monitor único (watch_all)

Em vez de entrar em cada pasta e rodar o conversor manualmente, de dois
cliques em `watch_all.bat` (Windows) ou rode `watch_all.sh` /
`python watch_all.py` (Linux/Mac). Ele fica na raiz do projeto,
verificando `MDtoPDF/`, `PDFtoMD/` e `allPDFtoMD/` a cada poucos segundos
e converte automaticamente qualquer arquivo novo que aparecer em alguma
delas — basta jogar os arquivos nas pastas certas e esperar.

```bash
python watch_all.py               # fica rodando, checa a cada 3s (Ctrl+C para parar)
python watch_all.py --once        # roda uma unica passada nas 3 pastas e sai
python watch_all.py --interval 10 # muda o intervalo de checagem
```

### Gerando um executavel standalone (opcional)

Se quiser rodar sem precisar ter Python instalado no dia a dia:

```bash
pip install pyinstaller
python build_executables.py
```

Isso gera `MDtoPDF/MDtoPDF.exe` e `PDFtoMD/PDFtoMD.exe` (ou binarios sem
extensao no Linux/Mac). Precisa ser rodado no mesmo sistema operacional
de destino (o PyInstaller nao faz cross-compilation).

## Limitacoes conhecidas (PDF → Markdown)

A extracao de PDF e heuristica (baseada em tamanho de fonte, negrito e
posicao do texto), entao:

- Titulos sao inferidos comparando o tamanho da fonte com o corpo do
  texto do documento — PDFs com tipografia muito incomum podem sair com
  nivel de titulo errado.
- Listas so sao detectadas quando o PDF realmente embute um caractere de
  marcador (`•`, `-`, etc.) no texto; alguns geradores de PDF desenham o
  marcador apenas como grafico vetorial, sem texto associado, e nesse caso
  o item de lista sai como texto corrido.
- Tabelas sao detectadas automaticamente pelo PyMuPDF; tabelas sem bordas
  visiveis podem nao ser reconhecidas.
- PDFs escaneados (imagem, sem camada de texto) nao sao suportados — seria
  necessario OCR, que nao esta incluido nesta primeira versao.
