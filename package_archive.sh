#!/bin/bash
# Package the maintained checkout by default. Optional arguments: SOURCE OUTPUT.zip
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="${1:-$SCRIPT_DIR}"
OUTPUT="${2:-$HOME/Desktop/DonGlendenningArchive.zip}"
if [ ! -f "$SOURCE/index.html" ]; then
    echo "ERROR: Archive index not found in $SOURCE" >&2
    exit 1
fi
mkdir -p "$(dirname "$OUTPUT")"
OUTPUT_DIR="$(cd "$(dirname "$OUTPUT")" && pwd)"
OUTPUT="$OUTPUT_DIR/$(basename "$OUTPUT")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/don-archive-package.XXXXXX")"
OUTPUT_TEMP="$(mktemp "$OUTPUT_DIR/.DonGlendenningArchive.XXXXXX")"
trap 'rm -rf "$WORK"; rm -f "$OUTPUT_TEMP"' EXIT
STAGING="$WORK/DonGlendenningArchive"
mkdir -p "$STAGING"
# Only reader-facing archive files belong in a distribution. Maintenance/review
# data stays in the repository and is never copied into this ZIP.
for entry in index.html search.html excluded.html README.md css js search pagefind Eulogy; do
    if [ -e "$SOURCE/$entry" ]; then
        rsync -a --exclude='.DS_Store' --exclude='._*' "$SOURCE/$entry" "$STAGING/"
    fi
done
for collection in "$SOURCE"/[0-9][0-9]-*/; do
    [ -d "$collection" ] || continue
    rsync -a --exclude='.DS_Store' --exclude='._*' "$collection" "$STAGING/$(basename "$collection")/"
done
cat > "$STAGING/START-HERE.txt" <<'EOF'
Don Glendenning Archive

Open index.html to browse the collections and documents offline.
Full-text search uses browser fetch requests and needs an HTTP server.
If Python 3 is available, open a terminal in this folder and run:

  python3 -m http.server 8000 --bind 127.0.0.1

Then open http://127.0.0.1:8000/ in your browser.
The online archive also provides search:
https://bglenden.github.io/DonGlendenningArchive/
EOF
(cd "$WORK" && zip -r -q archive.zip DonGlendenningArchive)
cp "$WORK/archive.zip" "$OUTPUT_TEMP"
mv -f "$OUTPUT_TEMP" "$OUTPUT"
echo "Packaged maintained archive: $OUTPUT"
echo "Browse index.html offline; use a local HTTP server for search (see START-HERE.txt)."
