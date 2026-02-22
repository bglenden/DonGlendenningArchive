#!/usr/bin/env python3
"""Add pagefind attributes to reader pages for full-text search indexing.

Adds:
- data-pagefind-body to .reader-content div (index only document text)
- data-pagefind-meta="theme" from the breadcrumb's theme link text
- data-pagefind-filter="theme" for faceted filtering
- data-pagefind-ignore to non-content pages (theme indexes, root index, etc.)
"""

import re
from pathlib import Path

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent

THEME_NAMES = {
    '01-autobiography': 'Autobiography & Personal Narrative',
    '02-family-chronicle': 'The Family Chronicle',
    '03-family-genealogy': 'Family History & Genealogy',
    '04-holland-college': 'Holland College & Institutional Legacy',
    '05-education-reform': 'Education Philosophy & Reform',
    '06-speeches': 'Speeches & Presentations',
    '07-professional-career': 'Professional Career & Consulting',
    '08-correspondence': 'Correspondence',
    '09-community-civic': 'Community Foundation & Civic Life',
    '10-creative-writing': 'Creative Writing',
    '11-personal-household': 'Personal & Household',
}


def process_reader_pages():
    """Add data-pagefind-body and theme metadata to reader pages."""
    count = 0
    for theme_dir, theme_name in THEME_NAMES.items():
        read_dir = ARCHIVE_ROOT / theme_dir / 'read'
        if not read_dir.exists():
            continue
        for html_file in sorted(read_dir.glob('*.html')):
            html = html_file.read_text(encoding='utf-8', errors='replace')

            modified = False

            # Add data-pagefind-body to reader-content div
            if 'data-pagefind-body' not in html and 'class="reader-content"' in html:
                html = html.replace(
                    'class="reader-content"',
                    'class="reader-content" data-pagefind-body',
                    1
                )
                modified = True

            # Add theme filter/meta as a hidden element inside reader-content
            if 'data-pagefind-filter="theme"' not in html and 'data-pagefind-body' in html:
                tag = f'<span data-pagefind-filter="theme" data-pagefind-meta="theme" style="display:none">{theme_name}</span>\n'
                html = html.replace(
                    'class="reader-content" data-pagefind-body>',
                    'class="reader-content" data-pagefind-body>\n' + tag,
                    1
                )
                modified = True

            # Add title meta from h1
            if 'data-pagefind-meta="title"' not in html:
                html = re.sub(
                    r'(<header class="site-header">\s*<h1)(>)',
                    r'\1 data-pagefind-meta="title"\2',
                    html,
                    count=1
                )
                modified = True

            if modified:
                html_file.write_text(html, encoding='utf-8')
                count += 1

    print(f'Updated {count} reader pages')


def add_pagefind_ignore():
    """Add data-pagefind-ignore to non-content pages so they aren't indexed."""
    ignore_pages = [
        ARCHIVE_ROOT / 'index.html',
        ARCHIVE_ROOT / 'excluded.html',
        ARCHIVE_ROOT / 'Eulogy' / 'index.html',
    ]
    # Theme index pages
    for theme_dir in THEME_NAMES:
        ignore_pages.append(ARCHIVE_ROOT / theme_dir / 'index.html')

    count = 0
    for page in ignore_pages:
        if not page.exists():
            continue
        html = page.read_text(encoding='utf-8', errors='replace')
        if 'data-pagefind-ignore' not in html:
            html = html.replace('<body>', '<body data-pagefind-ignore>', 1)
            page.write_text(html, encoding='utf-8')
            count += 1

    print(f'Added pagefind-ignore to {count} non-content pages')


if __name__ == '__main__':
    process_reader_pages()
    add_pagefind_ignore()
