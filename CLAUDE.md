# Don Glendenning Archive

## What This Is

A browsable HTML archive of the personal writings of **Donald Ernest Malcolm Glendenning** (1929–2025, Black River Bridge, NB) — founding President of Holland College PEI (1969–1987), Order of Canada recipient, DACUM methodology pioneer, and education reformer.

**3,857 documents** organized into 11 thematic collections, with 201 curated highlights and 200 Family Chronicle newsletter issues.

## How to Browse

Open `index.html` in any browser. No server required — everything is static HTML/CSS.

## Archive Structure

```
index.html                    # Main landing page
excluded.html                 # Excluded files list (for auditing)
css/style.css                 # Shared stylesheet
scripts/                      # Post-build enhancement scripts
  add_images.py               # Extract images from source docs via LibreOffice
  image_report.json           # Report from last add_images.py run
01-autobiography/             # Theme directories (01-11)
  index.html                  # Theme index page
  files/                      # Original .doc/.docx/.rtf source files
  read/                       # HTML viewer pages (one per document)
    img/                      # Extracted images (per-document subdirectories)
02-family-chronicle/
  ...
```

Each theme directory contains:
- `index.html` — sortable file listing with summaries and tags
- `files/` — original source documents (downloadable)
- `read/` — HTML viewer pages showing extracted text with metadata
- `read/img/` — extracted images organized by reader page slug (e.g. `img/chronicle-103/img001.png`)

## Theme Categories (11)

1. **Autobiography & Personal Narrative** — Life stories, memoirs
2. **The Family Chronicle** — 200-issue genealogical newsletter (1997–2010)
3. **Family History & Genealogy** — Ancestry research, family trees
4. **Holland College & Institutional Legacy** — Founding presidency
5. **Education Philosophy & Reform** — Education 20/20 advocacy
6. **Speeches & Presentations** — Talks, addresses, remarks
7. **Professional Career & Consulting** — DACUM methodology, international work
8. **Correspondence** — Personal and professional letters
9. **Community Foundation & Civic Life** — CFPEI, civic involvement
10. **Creative Writing** — Poetry, humour, literary works
11. **Personal & Household** — Recipes, health, practical documents

## Images

1,507 reader pages have embedded images (3,911 image files, 422 MB total). Images were extracted from source `.doc`/`.docx`/`.rtf` files using LibreOffice headless conversion (`scripts/add_images.py`). Reader pages with images are marked with `<!-- lo-images -->` in the HTML.

To re-run or update images:
```bash
python3 scripts/add_images.py --workers 4          # All themes
python3 scripts/add_images.py --theme 02-family-chronicle  # One theme
python3 scripts/add_images.py --dry-run             # Preview only
python3 scripts/add_images.py --force               # Re-process already-done pages
```

## Build Pipeline

The archive is built from source files on a USB stick (`/Volumes/Lexar/`). Build scripts live on the USB at `/Volumes/Lexar/_summaries/`:

| Script | Purpose |
|--------|---------|
| `extract_text.py` | Extract text from .doc/.docx/.rtf into SQLite |
| `export_text_files.py` | Export extracted text to hash-bucketed .txt files + create `archive_metadata.db` |
| `generate_missing_summaries.py` | Find unsummarized files, prepare AI batch work |
| `build_archive.py` | Build HTML archive from metadata DB → `/tmp/DonGlendenningArchive/` → USB |
| `review_archive_entries.py` | AI review passes to prune/curate the archive |
| `scripts/add_images.py` | Post-build: extract images from source docs into reader pages |

### Rebuilding

```bash
cd /Volumes/Lexar/_summaries
python3 build_archive.py          # Builds to /tmp/, copies to USB
# Then sync to git repo:
rsync -a --delete /tmp/DonGlendenningArchive/ /path/to/git/repo/ --exclude=.git
# Then add images:
python3 scripts/add_images.py --workers 4
```

### Packaging for Distribution

```bash
./package_archive.sh              # Creates ~/Desktop/DonGlendenningArchive.zip
```

## Key Databases (not in repo)

| Database | Location | Purpose |
|----------|----------|---------|
| `extracted_text.db` | `/tmp/` (working), USB (backup) | Full text extraction (32K+ docs) |
| `archive_metadata.db` | `/tmp/` (working), USB (backup) | Summaries, tags, themes, curation decisions |

## AI Review History

- **Pass 1**: Haiku agents reviewed summaries + 800-char text snippets. Reduced 7,812 → 4,705 files.
- **Pass 2**: Haiku agents reviewed full extracted text (up to 4,000 chars). Reduced 4,705 → 3,857 files. Whitelist protected 342 key files from exclusion.

## Future Improvements

- **Image compression**: The 422 MB of images are uncompressed PNGs from LibreOffice. Converting to JPEG or using PNG optimization (pngquant/optipng) could significantly reduce archive size, especially for photographic content.
