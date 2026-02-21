#!/bin/bash
# package_archive.sh - Create a clean distributable zip of the archive.
#
# Usage:
#   ./package_archive.sh                  # builds from /tmp/DonGlendenningArchive
#   ./package_archive.sh /path/to/source  # builds from a custom source path
#
# Output: ~/Desktop/DonGlendenningArchive.zip

set -e

SOURCE="${1:-/tmp/DonGlendenningArchive}"
STAGING="/tmp/_archive_pkg/DonGlendenningArchive"
OUTPUT="$HOME/Desktop/DonGlendenningArchive.zip"

if [ ! -d "$SOURCE" ]; then
    echo "ERROR: Source directory not found: $SOURCE"
    echo "Run build_archive.py first, or pass a custom source path."
    exit 1
fi

echo "=== Packaging Don Glendenning Archive ==="
echo "  Source: $SOURCE"

# Clean staging area
rm -rf /tmp/_archive_pkg
mkdir -p "$STAGING"

echo "  Copying to staging area..."
rsync -a \
    --exclude='.git' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    --exclude='*.py' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='*.db' \
    --exclude='*.sqlite' \
    --exclude='*.log' \
    --exclude='.gitignore' \
    --exclude='CLAUDE.md' \
    --exclude='package_archive.sh' \
    --exclude='scripts/' \
    "$SOURCE/" "$STAGING/"

# Count what we have
FILE_COUNT=$(find "$STAGING" -type f | wc -l | tr -d ' ')
DIR_COUNT=$(find "$STAGING" -type d | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$STAGING" | cut -f1)

echo "  Staged: $FILE_COUNT files in $DIR_COUNT directories ($TOTAL_SIZE)"

# Create zip from parent so top-level dir is DonGlendenningArchive/
rm -f "$OUTPUT"
echo "  Creating zip..."
cd /tmp/_archive_pkg
zip -r -q "$OUTPUT" DonGlendenningArchive/

ZIP_SIZE=$(du -sh "$OUTPUT" | cut -f1)

# Clean up staging
rm -rf /tmp/_archive_pkg

echo ""
echo "=== Done ==="
echo "  Output: $OUTPUT"
echo "  Size:   $ZIP_SIZE"
echo "  Files:  $FILE_COUNT"
echo ""
echo "Recipients can unzip and open index.html in any browser."
