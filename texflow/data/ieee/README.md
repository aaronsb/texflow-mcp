# IEEE class files

IEEE class files are licensed for distribution only through IEEE's own
channels, so TeXFlow never bundles them. `document_class="ieee-access"`
serializes to `\documentclass{IEEEtran}` + `\usepackage{ieeeaccess}` and
needs both files present here:

- `IEEEtran.cls` — ships with TeX Live (`kpsewhich IEEEtran.cls` to confirm;
  most installs have it). If missing, install via your TeX distribution.
- `ieeeaccess.cls` — **not** in TeX Live; download from the IEEE Author Center
  template page (`https://ieeeauthorcenter.ieee.org/create-your-ieee-article/use-authoring-tools-and-ieee-article-templates/`).

## Fetch script

```bash
./fetch_ieee_templates.sh
```

The script tries in order:

1. IEEE Author Center listed URL for `ieee-access.zip`/`ieeeaccess.cls`.
   IEEE frequently moves these URLs, so on failure read the error and grab
   the current link from the page above.
2. CTAN's `ieeeaccess` package (`https://mirrors.ctan.org/macros/latex/contrib/ieeeaccess.zip`),
   which ships `ieeeaccess.cls`. This is the most reliable source.

The script saves `ieeeaccess.cls` into this directory. Verify with
`./fetch_ieee_templates.sh --check`.

## Verification

```bash
./fetch_ieee_templates.sh --check
```

Exits 0 when both `IEEEtran.cls` (via kpsewhich) and `ieeeaccess.cls` (local)
resolve. The compiler prepends this directory to `TEXINPUTS`, so local files
here override system copies without touching your TeX installation.

`document_class="ieee-conference"` uses only the stock `IEEEtran.cls` and
needs nothing from this directory. IEEE documents compile with the `bibtex`
pass (`IEEEtran.bst` style), not biblatex/biber.