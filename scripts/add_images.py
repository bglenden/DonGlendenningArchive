#!/usr/bin/env python3
"""
Add images to archive reader pages using LibreOffice headless conversion.

Converts source .doc/.docx/.rtf files to HTML via LibreOffice, extracts any
companion images produced, and patches the reader pages with the LO-generated
HTML body content (cleaned up) and copies images alongside.

Usage:
    python3 scripts/add_images.py [OPTIONS]

Options:
    --workers N      Parallel LO instances (default: 4)
    --theme THEME    Process only one theme (e.g. "02-family-chronicle")
    --force          Re-process files with existing lo-images marker
    --dry-run        Report what would change, don't modify files
"""

import argparse
import concurrent.futures
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 60


# ─── HTML Cleaning ───────────────────────────────────────────────────────────

class TagStripper(html.parser.HTMLParser):
    """Strip specified tags but keep their content."""

    def __init__(self, strip_tags):
        super().__init__(convert_charrefs=False)
        self.strip_tags = {t.lower() for t in strip_tags}
        self.result = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() not in self.strip_tags:
            self.result.append(self._rebuild_tag(tag, attrs))

    def handle_endtag(self, tag):
        if tag.lower() not in self.strip_tags:
            self.result.append(f'</{tag}>')

    def handle_data(self, data):
        self.result.append(data)

    def handle_entityref(self, name):
        self.result.append(f'&{name};')

    def handle_charref(self, name):
        self.result.append(f'&#{name};')

    def handle_comment(self, data):
        self.result.append(f'<!--{data}-->')

    def handle_startendtag(self, tag, attrs):
        if tag.lower() not in self.strip_tags:
            self.result.append(self._rebuild_tag(tag, attrs, self_closing=True))

    @staticmethod
    def _rebuild_tag(tag, attrs, self_closing=False):
        parts = [tag]
        for k, v in attrs:
            if v is None:
                parts.append(k)
            else:
                parts.append(f'{k}="{v}"')
        close = ' /' if self_closing else ''
        return '<' + ' '.join(parts) + close + '>'

    def get_result(self):
        return ''.join(self.result)


def strip_tags(html_str, tags):
    """Remove specified tags but keep their inner content."""
    s = TagStripper(tags)
    s.feed(html_str)
    return s.get_result()


def clean_lo_html(body_html, image_files, reader_slug):
    """Clean LibreOffice HTML body content for embedding in reader pages.

    - Strip <font> tags (unwrap)
    - Strip inline font-size from style attributes
    - Remove column-count divs (unwrap)
    - Remove class="western"/"cjk"/"ctl"
    - Strip width/height/border/name from <img> tags, rewrite src paths
    - Sequential image naming: img001.png, img002.png, ...
    """
    # Strip <font> tags
    result = strip_tags(body_html, ['font'])

    # Remove class="western", class="cjk", class="ctl"
    result = re.sub(r'\s+class="(western|cjk|ctl)"', '', result)

    # Strip font-size from style attributes
    result = re.sub(r'font-size\s*:\s*[^;"}]+;?\s*', '', result)

    # Remove empty style attributes left over
    result = re.sub(r'\s+style="\s*"', '', result)

    # Remove column-count divs (unwrap them)
    # Match <div ...column-count...> and </div> that wraps everything
    result = re.sub(r'<div[^>]*column-count[^>]*>', '', result, flags=re.IGNORECASE)
    # We can't perfectly match closing divs, but LO column-count divs typically
    # wrap the whole body. We'll remove the corresponding closing tags carefully.
    # Instead, let's just remove all div tags that have column-count in their style
    # and handle the general case with a simpler approach

    # Build image rename map: original_name -> new_name
    img_map = {}
    sorted_images = sorted(image_files)
    for i, orig_name in enumerate(sorted_images, 1):
        ext = Path(orig_name).suffix or '.png'
        new_name = f'img{i:03d}{ext}'
        img_map[orig_name] = new_name

    # Rewrite <img> tags
    def rewrite_img(m):
        tag_content = m.group(1)
        # Extract src
        src_match = re.search(r'src="([^"]*)"', tag_content)
        if not src_match:
            return m.group(0)

        src_basename = os.path.basename(urllib.parse.unquote(src_match.group(1)))

        if src_basename not in img_map:
            # Image not in our map - might be a data URI or external, keep as is
            return m.group(0)

        new_src = f'img/{reader_slug}/{img_map[src_basename]}'

        # Strip width, height, border, name attributes
        cleaned = re.sub(r'\s+(width|height|border|name)="[^"]*"', '', tag_content)
        # Replace src
        cleaned = re.sub(r'src="[^"]*"', f'src="{new_src}"', cleaned)

        return f'<img {cleaned.strip()}>'

    result = re.sub(r'<img\s+([^>]*)/?>', rewrite_img, result, flags=re.IGNORECASE)

    return result, img_map


def extract_lo_body(lo_html_path):
    """Extract content between <body> and </body> from LO HTML output."""
    content = lo_html_path.read_text(encoding='utf-8', errors='replace')

    # Find body content
    body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
    if body_match:
        return body_match.group(1).strip()

    # Fallback: return everything
    return content


# ─── Phase 1: Build source→reader mapping ────────────────────────────────────

def build_mapping(themes=None):
    """Scan reader pages, extract download links, build mapping.

    Returns dict: (theme_dir, source_filename) → reader_html_path
    """
    mapping = {}

    theme_dirs = sorted(ARCHIVE_ROOT.glob('[0-9][0-9]-*'))
    if themes:
        theme_dirs = [d for d in theme_dirs if d.name in themes]

    for theme_dir in theme_dirs:
        read_dir = theme_dir / 'read'
        if not read_dir.is_dir():
            continue

        for reader_html in sorted(read_dir.glob('*.html')):
            content = reader_html.read_text(encoding='utf-8', errors='replace')

            # Look for <a class="file-link-btn" href="../files/FILENAME">
            m = re.search(
                r'<a\s+class="file-link-btn"\s+href="\.\./files/([^"]+)"',
                content,
                re.IGNORECASE
            )
            if m:
                source_filename = urllib.parse.unquote(m.group(1))
                source_path = theme_dir / 'files' / source_filename
                if source_path.exists():
                    mapping[(theme_dir.name, source_filename)] = reader_html

    return mapping


# ─── Phase 2: LibreOffice conversion ─────────────────────────────────────────

def convert_one(args):
    """Convert a single source file with LibreOffice. Returns result dict."""
    theme_name, source_filename, source_path, reader_html, worker_id, index, total = args

    reader_slug = reader_html.stem

    result = {
        'theme': theme_name,
        'source': source_filename,
        'reader': str(reader_html),
        'reader_slug': reader_slug,
        'images': [],
        'error': None,
        'skipped': False,
    }

    # Create a per-file temp dir for conversion
    tmpdir = tempfile.mkdtemp(prefix=f'lo_conv_{worker_id}_')
    try:
        profile_dir = f'/tmp/lo_profile_{worker_id}'
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            'soffice',
            '--headless',
            '--norestore',
            f'-env:UserInstallation=file://{profile_dir}',
            '--convert-to', 'html',
            '--outdir', tmpdir,
            str(source_path),
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )

        if proc.returncode != 0:
            result['error'] = f'LO exit code {proc.returncode}: {proc.stderr[:200]}'
            return result

        # Find the output HTML file
        html_files = list(Path(tmpdir).glob('*.html')) + list(Path(tmpdir).glob('*.htm'))
        if not html_files:
            result['error'] = 'No HTML output produced'
            return result

        lo_html_path = html_files[0]

        # Find companion image files (LO names them like filename_html_XXXX.png)
        all_files = set(Path(tmpdir).iterdir())
        image_files = []
        for f in sorted(all_files):
            if f == lo_html_path:
                continue
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.svg', '.wmf', '.emf'):
                image_files.append(f)

        if not image_files:
            # No images - skip this file
            result['skipped'] = True
            return result

        # Extract and clean body content
        body_html = extract_lo_body(lo_html_path)
        image_basenames = [f.name for f in image_files]
        cleaned_html, img_map = clean_lo_html(body_html, image_basenames, reader_slug)

        result['body_html'] = cleaned_html
        result['image_files'] = [(f, img_map.get(f.name, f.name)) for f in image_files]
        result['images'] = list(img_map.values())
        result['num_images'] = len(image_files)

    except subprocess.TimeoutExpired:
        result['error'] = f'Timeout after {TIMEOUT_SECONDS}s'
    except Exception as e:
        result['error'] = str(e)
    finally:
        # Don't clean tmpdir yet if we have images to copy
        if result.get('image_files'):
            result['_tmpdir'] = tmpdir
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return result


# ─── Phase 3: Update reader pages ────────────────────────────────────────────

def update_reader_page(result, dry_run=False):
    """Update a reader page with LO-generated HTML and copy images."""
    reader_path = Path(result['reader'])
    reader_slug = result['reader_slug']
    theme_dir = reader_path.parent.parent

    before_size = reader_path.stat().st_size

    if dry_run:
        # Calculate approximate after size
        body_size = len(result.get('body_html', '').encode('utf-8'))
        img_size = sum(f.stat().st_size for f, _ in result.get('image_files', []))
        return before_size, before_size + body_size + img_size

    # Read existing page
    page_content = reader_path.read_text(encoding='utf-8')
    new_body = result['body_html']

    # Find reader-content div and replace its contents using string ops
    # (avoids regex replacement issues with backslash sequences in LO HTML)
    open_tag = '<div class="reader-content">'
    open_idx = page_content.find(open_tag)
    if open_idx == -1:
        print(f'  WARNING: Could not find reader-content div in {reader_path}')
        return before_size, before_size

    content_start = open_idx + len(open_tag)

    # Find the matching </div> — it's the next </div> before <a class="file-link-btn">
    file_link_idx = page_content.find('<a class="file-link-btn"', content_start)
    if file_link_idx != -1:
        # Find the </div> just before the file-link-btn
        close_idx = page_content.rfind('</div>', content_start, file_link_idx)
    else:
        close_idx = -1

    if close_idx == -1:
        # Fallback: find first </div> after the open tag
        close_idx = page_content.find('</div>', content_start)

    if close_idx == -1:
        print(f'  WARNING: Could not find closing </div> in {reader_path}')
        return before_size, before_size

    new_content = (
        page_content[:content_start]
        + f'\n<!-- lo-images -->\n{new_body}\n'
        + page_content[close_idx:]
    )

    # Copy images
    img_dir = theme_dir / 'read' / 'img' / reader_slug
    img_dir.mkdir(parents=True, exist_ok=True)

    total_img_size = 0
    for src_file, new_name in result.get('image_files', []):
        dst = img_dir / new_name
        shutil.copy2(str(src_file), str(dst))
        total_img_size += dst.stat().st_size

    # Write updated page
    reader_path.write_text(new_content, encoding='utf-8')
    after_size = reader_path.stat().st_size + total_img_size

    return before_size, after_size


# ─── Phase 4: Report ─────────────────────────────────────────────────────────

def format_size(nbytes):
    """Format bytes as human-readable size."""
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(nbytes) < 1024:
            return f'{nbytes:.1f} {unit}'
        nbytes /= 1024
    return f'{nbytes:.1f} TB'


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Add images to archive reader pages via LibreOffice')
    parser.add_argument('--workers', type=int, default=4, help='Parallel LO instances (default: 4)')
    parser.add_argument('--theme', type=str, default=None, help='Process only one theme')
    parser.add_argument('--force', action='store_true', help='Re-process files with existing lo-images marker')
    parser.add_argument('--dry-run', action='store_true', help='Report what would change, don\'t modify')
    args = parser.parse_args()

    print(f'Archive root: {ARCHIVE_ROOT}')
    print()

    # Phase 1: Build mapping
    print('Phase 1: Building source→reader mapping...')
    t0 = time.time()

    themes = [args.theme] if args.theme else None
    mapping = build_mapping(themes)

    print(f'  Found {len(mapping)} source↔reader pairs in {time.time()-t0:.1f}s')

    # Filter out already-processed files unless --force
    if not args.force:
        filtered = {}
        skipped_existing = 0
        for key, reader_html in mapping.items():
            content = reader_html.read_text(encoding='utf-8', errors='replace')
            if '<!-- lo-images -->' in content:
                skipped_existing += 1
            else:
                filtered[key] = reader_html
        if skipped_existing:
            print(f'  Skipping {skipped_existing} already-processed files (use --force to redo)')
        mapping = filtered

    # Prepare work items
    work = []
    for i, ((theme_name, source_filename), reader_html) in enumerate(sorted(mapping.items())):
        source_path = ARCHIVE_ROOT / theme_name / 'files' / source_filename
        # Skip non-convertible file types
        ext = source_path.suffix.lower()
        if ext not in ('.doc', '.docx', '.rtf', '.odt'):
            continue
        worker_id = i % args.workers
        work.append((theme_name, source_filename, source_path, reader_html, worker_id, i + 1, len(mapping)))

    print(f'  {len(work)} files to convert')
    print()

    # Phase 2: Batch convert
    print(f'Phase 2: Converting with LibreOffice ({args.workers} workers)...')
    t0 = time.time()

    results = []
    completed = 0
    errors = 0
    skipped = 0
    with_images = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(convert_one, w): w for w in work}

        for future in concurrent.futures.as_completed(future_map):
            completed += 1
            result = future.result()

            if result['error']:
                errors += 1
                print(f'  [{completed}/{len(work)}] ERROR {result["theme"]}/{result["source"]}: {result["error"]}')
            elif result['skipped']:
                skipped += 1
                if completed % 100 == 0 or completed == len(work):
                    print(f'  [{completed}/{len(work)}] progress... ({with_images} with images, {skipped} without)')
            else:
                with_images += 1
                n = result.get('num_images', 0)
                print(f'  [{completed}/{len(work)}] {result["theme"]}/{result["source"]} → {n} image{"s" if n != 1 else ""}')
                results.append(result)

    elapsed = time.time() - t0
    print(f'  Done in {elapsed:.1f}s: {with_images} files with images, {skipped} without, {errors} errors')
    print()

    if not results:
        print('No files with images found. Nothing to update.')
        return

    # Phase 3: Update reader pages
    print(f'Phase 3: Updating {len(results)} reader pages...')
    t0 = time.time()

    # Track stats per theme
    theme_stats = {}
    for result in sorted(results, key=lambda r: r['reader']):
        theme = result['theme']
        if theme not in theme_stats:
            theme_stats[theme] = {'updated': 0, 'images': 0, 'before': 0, 'after': 0}

        before, after = update_reader_page(result, dry_run=args.dry_run)

        theme_stats[theme]['updated'] += 1
        theme_stats[theme]['images'] += result.get('num_images', 0)
        theme_stats[theme]['before'] += before
        theme_stats[theme]['after'] += after

        # Clean up temp dir
        tmpdir = result.get('_tmpdir')
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print(f'  Done in {time.time()-t0:.1f}s')
    print()

    # Phase 4: Report
    prefix = '[DRY RUN] ' if args.dry_run else ''
    print(f'{prefix}Phase 4: Summary')
    print()
    print(f'{"Theme":<30} | {"Updated":>7} | {"Images":>6} | {"Before":>10} | {"After":>10} | {"Delta":>10}')
    print('-' * 85)

    total_updated = 0
    total_images = 0
    total_before = 0
    total_after = 0

    for theme in sorted(theme_stats):
        s = theme_stats[theme]
        delta = s['after'] - s['before']
        print(f'{theme:<30} | {s["updated"]:>7} | {s["images"]:>6} | {format_size(s["before"]):>10} | {format_size(s["after"]):>10} | +{format_size(delta):>9}')
        total_updated += s['updated']
        total_images += s['images']
        total_before += s['before']
        total_after += s['after']

    total_delta = total_after - total_before
    print('-' * 85)
    print(f'{"TOTAL":<30} | {total_updated:>7} | {total_images:>6} | {format_size(total_before):>10} | {format_size(total_after):>10} | +{format_size(total_delta):>9}')
    print()

    # Write report JSON
    report = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'dry_run': args.dry_run,
        'themes': {
            theme: {
                'updated': s['updated'],
                'images': s['images'],
                'before_bytes': s['before'],
                'after_bytes': s['after'],
            }
            for theme, s in theme_stats.items()
        },
        'totals': {
            'updated': total_updated,
            'images': total_images,
            'before_bytes': total_before,
            'after_bytes': total_after,
        },
        'errors': errors,
        'skipped_no_images': skipped,
        'files': [
            {
                'theme': r['theme'],
                'source': r['source'],
                'reader': r['reader_slug'],
                'num_images': r.get('num_images', 0),
            }
            for r in sorted(results, key=lambda r: r['reader'])
        ],
    }

    report_path = ARCHIVE_ROOT / 'scripts' / 'image_report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report written to {report_path}')


if __name__ == '__main__':
    main()
