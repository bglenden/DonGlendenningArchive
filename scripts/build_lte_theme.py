#!/usr/bin/env python3
"""Build a 'Letters to the Editor' cross-reference theme.

Scans all theme index pages for documents whose summaries indicate they are
letters to the editor, then creates a new theme 12 index page linking back
to the original reader pages in their source themes.
"""

import re
from pathlib import Path
from html import unescape

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent

# Patterns that indicate a letter to the editor (case-insensitive)
INCLUDE_PATTERNS = [
    r'letter to the editor',
    r'letter to editor',
    r'letter to the (?:charlottetown )?guardian',
    r'letter to the journal.?pioneer',
    r'letter to the moncton times',
    r'letter to editors',
    r'guardian letter',
    r'published letter',
    r'opinion letter',
    r'editor letter',
    r"editor'?s letter",
    r'open letter to (?:the )?guardian',
    r'letter (?:penned |submitted )?to (?:the )?(?:charlottetown )?guardian',
    r'dear editor',
    r'opinion piece for (?:the )?guardian',
]

# Patterns that should exclude a match (institutional letters, not LTEs)
EXCLUDE_PATTERNS = [
    r'letter to (?:the )?upei',
    r'letter to (?:the )?westwood',
    r'letter (?:to|from) .{0,30}(?:mla|minister|premier|foundation|rotary)',
    r'award letter',
    r'fundraising letter',
    r'table of contents',
    r'planning.{0,20}outline',
    r'topics for (?:potential |future )?letters',
]

# Near-duplicate slugs to exclude (keep the best version of each cluster)
DEDUP_EXCLUDE = {
    ('04-holland-college', 'intro'),          # dup of 05/2-intro (shorter)
    ('07-professional-career', 'clarity-4-docx'),  # dup of 05/clarity-7-docx
    ('05-education-reform', 'd-clarity-1-docx'),   # shorter draft of clarity-7
}

COMPILED_INCLUDE = re.compile('|'.join(INCLUDE_PATTERNS), re.IGNORECASE)
COMPILED_EXCLUDE = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)


def extract_rows_from_index(index_path):
    """Extract document rows from a theme index page."""
    html = index_path.read_text(encoding='utf-8', errors='replace')
    theme = index_path.parent.name

    tbody_start = html.find('<tbody>')
    tbody_end = html.find('</tbody>')
    if tbody_start == -1 or tbody_end == -1:
        return []

    tbody = html[tbody_start:tbody_end]
    rows = re.findall(r'<tr(?:\s[^>]*)?>.*?</tr>', tbody, re.DOTALL)

    results = []
    for row in rows:
        # Extract slug from read link
        slug_m = re.search(r'href="read/([^"]+)\.html"', row)
        if not slug_m:
            continue
        slug = slug_m.group(1)

        # Extract date
        date_m = re.search(r'<td class="date-col">([^<]*)</td>', row)
        date = date_m.group(1).strip() if date_m else 'Undated'

        # Extract title (second td)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        title = tds[1].strip() if len(tds) > 1 else slug

        # Extract full summary text (short + full)
        summary = ''
        short_m = re.search(r'<span class="short-summary">(.*?)</span>', row, re.DOTALL)
        full_m = re.search(r'<div class="full-summary"[^>]*>(.*?)</div>', row, re.DOTALL)
        if short_m:
            summary += unescape(short_m.group(1))
        if full_m:
            summary += ' ' + unescape(full_m.group(1))

        # Also check title for "Dear Editor" pattern
        full_text = summary + ' ' + title

        # Check highlight status
        is_highlight = 'data-highlight="true"' in row

        # Extract download link
        dl_m = re.search(r'href="files/([^"]+)"', row)
        download = dl_m.group(1) if dl_m else None

        results.append({
            'slug': slug,
            'theme': theme,
            'title': title,
            'date': date,
            'summary_text': full_text,
            'short_summary': unescape(short_m.group(1)) if short_m else '',
            'full_summary': unescape(re.sub(r'<[^>]+>', '', full_m.group(1))) if full_m else '',
            'is_highlight': is_highlight,
            'download': download,
            'original_row': row,
        })

    return results


def is_letter_to_editor(doc):
    """Check if a document is a letter to the editor based on summary text."""
    if (doc['theme'], doc['slug']) in DEDUP_EXCLUDE:
        return False
    text = doc['summary_text']
    if COMPILED_INCLUDE.search(text):
        if not COMPILED_EXCLUDE.search(text):
            return True
    return False


def build_index_html(letters):
    """Build the theme 12 index page HTML."""
    n_docs = len(letters)
    n_highlights = sum(1 for l in letters if l['is_highlight'])

    rows = []
    for doc in letters:
        hl_attr = ' data-highlight="true"' if doc['is_highlight'] else ''
        read_link = f'../{doc["theme"]}/read/{doc["slug"]}.html'

        # Build download link
        dl_html = ''
        if doc['download']:
            dl_link = f'../{doc["theme"]}/files/{doc["download"]}'
            dl_html = f' · <a href="{dl_link}">Download</a>'

        # Build summary cell
        short = doc['short_summary']
        full = doc['full_summary']
        if full and len(full) > len(short):
            summary_cell = (
                f'<span class="short-summary">{short}</span> '
                f'<span class="expand-btn" onclick="toggleRow(this)">▸ more</span>'
                f'<div class="full-summary" style="display:none">{full}'
                f'<div class="expanded-file"><a href="{read_link}">Read</a>{dl_html}</div>'
                f'</div>'
            )
        else:
            summary_cell = short

        rows.append(
            f'<tr{hl_attr}>\n'
            f'  <td class="date-col">{doc["date"]}</td>\n'
            f'  <td>{doc["title"]}</td>\n'
            f'  <td>{summary_cell}</td>\n'
            f'  <td><a href="{read_link}">Read</a>{dl_html}</td>\n'
            f'</tr>'
        )

    tbody = '\n'.join(rows)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Letters to the Editor – Don Glendenning Archive</title>
<link rel="stylesheet" href="../css/style.css">
</head>
<body data-pagefind-ignore>

<header class="site-header">
  <h1>Letters to the Editor</h1>
  <div class="subtitle">Published letters and opinion pieces, primarily in the Charlottetown Guardian</div>
</header>

<div class="container">

<div class="breadcrumb">
  <a href="../index.html">Home</a> <span class="sep">›</span> Letters to the Editor
</div>

<div class="stats-bar">
  <div><span class="stat-num">{n_docs}</span> documents</div>
  <div><span class="stat-num">{n_highlights}</span> highlights</div>
  <div><span class="stat-num">{n_docs}</span> files available</div>
</div>

<p style="color: var(--muted); font-size: 0.9rem;">This is a cross-reference collection. Documents are also listed in their
primary thematic collection. Identification was done by AI and may not be complete.</p>

<input type="text" class="search-box" placeholder="Search documents in this collection…"
       onkeyup="filterTable()" id="searchInput">

<div class="filter-bar">
  <label><input type="checkbox" id="hlFilter" onchange="toggleHighlightsFilter()"> Show highlights only ({n_highlights})</label>
  <span class="filter-count" id="rowCount">{n_docs} documents</span>
</div>

<table class="file-table" id="fileTable">
<thead><tr>
  <th>Date</th>
  <th>Document</th>
  <th>Summary</th>
  <th>File</th>
</tr></thead>
<tbody>
{tbody}
</tbody>
</table>

</div>

<footer class="site-footer">
  <a href="../index.html">&larr; Back to Archive Home</a> &middot;
  The Papers of Don Glendenning
</footer>

<script>
function filterTable() {{
  var query = document.getElementById('searchInput').value.toLowerCase();
  var hlOnly = document.getElementById('hlFilter');
  hlOnly = hlOnly ? hlOnly.checked : false;
  var rows = document.querySelectorAll('#fileTable tbody tr');
  var visible = 0;
  rows.forEach(function(row) {{
    var matchText = !query || row.textContent.toLowerCase().includes(query);
    var matchHl = !hlOnly || row.hasAttribute('data-highlight');
    if (matchText && matchHl) {{
      row.style.display = '';
      visible++;
    }} else {{
      row.style.display = 'none';
    }}
  }});
  var counter = document.getElementById('rowCount');
  if (counter) counter.textContent = visible + ' documents';
}}
function toggleHighlightsFilter() {{
  filterTable();
}}
function toggleRow(btn) {{
  var container = btn.parentElement;
  var short = container.querySelector('.short-summary');
  var full = container.querySelector('.full-summary');
  if (full.style.display === 'none') {{
    short.style.display = 'none';
    full.style.display = 'block';
    btn.textContent = '▾ less';
  }} else {{
    short.style.display = 'inline';
    full.style.display = 'none';
    btn.textContent = '▸ more';
  }}
}}
</script>

</body>
</html>'''


def main():
    all_letters = []

    # Scan all theme directories
    for theme_dir in sorted(ARCHIVE_ROOT.iterdir()):
        if not (theme_dir.is_dir() and re.match(r'\d{2}-', theme_dir.name)):
            continue
        index_path = theme_dir / 'index.html'
        if not index_path.exists():
            continue

        docs = extract_rows_from_index(index_path)
        letters = [d for d in docs if is_letter_to_editor(d)]

        if letters:
            print(f'  {theme_dir.name}: {len(letters)} letters to the editor')
            all_letters.extend(letters)

    print(f'\n  Total: {len(all_letters)} letters to the editor')

    # Create output directory
    out_dir = ARCHIVE_ROOT / '12-letters-to-editor'
    out_dir.mkdir(exist_ok=True)

    # Write index page
    html = build_index_html(all_letters)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    print(f'  Written to {out_dir}/index.html')


if __name__ == '__main__':
    main()
