#!/usr/bin/env bash
# Fetch IEEE Access class file (ieeeaccess.cls) into this directory.
#
# IEEE distributes class files only from its own channels and frequently
# moves URLs, so this tries the listed URLs, falls back to CTAN, and always
# ends with a clear fix-it instruction instead of a broken bundle.
#
# Usage:
#   ./fetch_ieee_templates.sh            download (best-effort)
#   ./fetch_ieee_templates.sh --check    verify both IEEE files resolve
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK=0
if [[ "${1:-}" == "--check" ]]; then
    CHECK=1
fi

ieee_author_center="https://ieeeauthorcenter.ieee.org/wp-content/uploads/IEEEtran.zip"
ctan_ieeeaccess="https://mirrors.ctan.org/macros/latex/contrib/ieeeaccess.zip"

have_local_cls() {
    [[ -f "$DIR/ieeeaccess.cls" ]]
}

have_texlive_cls() {
    command -v kpsewhich >/dev/null 2>&1 && kpsewhich IEEEtran.cls >/dev/null 2>&1
}

if [[ "$CHECK" -eq 1 ]]; then
    ok=1
    if have_texlive_cls; then
        echo "OK  IEEEtran.cls -> $(kpsewhich IEEEtran.cls)"
    else
        echo "MISSING IEEEtran.cls (install via your TeX distribution)"
        ok=0
    fi
    if have_local_cls; then
        echo "OK  ieeeaccess.cls -> $DIR/ieeeaccess.cls"
    else
        echo "MISSING ieeeaccess.cls (run $0 without --check)"
        ok=0
    fi
    exit $((1 - ok))
fi

if have_local_cls; then
    echo "ieeeaccess.cls already present in $DIR — nothing to do."
    exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fetch_and_extract() {
    local url="$1"
    echo "Trying $url ..."
    if ! curl -fsSL --max-time 60 -o "$tmp/pkg.zip" "$url" 2>/dev/null; then
        echo "  download failed."
        return 1
    fi
    unzip -q -o "$tmp/pkg.zip" -d "$tmp/pkg" 2>/dev/null || return 1
    local found
    found="$(find "$tmp/pkg" -name 'ieeeaccess.cls' -print -quit)"
    if [[ -z "$found" ]]; then
        echo "  archive found, but no ieeeaccess.cls inside."
        return 1
    fi
    cp "$found" "$DIR/ieeeaccess.cls"
    echo "Installed ieeeaccess.cls -> $DIR/ieeeaccess.cls"
    return 0
}

if ! fetch_and_extract "$ctan_ieeeaccess" && ! fetch_and_extract "$ieee_author_center"; then
    echo
    echo "Could not auto-download ieeeaccess.cls. IEEE moves these URLs often;"
    echo "give it to you from: https://ieeeauthorcenter.ieee.org/create-your-ieee-article/"
    echo "use-authoring-tools-and-ieee-article-templates/ and place the file next to this script."
    exit 1
fi

if ! have_texlive_cls; then
    echo
    echo "Note: IEEEtran.cls (needed by both IEEE classes) was not found via kpsewhich."
    echo "Install it with your TeX distribution (e.g. sudo tlmgr install ieeetran)."
fi