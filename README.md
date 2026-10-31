# The Papers of Don Glendenning

A browsable HTML archive of the personal writings of **Donald Ernest Malcolm Glendenning, C.M., Ph.D.** (1929–2026) — founding President of Holland College PEI (1969–1987), Order of Canada recipient, DACUM methodology pioneer, and education reformer.

**3,695 catalog entries** in 11 primary collections, plus a Letters to the Editor cross-reference collection. There are 195 highlights and 200 Family Chronicle newsletter issues.

## Browse Online

**[bglenden.github.io/DonGlendenningArchive](https://bglenden.github.io/DonGlendenningArchive/)**

Or open `index.html` locally in any browser — no server or internet connection required.

Each collection has a searchable index page with document summaries. Click **Read** to view a document's extracted text inline, or **Download** to get the original file.

Items marked **HIGH** relevance are especially meaningful for understanding Don's life and legacy.

## Collections

| # | Collection | Documents | Description |
|---|-----------|-----------|-------------|
| 01 | Autobiography & Personal Narrative | 28 | Life stories, memoirs, and personal anecdotes |
| 02 | The Family Chronicle | 200 | Self-published genealogical newsletter — 200 issues, 1997–2010 |
| 03 | Family History & Genealogy | 210 | Ancestry research, family trees, and Christmas letters |
| 04 | Holland College & Institutional Legacy | 186 | Founding, presidency, innovations, and institutional history |
| 05 | Education Philosophy & Reform | 1,748 | Letters to editor, Education 20/20, advocacy for educational change |
| 06 | Speeches & Presentations | 130 | Talks, addresses, ceremony remarks, and formal presentations |
| 07 | Professional Career & Consulting | 795 | DACUM methodology, international consulting, and career documents |
| 08 | Correspondence | 9 | Personal and professional letters |
| 09 | Community Foundation & Civic Life | 220 | CFPEI, community involvement, and civic engagement |
| 10 | Creative Writing | 94 | Poetry, humour, literary works, and personal reflections |
| 11 | Personal & Household | 75 | Recipes, practical documents, and everyday life |

The catalog includes 3,638 reading pages and 51 download-only entries. Six pairs of originals share a reading page; those pages identify both original downloads. Letters to the Editor repeats 88 entries from the primary collections and is not added to the overall total.

## Recovered illustrated book

[Read The Neighbourhood](03-family-genealogy/read/the-neighbourhood.html) or [download the illustrated PDF](03-family-genealogy/files/The%20Neighbourhood%20-%20illustrated%20edition.pdf) (403 pages, 20.75 MB).

This October 2026 reconstruction uses Don's September 2015 Family Tree Maker project and 50 recovered source images. The import-message section includes an explanation of the reconstruction and its limitations. It preserves the recovered prose and section order in a new layout; it is not a facsimile of the earlier printed edition.

## About Don Glendenning

Don Glendenning grew up in Black River Bridge, New Brunswick. He founded Holland College in Prince Edward Island in 1969 and served as its President until 1987, building it into one of Canada's most innovative community colleges. He developed the DACUM (Developing A Curriculum) methodology — a competency-based approach to curriculum design now used internationally. He received the Order of Canada and spent his later years advocating for education reform on PEI through his Education 20/20 initiative.

## License

This archive is a family project preserving Don Glendenning's personal papers for historical and educational purposes.

## Search and maintenance

Search puts exact and close title matches first, supports both neighbourhood/neighborhood spellings, and then uses the existing Pagefind full-text ranking. Collection selections are combined with OR (either selected collection). Download-only entries are searchable by title. Original documents and existing reader URLs are preserved.

Run `npm test` to check title ranking, collection filters, source links, images, accessible collection controls, and catalog totals. After changing document content, run `npm run build:search` (pinned Pagefind 1.4.0), then `npm test`. These commands operate on this maintained checkout; the old USB import is not the current source of truth.

`./package_archive.sh` packages this checkout to `~/Desktop/DonGlendenningArchive.zip`. Optional arguments specify a source directory and output ZIP. Packages contain reader-facing archive files and omit maintenance/review work files. Unzip and open `index.html` for browsing; full-text search needs HTTP. For local search, run `python3 -m http.server 8000 --bind 127.0.0.1` in the unzipped directory, then visit `http://127.0.0.1:8000/`.
