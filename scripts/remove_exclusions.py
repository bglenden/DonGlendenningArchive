#!/usr/bin/env python3
"""Remove excluded documents from the archive.

Reads an exclusions.json file and removes:
- Reader pages ({theme}/read/{slug}.html)
- Image directories ({theme}/read/img/{slug}/)
- Source files ({theme}/files/{filename})
- Table rows from theme index pages
Then updates all document counts in theme and root index pages.
Finally runs an audit to verify removal.
"""

import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent


def extract_source_filename(reader_path):
    """Extract the original source filename from a reader page's download link."""
    try:
        html = reader_path.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'<a\s+class="file-link-btn"\s+href="\.\./files/([^"]+)"', html)
        if m:
            return unquote(m.group(1))
    except Exception:
        pass
    return None


def remove_files(exclusions):
    """Delete reader pages, image dirs, and source files. Returns removal stats."""
    stats = {'reader': 0, 'images': 0, 'source': 0, 'source_missing': [], 'reader_missing': []}

    for entry in exclusions:
        slug = entry['slug']
        theme = entry['theme']
        theme_dir = ARCHIVE_ROOT / theme

        reader_path = theme_dir / 'read' / f'{slug}.html'
        img_dir = theme_dir / 'read' / 'img' / slug

        # Extract source filename before deleting reader page
        source_filename = extract_source_filename(reader_path) if reader_path.exists() else None

        if reader_path.exists():
            reader_path.unlink()
            stats['reader'] += 1
        else:
            stats['reader_missing'].append(f'{theme}/read/{slug}.html')

        # Delete image directory
        if img_dir.exists():
            n_images = len(list(img_dir.iterdir()))
            shutil.rmtree(img_dir)
            stats['images'] += n_images

        # Delete source file
        if source_filename:
            source_path = theme_dir / 'files' / source_filename
            if source_path.exists():
                source_path.unlink()
                stats['source'] += 1
            else:
                stats['source_missing'].append(f'{theme}/files/{source_filename}')
        elif reader_path not in [None] and not reader_path.exists():
            stats['source_missing'].append(f'{theme}/files/? (no reader page)')

    return stats


def update_theme_indexes(exclusions_by_theme):
    """Remove table rows from theme index pages and update counts."""
    theme_stats = {}

    for theme, slugs in exclusions_by_theme.items():
        index_path = ARCHIVE_ROOT / theme / 'index.html'
        if not index_path.exists():
            print(f"  WARNING: {theme}/index.html not found")
            continue

        html = index_path.read_text(encoding='utf-8', errors='replace')
        href_patterns = {f'href="read/{slug}.html"' for slug in slugs}

        # Extract tbody content
        tbody_start = html.find('<tbody>')
        tbody_end = html.find('</tbody>')
        if tbody_start == -1 or tbody_end == -1:
            print(f"  WARNING: no <tbody> in {theme}/index.html")
            continue

        before = html[:tbody_start + len('<tbody>')]
        tbody = html[tbody_start + len('<tbody>'):tbody_end]
        after = html[tbody_end:]

        # Split into individual <tr>...</tr> blocks
        rows = re.findall(r'<tr(?:\s[^>]*)?>.*?</tr>', tbody, re.DOTALL)

        # Filter out rows containing excluded slug links
        kept_rows = []
        removed = 0
        removed_highlights = 0
        for row in rows:
            should_remove = any(hp in row for hp in href_patterns)
            if should_remove:
                removed += 1
                if 'data-highlight="true"' in row:
                    removed_highlights += 1
            else:
                kept_rows.append(row)

        # Rebuild HTML
        html = before + '\n' + ''.join(kept_rows) + '\n' + after

        remaining_rows = len(kept_rows)
        remaining_highlights = sum(1 for r in kept_rows if 'data-highlight="true"' in r)

        # Update stats bar: first stat-num is doc count, second is highlights, third is files
        stat_nums = list(re.finditer(r'<span class="stat-num">(\d+)</span>', html))
        if len(stat_nums) >= 3:
            for i, new_val in reversed(list(enumerate([
                remaining_rows, remaining_highlights, remaining_rows,
            ]))):
                if i < len(stat_nums):
                    m = stat_nums[i]
                    html = html[:m.start()] + f'<span class="stat-num">{new_val}</span>' + html[m.end():]

        # Update filter count
        html = re.sub(
            r'(<span class="filter-count" id="rowCount">)\d+ documents(</span>)',
            rf'\g<1>{remaining_rows} documents\2',
            html
        )

        # Update highlights filter label
        html = re.sub(
            r'(Show highlights only \()\d+(\))',
            rf'\g<1>{remaining_highlights}\2',
            html
        )

        index_path.write_text(html, encoding='utf-8')
        theme_stats[theme] = {
            'removed': removed,
            'removed_highlights': removed_highlights,
            'remaining': remaining_rows,
            'remaining_highlights': remaining_highlights,
        }
        print(f"  {theme}/index.html: removed {removed} rows, {remaining_rows} remaining")

    return theme_stats


def update_root_index(theme_stats):
    """Update document counts in root index.html."""
    index_path = ARCHIVE_ROOT / 'index.html'
    html = index_path.read_text(encoding='utf-8', errors='replace')

    total_docs = sum(s['remaining'] for s in theme_stats.values())
    total_highlights = sum(s['remaining_highlights'] for s in theme_stats.values())

    # For themes not in exclusions, add their existing counts from the HTML
    for theme_card_match in re.finditer(
        r'<a href="(\d{2}-[^/]+)/index\.html">.*?<div class="count">(\d+) documents · (\d+) highlights</div>',
        html, re.DOTALL
    ):
        theme_name = theme_card_match.group(1)
        if theme_name not in theme_stats:
            total_docs += int(theme_card_match.group(2))
            total_highlights += int(theme_card_match.group(3))

    # Update global stats bar
    html = re.sub(
        r'(<span class="stat-num">)\d+(</span> documents archived)',
        rf'\g<1>{total_docs}\2',
        html
    )

    # Update each affected theme card count
    for theme, stats in theme_stats.items():
        pattern = re.compile(
            r'(<a href="' + re.escape(theme) + r'/index\.html">.*?<div class="count">)\d+ documents · \d+ highlights(</div>)',
            re.DOTALL
        )
        html = pattern.sub(
            rf'\g<1>{stats["remaining"]} documents · {stats["remaining_highlights"]} highlights\2',
            html
        )

    index_path.write_text(html, encoding='utf-8')
    print(f"\n  Root index.html: total now {total_docs} documents, {total_highlights} highlights")
    return total_docs


def audit(exclusions, exclusions_by_theme):
    """Verify all excluded content is actually gone."""
    print("\n── Audit ──")
    failures = 0
    checks = 0

    # 1. No excluded reader pages exist
    for entry in exclusions:
        slug, theme = entry['slug'], entry['theme']
        reader = ARCHIVE_ROOT / theme / 'read' / f'{slug}.html'
        img_dir = ARCHIVE_ROOT / theme / 'read' / 'img' / slug
        checks += 1
        if reader.exists():
            print(f"  FAIL: reader page still exists: {theme}/read/{slug}.html")
            failures += 1
        if img_dir.exists():
            print(f"  FAIL: image dir still exists: {theme}/read/img/{slug}/")
            failures += 1

    # 2. No excluded slugs referenced in theme indexes
    for theme, slugs in exclusions_by_theme.items():
        index_path = ARCHIVE_ROOT / theme / 'index.html'
        if not index_path.exists():
            continue
        html = index_path.read_text(encoding='utf-8', errors='replace')
        for slug in slugs:
            checks += 1
            if f'href="read/{slug}.html"' in html:
                print(f"  FAIL: {theme}/index.html still references {slug}")
                failures += 1

    # 3. No excluded slugs referenced in root index
    root_html = (ARCHIVE_ROOT / 'index.html').read_text()
    for entry in exclusions:
        slug = entry['slug']
        if f'{slug}.html' in root_html:
            print(f"  FAIL: root index.html references {slug}")
            failures += 1

    # 4. Theme index stats match their own row counts
    for theme_dir in sorted(ARCHIVE_ROOT.iterdir()):
        if not (theme_dir.is_dir() and re.match(r'\d{2}-', theme_dir.name)):
            continue
        index_path = theme_dir / 'index.html'
        if not index_path.exists():
            continue
        html = index_path.read_text()

        # Count rows in tbody
        tbody_start = html.find('<tbody>')
        tbody_end = html.find('</tbody>')
        if tbody_start == -1:
            continue
        tbody = html[tbody_start:tbody_end]
        row_count = len(re.findall(r'<tr(?:\s[^>]*)?>.*?</tr>', tbody, re.DOTALL))

        # Get reported stat
        m = re.search(r'<span class="stat-num">(\d+)</span> documents', html)
        if not m:
            continue
        reported = int(m.group(1))
        checks += 1
        if reported != row_count:
            print(f"  FAIL: {theme_dir.name} stats say {reported} but has {row_count} table rows")
            failures += 1

    # 5. Root total matches sum of theme card counts
    card_total = 0
    for m in re.finditer(r'<div class="count">(\d+) documents', root_html):
        card_total += int(m.group(1))
    m = re.search(r'<span class="stat-num">(\d+)</span> documents archived', root_html)
    root_total = int(m.group(1)) if m else -1
    checks += 1
    if card_total != root_total:
        print(f"  FAIL: root total ({root_total}) != sum of theme cards ({card_total})")
        failures += 1
    else:
        print(f"  OK: root total ({root_total}) matches sum of theme cards")

    print(f"  {checks} checks performed")
    if failures == 0:
        print(f"\n  ALL CHECKS PASSED")
    else:
        print(f"\n  {failures} FAILURES detected")

    return failures


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <exclusions.json>")
        sys.exit(1)

    exclusions_path = Path(sys.argv[1]).expanduser()
    if not exclusions_path.exists():
        print(f"Error: {exclusions_path} not found")
        sys.exit(1)

    with open(exclusions_path) as f:
        exclusions = json.load(f)

    print(f"Loaded {len(exclusions)} exclusions from {exclusions_path}\n")

    # Group by theme
    exclusions_by_theme = defaultdict(list)
    for entry in exclusions:
        exclusions_by_theme[entry['theme']].append(entry['slug'])

    # Step 1: Delete files
    print("── Deleting files ──")
    stats = remove_files(exclusions)
    print(f"  Deleted {stats['reader']} reader pages, {stats['images']} images, {stats['source']} source files")
    if stats['reader_missing']:
        print(f"  Note: {len(stats['reader_missing'])} reader pages already deleted")
    if stats['source_missing']:
        print(f"  Note: {len(stats['source_missing'])} source files already deleted")

    # Step 2: Update theme index pages
    print("\n── Updating theme indexes ──")
    theme_stats = update_theme_indexes(exclusions_by_theme)

    # Step 3: Update root index
    print("\n── Updating root index ──")
    update_root_index(theme_stats)

    # Step 4: Audit
    audit(exclusions, exclusions_by_theme)


if __name__ == '__main__':
    main()
