#!/usr/bin/env python3
"""Find duplicate/near-duplicate letters to the editor.

Reads all reader pages linked from the LTE theme index, extracts text content,
and identifies pairs with high text similarity.
"""

import re
from pathlib import Path
from difflib import SequenceMatcher

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent
LTE_INDEX = ARCHIVE_ROOT / '12-letters-to-editor' / 'index.html'


def extract_text_from_reader(path):
    """Extract plain text from a reader page's .reader-content div."""
    if not path.exists():
        return ''
    html = path.read_text(encoding='utf-8', errors='replace')
    # Find reader-content div
    m = re.search(r'<div class="reader-content"[^>]*>(.*?)</div>\s*(?:<a class="file-link-btn"|</div>)', html, re.DOTALL)
    if not m:
        return ''
    content = m.group(1)
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', content)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_lte_documents():
    """Parse the LTE index to get all document references."""
    html = LTE_INDEX.read_text(encoding='utf-8', errors='replace')
    docs = []
    rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)
    for row in rows:
        # Extract theme and slug from link like ../05-education-reform/read/slug.html
        m = re.search(r'href="\.\./([^/]+)/read/([^"]+)\.html"', row)
        if not m:
            continue
        theme, slug = m.group(1), m.group(2)
        # Extract title
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', tds[1]).strip() if len(tds) > 1 else slug
        date = re.sub(r'<[^>]+>', '', tds[0]).strip() if tds else ''
        docs.append({
            'theme': theme,
            'slug': slug,
            'title': title,
            'date': date,
            'path': ARCHIVE_ROOT / theme / 'read' / f'{slug}.html',
        })
    return docs


def main():
    docs = get_lte_documents()
    print(f'Reading {len(docs)} reader pages...\n')

    # Extract text from all pages
    for doc in docs:
        doc['text'] = extract_text_from_reader(doc['path'])
        doc['text_len'] = len(doc['text'])

    # Find empty/very short documents
    print('── Very short documents (< 100 chars) ──')
    short = [d for d in docs if d['text_len'] < 100]
    for d in short:
        print(f'  [{d["text_len"]:4d} chars] {d["theme"]}/{d["slug"]} — {d["title"]}')
    if not short:
        print('  None')

    # Compare all pairs for similarity
    print(f'\n── Checking {len(docs) * (len(docs)-1) // 2} pairs for similarity ──')
    duplicates = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a, b = docs[i], docs[j]
            # Skip if either is very short (< 50 chars)
            if a['text_len'] < 50 or b['text_len'] < 50:
                continue
            # Quick length check — if lengths differ by >3x, skip
            ratio = min(a['text_len'], b['text_len']) / max(a['text_len'], b['text_len'])
            if ratio < 0.3:
                continue
            # Compare first 2000 chars for speed
            sim = SequenceMatcher(None, a['text'][:2000], b['text'][:2000]).ratio()
            if sim > 0.6:
                duplicates.append((sim, a, b))

    duplicates.sort(key=lambda x: -x[0])

    if duplicates:
        print(f'\n── {len(duplicates)} similar pairs found ──\n')
        for sim, a, b in duplicates:
            print(f'  {sim:.0%} similar:')
            print(f'    A: [{a["date"]:>15}] {a["theme"]}/{a["slug"]} — {a["title"]} ({a["text_len"]} chars)')
            print(f'    B: [{b["date"]:>15}] {b["theme"]}/{b["slug"]} — {b["title"]} ({b["text_len"]} chars)')
            print()
    else:
        print('  No similar pairs found above 60% threshold')

    print(f'\nTotal: {len(docs)} documents, {len(duplicates)} similar pairs')


if __name__ == '__main__':
    main()
