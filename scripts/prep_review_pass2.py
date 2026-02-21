#!/usr/bin/env python3
"""Prepare compact data chunks for review pass 2 (privacy + archival value).

Creates 15 chunk files matching the original agent splits, with compact
doc entries (slug, title, summary, short content preview). Excludes docs
already flagged in pass 1.
"""

import json
from pathlib import Path
from collections import defaultdict

REVIEW_DATA = Path(__file__).resolve().parent / 'review_data'

# Theme doc counts: 01:31, 02:200, 03:223, 04:189, 05:1786, 06:143,
#                   07:819, 08:16, 09:232, 10:99, 11:144

def load_existing_flagged_slugs():
    """Load all slugs already flagged in pass 1."""
    flagged = set()
    for p in REVIEW_DATA.glob('flags_*.json'):
        if '_p2_' in p.name:
            continue  # skip our own output
        with open(p) as f:
            try:
                flags = json.load(f)
                for flag in flags:
                    flagged.add(flag.get('slug', ''))
            except json.JSONDecodeError:
                pass
    return flagged


def load_theme_docs(theme_name):
    """Load docs from a theme review_data JSON."""
    path = REVIEW_DATA / f'{theme_name}.json'
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def compact_doc(doc):
    """Create compact version: slug, title, summary, short content preview."""
    return {
        'slug': doc['slug'],
        'title': doc.get('title', ''),
        'summary': doc.get('summary', ''),
        'content_preview': doc.get('content_preview', '')[:500],
        'theme': '',  # filled in by caller
    }


def write_chunk(name, docs, flagged_slugs):
    """Write a chunk file, filtering out already-flagged docs."""
    filtered = [d for d in docs if d['slug'] not in flagged_slugs]
    out_path = REVIEW_DATA / f'p2_input_{name}.json'
    with open(out_path, 'w') as f:
        json.dump(filtered, f, indent=1)
    print(f"  p2_input_{name}.json: {len(filtered)} docs ({len(docs) - len(filtered)} already flagged)")
    return len(filtered)


def main():
    flagged = load_existing_flagged_slugs()
    print(f"Pass 1 flagged {len(flagged)} slugs (will skip)\n")

    total = 0

    # Single-theme chunks
    singles = {
        '02': '02-family-chronicle',
        '03': '03-family-genealogy',
        '04': '04-holland-college',
        '06': '06-speeches',
        '09': '09-community-civic',
        '10': '10-creative-writing',
        '11': '11-personal-household',
    }

    for chunk_id, theme in singles.items():
        docs = load_theme_docs(theme)
        for d in docs:
            d = compact_doc(d)
            d['theme'] = theme
        compact = [dict(compact_doc(d), theme=theme) for d in docs]
        total += write_chunk(chunk_id, compact, flagged)

    # Combined 01 + 08
    docs_01 = [dict(compact_doc(d), theme='01-autobiography')
               for d in load_theme_docs('01-autobiography')]
    docs_08 = [dict(compact_doc(d), theme='08-correspondence')
               for d in load_theme_docs('08-correspondence')]
    total += write_chunk('01_08', docs_01 + docs_08, flagged)

    # Theme 05 split 5 ways
    docs_05 = [dict(compact_doc(d), theme='05-education-reform')
               for d in load_theme_docs('05-education-reform')]
    chunk_size = len(docs_05) // 5
    for i, label in enumerate(['05a', '05b', '05c', '05d', '05e']):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < 4 else len(docs_05)
        total += write_chunk(label, docs_05[start:end], flagged)

    # Theme 07 split 2 ways
    docs_07 = [dict(compact_doc(d), theme='07-professional-career')
               for d in load_theme_docs('07-professional-career')]
    mid = len(docs_07) // 2
    total += write_chunk('07a', docs_07[:mid], flagged)
    total += write_chunk('07b', docs_07[mid:], flagged)

    print(f"\nTotal: {total} docs across 15 chunks ready for review")


if __name__ == '__main__':
    main()
