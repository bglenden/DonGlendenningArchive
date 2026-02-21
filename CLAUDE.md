# Don Glendenning Archive — Developer Guide

Instructions for maintaining, updating, and regenerating the archive. See `README.md` for user-facing information.

## Archive Structure

```
index.html                    # Main landing page (3,612 documents, 11 themes)
excluded.html                 # Excluded files list (for auditing)
css/style.css                 # Shared stylesheet
scripts/                      # Maintenance and build scripts
01-autobiography/             # Theme directories (01 through 11)
  index.html                  # Searchable theme index with summaries
  files/                      # Original .doc/.docx/.rtf source files
  read/                       # HTML reader pages (one per document)
    img/                      # Extracted images (per-document subdirectories)
```

## Theme Index Page Format

Each `{theme}/index.html` has:
- A `<div class="stats-bar">` with three `<span class="stat-num">` values: document count, highlights count, files count
- A `<table class="file-table">` with `<tbody>` containing one `<tr>` per document
- Highlighted rows have `data-highlight="true"` attribute
- Each row links to `read/{slug}.html` for reading and `files/{filename}` for download
- A search box and highlights filter with JavaScript at the bottom

**Exception**: Theme 02 (Family Chronicle) uses "issues" instead of "documents" in its stats bar.

## Root index.html Format

- Global stats bar: `<span class="stat-num">N</span> documents archived`
- Theme cards: `<div class="count">N documents · M highlights</div>`
- The global document count must equal the sum of all theme card counts

## Reader Pages

Each `read/{slug}.html` contains:
- Document metadata (title, date, tags, summary)
- Extracted text content
- A `<a class="file-link-btn" href="../files/{filename}">` link to the original source file
- Embedded images (if extracted) marked with `<!-- lo-images -->` comment

## Scripts in This Repo

| Script | Purpose |
|--------|---------|
| `scripts/add_images.py` | Extract images from source .doc/.docx/.rtf into reader pages via LibreOffice |
| `scripts/remove_exclusions.py` | Remove documents from archive given an `exclusions.json` file |
| `scripts/generate_review.py` | Generate review HTML from flag files in `scripts/review_data/` |
| `scripts/prep_review_pass2.py` | Prepare compact data chunks for AI review agents |
| `scripts/extract_for_review.py` | Extract document data for review passes |

### Extracting Images

Requires LibreOffice installed. Extracts images from source documents into reader pages.

```bash
python3 scripts/add_images.py --workers 4          # All themes, 4 parallel workers
python3 scripts/add_images.py --theme 02-family-chronicle  # Single theme
python3 scripts/add_images.py --dry-run             # Preview only
python3 scripts/add_images.py --force               # Re-process already-done pages
```

### Removing Documents

To remove documents from the archive (reader pages, source files, images, index listings):

1. Create an `exclusions.json` file — an array of `{"slug": "...", "theme": "..."}` objects
2. Run: `python3 scripts/remove_exclusions.py exclusions.json`
3. The script deletes files, updates all index page counts, and runs an audit

## Build Pipeline (USB Stick)

The archive is built from source files on a USB stick (`/Volumes/Lexar/`). Build scripts live at `/Volumes/Lexar/_summaries/`:

| Script | Purpose |
|--------|---------|
| `extract_text.py` | Extract text from .doc/.docx/.rtf into SQLite (`extracted_text.db`) |
| `export_text_files.py` | Export text to hash-bucketed .txt files + create `archive_metadata.db` |
| `generate_missing_summaries.py` | Find unsummarized files, prepare AI batch summaries |
| `build_archive.py` | Build HTML archive from metadata DB → `/tmp/DonGlendenningArchive/` |
| `review_archive_entries.py` | AI review passes to prune/curate the archive |

### Full Rebuild

```bash
cd /Volumes/Lexar/_summaries
python3 build_archive.py          # Builds to /tmp/DonGlendenningArchive/
# Sync to git repo:
rsync -a --delete /tmp/DonGlendenningArchive/ /path/to/git/repo/ --exclude=.git --exclude=CLAUDE.md --exclude=README.md
# Add images:
cd /path/to/git/repo
python3 scripts/add_images.py --workers 4
```

### Packaging for Distribution

```bash
./package_archive.sh              # Creates ~/Desktop/DonGlendenningArchive.zip (~1 GB)
```

## Key Databases (not in repo)

| Database | Location | Purpose |
|----------|----------|---------|
| `extracted_text.db` | USB stick (`/Volumes/Lexar/`) | Full text extraction from 32K+ source documents (5.8 GB) |
| `archive_metadata.db` | USB stick | Summaries, tags, themes, curation decisions |

## AI Review History

Three review passes have been performed:

1. **Pass 1**: Haiku agents reviewed summaries + 800-char text snippets. Reduced 7,812 → 4,705 files.
2. **Pass 2**: Haiku agents reviewed full extracted text (up to 4,000 chars). Reduced 4,705 → 3,857 files. A whitelist protected 342 key files from exclusion.
3. **Pass 3**: 15 Haiku agents reviewed for privacy/sensitive content and low archival value. Flagged 264 documents, of which 245 were confirmed for removal. Reduced 3,857 → 3,612 files.

Review data (flags, input chunks) is stored in `scripts/review_data/`.

## Future Improvements

- **Image compression**: The extracted images are uncompressed PNGs from LibreOffice. Converting to JPEG or using pngquant/optipng could significantly reduce archive size.
- **GitHub Pages**: The repo can be hosted publicly via GitHub Pages (Settings → Pages → Deploy from main branch).
