#!/usr/bin/env python3
"""Extract reader page content into compact JSON files for AI review.

Reads each reader page and extracts:
- slug, title, summary, first ~2000 chars of text content
- File size, garbage ratio (% non-printable characters)

Outputs one JSON file per theme into scripts/review_data/.
"""

import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent
THEMES = sorted(d for d in ARCHIVE_ROOT.iterdir()
                if d.is_dir() and re.match(r'\d{2}-', d.name))
OUTPUT_DIR = ARCHIVE_ROOT / 'scripts' / 'review_data'


class TextExtractor(HTMLParser):
    """Strip HTML tags, return plain text."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip = True
        if tag in ('p', 'br', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'pre'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def get_text(self):
        return ''.join(self.parts).strip()


def strip_html(html_str):
    """Remove HTML tags and return plain text."""
    ext = TextExtractor()
    ext.feed(html_str)
    return ext.get_text()


def extract_between(html, start_marker, end_marker):
    """Extract content between two markers in HTML."""
    idx = html.find(start_marker)
    if idx == -1:
        return ''
    idx += len(start_marker)
    end = html.find(end_marker, idx)
    if end == -1:
        return html[idx:]
    return html[idx:end]


def garbage_ratio(text):
    """Fraction of non-printable, non-whitespace characters."""
    if not text:
        return 0.0
    non_print = sum(1 for c in text if not c.isprintable() and c not in '\n\r\t')
    return non_print / len(text)


def process_reader_page(filepath):
    """Extract metadata from a single reader page."""
    slug = filepath.stem
    size = filepath.stat().st_size

    try:
        html = filepath.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return {'slug': slug, 'error': str(e), 'size': size}

    # Title from <h1>
    m = re.search(r'<h1>(.*?)</h1>', html, re.DOTALL)
    title = strip_html(m.group(1)).strip() if m else slug

    # Summary from <div class="reader-summary">
    summary_html = extract_between(html, '<div class="reader-summary">', '</div>')
    summary = strip_html(summary_html).strip()

    # Content from <div class="reader-content">
    content_html = extract_between(html, '<div class="reader-content">', '\n<a class="file-link-btn"')
    if not content_html:
        content_html = extract_between(html, '<div class="reader-content">', '</div>\n</main>')
    content_text = strip_html(content_html).strip()

    # Compute garbage ratio on first 5000 chars of content
    sample = content_text[:5000]
    gr = garbage_ratio(sample)

    # Truncate content to ~2000 chars for review
    content_preview = content_text[:2000]
    if len(content_text) > 2000:
        content_preview += '...'

    return {
        'slug': slug,
        'title': title,
        'summary': summary,
        'content_preview': content_preview,
        'size': size,
        'content_length': len(content_text),
        'garbage_ratio': round(gr, 4),
    }


def process_theme(theme_dir):
    """Process all reader pages in a theme directory."""
    read_dir = theme_dir / 'read'
    if not read_dir.exists():
        return theme_dir.name, []

    pages = sorted(read_dir.glob('*.html'))
    results = []
    for p in pages:
        results.append(process_reader_page(p))
    return theme_dir.name, results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_docs = 0
    total_flagged = 0

    print(f"Extracting from {len(THEMES)} themes...")

    with ProcessPoolExecutor(max_workers=min(8, len(THEMES))) as pool:
        futures = {pool.submit(process_theme, t): t.name for t in THEMES}
        for future in as_completed(futures):
            theme_name = futures[future]
            name, results = future.result()

            # Count high-garbage files
            flagged = sum(1 for r in results if r.get('garbage_ratio', 0) > 0.05)

            out_path = OUTPUT_DIR / f'{name}.json'
            with open(out_path, 'w') as f:
                json.dump(results, f, indent=1)

            size_kb = out_path.stat().st_size / 1024
            print(f"  {name}: {len(results)} docs, {flagged} high-garbage, {size_kb:.0f} KB JSON")
            total_docs += len(results)
            total_flagged += flagged

    print(f"\nDone: {total_docs} docs extracted, {total_flagged} pre-flagged as high-garbage")
    print(f"Output: {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
