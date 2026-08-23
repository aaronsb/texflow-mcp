# IEEE class files

IEEE class files are licensed for distribution only through IEEE's own
channels, so TeXFlow never bundles them. `document_class="ieee-access"`
serializes to `\documentclass{ieeeaccess}` and needs two things:

- `IEEEtran.cls` — ships with TeX Live (`kpsewhich IEEEtran.cls` to confirm;
  most installs have it). If missing, install via your TeX distribution
  (`texlive-publishers` on Arch/Debian, `texlive-collection-publishers` on
  Fedora).
- `ieeeaccess.cls` + supporting assets — **not** in TeX Live; download from
  the IEEE Access template page with the fetch script below.

`ieeeaccess.cls` is a **pdfLaTeX-only** class: its `spotcolor.sty` uses pdfTeX
primitives (`\pdfobj`) and crashes under XeLaTeX. TeXFlow automatically
compiles `ieee-access` documents with pdflatex and reports an error if
pdflatex is unavailable.

## Fetch script

```bash
./fetch_ieee_templates.sh
```

Downloads the official IEEE Access template zip
(`https://ieeeaccess.ieee.org/wp-content/uploads/2026/05/ACCESS_latex_template_20260513-1-1.zip`)
and installs into this directory:

- `ieeeaccess.cls` and `spotcolor.sty`
- the template's own fonts (`t1-formata*`, `t1-giovannistd*`, their `.fd`
  files and font maps) — the class `\RequirePackage`s these at `\usepackage`
  time and via `\EOD`
- the header logos (`logo.png`, `notaglinelogo.png`, `bullet.png`)

IEEE moves these URLs frequently, so on failure read the error and grab the
current link from `https://ieeeaccess.ieee.org/guide-for-authors/`, then
place the files next to this script.

## Verification

```bash
./fetch_ieee_templates.sh --check
```

Exits 0 when both `IEEEtran.cls` (via kpsewhich) and `ieeeaccess.cls` (local)
resolve. The compiler prepends this directory to `TEXINPUTS`, `TEXFONTS`, and
`FONTMAP`, so local files here override system copies without touching your
TeX installation.

`document_class="ieee-conference"` uses only the stock `IEEEtran.cls` and
needs nothing from this directory. IEEE documents compile with the `bibtex`
pass (`IEEEtran.bst` style), not biblatex/biber.
