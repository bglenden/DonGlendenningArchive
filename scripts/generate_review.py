#!/usr/bin/env python3
"""Generate review HTML pages from flagged document JSON files.

Reads scripts/review_data/flags_*.json and produces:
- review/index.html (master page with all flagged docs)
- review/{theme}.html (per-theme pages)

Styled with the existing css/style.css.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent
FLAGS_DIR = ARCHIVE_ROOT / 'scripts' / 'review_data'
REVIEW_DIR = ARCHIVE_ROOT / 'review'

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

CRITERION_LABELS = {
    1: 'Corrupt/Garbage',
    2: 'Empty/Stub',
    3: 'Machine-Generated Data',
    4: 'Exact Duplicate',
    5: "Not Don's Work",
    6: 'System/Software File',
    7: 'Private/Sensitive',
    8: 'Low Archival Value',
}

# Load review_data JSONs for summary lookup
_review_data_cache = {}

def get_doc_summary(theme, slug):
    """Look up the summary for a doc from the review_data JSON."""
    if theme not in _review_data_cache:
        path = FLAGS_DIR / f'{theme}.json'
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            _review_data_cache[theme] = {d['slug']: d for d in data}
        else:
            _review_data_cache[theme] = {}
    doc = _review_data_cache[theme].get(slug, {})
    return doc.get('summary', ''), doc.get('size', 0), doc.get('garbage_ratio', 0)


CRITERION_FROM_LABEL = {v.lower(): k for k, v in CRITERION_LABELS.items()}


def infer_theme_from_filename(filename):
    """Infer theme from flags filename like flags_09.json or flags_p2_09.json."""
    m = re.match(r'flags_(?:p2_)?(\d{2})', filename)
    if not m:
        return ''
    num = m.group(1)
    for name in THEME_NAMES:
        if name.startswith(num + '-'):
            return name
    return ''


def normalize_flag(flag, source_filename):
    """Normalize flag entries to a consistent schema."""
    # Handle 'action' vs 'recommendation'
    if 'recommendation' not in flag and 'action' in flag:
        flag['recommendation'] = flag.pop('action')
    # Handle missing theme
    if not flag.get('theme'):
        flag['theme'] = infer_theme_from_filename(source_filename)
    # Handle string criterion labels
    crit = flag.get('criterion', 0)
    if isinstance(crit, str):
        flag['criterion'] = CRITERION_FROM_LABEL.get(crit.lower(), 0)
    return flag


def load_all_flags():
    """Load all flags_*.json files, merge, and deduplicate by theme+slug."""
    all_flags = []
    seen = set()
    for p in sorted(FLAGS_DIR.glob('flags_*.json')):
        with open(p) as f:
            try:
                flags = json.load(f)
                if isinstance(flags, list):
                    for flag in flags:
                        flag = normalize_flag(flag, p.name)
                        key = (flag.get('theme', ''), flag.get('slug', ''))
                        if key not in seen:
                            seen.add(key)
                            all_flags.append(flag)
            except json.JSONDecodeError:
                print(f"  WARNING: Could not parse {p.name}")
    return all_flags


def html_escape(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def render_flag_row(flag):
    """Render a single flagged document as an HTML card with checkbox."""
    slug = flag.get('slug', '')
    theme = flag.get('theme', '')
    rec = flag.get('recommendation', 'REVIEW')
    reason = flag.get('reason', '')
    criterion = flag.get('criterion', 0)
    criterion_label = CRITERION_LABELS.get(criterion, f'Criterion {criterion}')

    summary, size, garbage_ratio = get_doc_summary(theme, slug)
    size_kb = size / 1024 if size else 0

    rec_class = 'exclude' if rec == 'EXCLUDE' else 'review'
    reader_link = f'../{theme}/read/{slug}.html'
    checked = 'checked' if rec == 'EXCLUDE' else ''

    parts = []
    parts.append(f'<div class="flag-card flag-{rec_class}" data-slug="{html_escape(slug)}" data-theme="{html_escape(theme)}">')
    parts.append(f'  <div class="flag-header">')
    parts.append(f'    <label class="flag-check"><input type="checkbox" {checked} data-slug="{html_escape(slug)}" data-theme="{html_escape(theme)}"><span class="checkmark"></span></label>')
    parts.append(f'    <span class="flag-badge badge-{rec_class}">{html_escape(rec)}</span>')
    parts.append(f'    <span class="flag-criterion">{html_escape(criterion_label)}</span>')
    if size_kb > 0:
        parts.append(f'    <span class="flag-size">{size_kb:.0f} KB</span>')
    if garbage_ratio and garbage_ratio > 0.01:
        parts.append(f'    <span class="flag-garbage">{garbage_ratio:.1%} garbage</span>')
    parts.append(f'  </div>')
    parts.append(f'  <h3><a href="{reader_link}" target="_blank">{html_escape(slug)}</a></h3>')
    if summary:
        parts.append(f'  <p class="flag-summary">{html_escape(summary)}</p>')
    parts.append(f'  <p class="flag-reason"><strong>Reason:</strong> {html_escape(reason)}</p>')
    parts.append(f'</div>')
    return '\n'.join(parts)


PAGE_CSS = """
<style>
  .flag-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    margin: 0.8rem 0;
    border-left: 4px solid var(--card-border);
    transition: opacity 0.2s;
  }
  .flag-card.dimmed { opacity: 0.45; }
  .flag-exclude { border-left-color: #c0392b; }
  .flag-review { border-left-color: #e67e22; }
  .flag-header {
    display: flex;
    gap: 0.8rem;
    align-items: center;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }
  .flag-check {
    display: flex;
    align-items: center;
    cursor: pointer;
    flex-shrink: 0;
  }
  .flag-check input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
    accent-color: #c0392b;
  }
  .flag-badge {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
    font-family: -apple-system, sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .badge-exclude { background: #c0392b; color: #fff; }
  .badge-review { background: #e67e22; color: #fff; }
  .flag-criterion {
    font-size: 0.8rem;
    color: var(--muted);
    font-family: -apple-system, sans-serif;
  }
  .flag-size, .flag-garbage {
    font-size: 0.75rem;
    color: var(--muted);
    font-family: -apple-system, sans-serif;
  }
  .flag-garbage { color: #c0392b; }
  .flag-card h3 {
    margin: 0.3rem 0;
    font-size: 1.1rem;
  }
  .flag-summary {
    font-style: italic;
    color: var(--muted);
    font-size: 0.9rem;
    margin: 0.3rem 0;
  }
  .flag-reason {
    font-size: 0.9rem;
    margin: 0.3rem 0 0;
  }
  .theme-section {
    margin: 2rem 0;
  }
  .theme-section h2 {
    border-bottom: 2px solid var(--card-border);
    padding-bottom: 0.5rem;
    font-size: 1.4rem;
  }
  .stats-bar {
    display: flex;
    gap: 2rem;
    background: var(--sidebar-bg);
    padding: 1rem 1.5rem;
    border-radius: 8px;
    margin: 1rem 0 2rem;
    font-family: -apple-system, sans-serif;
    font-size: 0.9rem;
    flex-wrap: wrap;
  }
  .stats-bar .stat-num {
    font-size: 1.4rem;
    font-weight: bold;
    color: var(--accent);
  }
  .toc-list {
    list-style: none;
    padding: 0;
    columns: 2;
    column-gap: 2rem;
  }
  .toc-list li {
    padding: 0.3rem 0;
    font-family: -apple-system, sans-serif;
    font-size: 0.95rem;
  }
  .toc-count {
    color: var(--muted);
    font-size: 0.85rem;
  }
  /* Sticky toolbar */
  .review-toolbar {
    position: sticky;
    top: 0;
    z-index: 100;
    background: #1a1a2e;
    border-bottom: 2px solid var(--accent, #e67e22);
    padding: 0.7rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 1.2rem;
    flex-wrap: wrap;
    font-family: -apple-system, sans-serif;
    font-size: 0.9rem;
    color: #ccc;
  }
  .review-toolbar .toolbar-count {
    font-weight: bold;
    font-size: 1rem;
    color: #fff;
    min-width: 140px;
  }
  .review-toolbar .toolbar-count .num { color: var(--accent, #e67e22); }
  .review-toolbar button {
    padding: 0.35rem 0.8rem;
    border: 1px solid #555;
    border-radius: 4px;
    background: #2a2a4a;
    color: #ddd;
    cursor: pointer;
    font-size: 0.8rem;
    font-family: -apple-system, sans-serif;
    transition: background 0.15s;
  }
  .review-toolbar button:hover { background: #3a3a6a; }
  .review-toolbar button.primary {
    background: #c0392b;
    border-color: #c0392b;
    color: #fff;
  }
  .review-toolbar button.primary:hover { background: #e74c3c; }
  .toolbar-spacer { flex: 1; }
</style>
"""

PAGE_JS = """
<script>
(function() {
  const STORAGE_KEY = 'archiveReviewSelections';

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch(e) { return {}; }
  }

  function saveState(state) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function updateCounts() {
    const boxes = document.querySelectorAll('.flag-card input[type="checkbox"]');
    const checked = document.querySelectorAll('.flag-card input[type="checkbox"]:checked');
    const countEl = document.querySelector('.toolbar-count');
    if (countEl) {
      countEl.innerHTML = '<span class="num">' + checked.length + '</span> of ' + boxes.length + ' selected for exclusion';
    }
  }

  function applyDimming() {
    document.querySelectorAll('.flag-card').forEach(function(card) {
      const cb = card.querySelector('input[type="checkbox"]');
      if (cb) card.classList.toggle('dimmed', !cb.checked);
    });
  }

  function init() {
    const state = loadState();
    const boxes = document.querySelectorAll('.flag-card input[type="checkbox"]');

    // Restore saved state (overrides default checked/unchecked)
    boxes.forEach(function(cb) {
      const key = cb.dataset.theme + '/' + cb.dataset.slug;
      if (key in state) cb.checked = state[key];
    });

    // Listen for changes
    boxes.forEach(function(cb) {
      cb.addEventListener('change', function() {
        var st = loadState();
        st[cb.dataset.theme + '/' + cb.dataset.slug] = cb.checked;
        saveState(st);
        updateCounts();
        applyDimming();
      });
    });

    applyDimming();
    updateCounts();

    // Select all / deselect all
    var selAll = document.getElementById('select-all');
    if (selAll) selAll.addEventListener('click', function() {
      var st = loadState();
      boxes.forEach(function(cb) { cb.checked = true; st[cb.dataset.theme + '/' + cb.dataset.slug] = true; });
      saveState(st);
      updateCounts();
      applyDimming();
    });

    var deselAll = document.getElementById('deselect-all');
    if (deselAll) deselAll.addEventListener('click', function() {
      var st = loadState();
      boxes.forEach(function(cb) { cb.checked = false; st[cb.dataset.theme + '/' + cb.dataset.slug] = false; });
      saveState(st);
      updateCounts();
      applyDimming();
    });

    // Download exclusion list
    var dlBtn = document.getElementById('download-exclusions');
    if (dlBtn) dlBtn.addEventListener('click', function() {
      var exclusions = [];
      document.querySelectorAll('.flag-card input[type="checkbox"]:checked').forEach(function(cb) {
        exclusions.push({ slug: cb.dataset.slug, theme: cb.dataset.theme });
      });
      var blob = new Blob([JSON.stringify(exclusions, null, 2)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'exclusions.json';
      a.click();
      URL.revokeObjectURL(a.href);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>
"""


TOOLBAR_HTML = """
<div class="review-toolbar">
  <span class="toolbar-count"><span class="num">0</span> of 0 selected for exclusion</span>
  <span class="toolbar-spacer"></span>
  <button id="select-all">Select All</button>
  <button id="deselect-all">Deselect All</button>
  <button id="download-exclusions" class="primary">Download Exclusions</button>
</div>
"""


def render_page(title, subtitle, body_html, breadcrumbs=None):
    """Wrap body content in the standard page template."""
    bc = ''
    if breadcrumbs:
        bc_parts = []
        for label, href in breadcrumbs[:-1]:
            bc_parts.append(f'<a href="{href}">{html_escape(label)}</a>')
        bc_parts.append(html_escape(breadcrumbs[-1][0]))
        bc = '<div class="breadcrumb">' + ' <span class="sep">&rsaquo;</span> '.join(bc_parts) + '</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_escape(title)}</title>
<link rel="stylesheet" href="../css/style.css">
{PAGE_CSS}
</head>
<body>
{TOOLBAR_HTML}
<header class="site-header">
  <h1>{html_escape(title)}</h1>
  <div class="subtitle">{html_escape(subtitle)}</div>
</header>
<main class="container">
{bc}
{body_html}
</main>
<footer class="site-footer">
  <a href="../index.html">Archive Home</a>
</footer>
{PAGE_JS}
</body>
</html>
"""


def main():
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    all_flags = load_all_flags()
    print(f"Loaded {len(all_flags)} flagged documents")

    if not all_flags:
        print("No flags found. Make sure review agents have completed.")
        return

    # Group by theme
    by_theme = defaultdict(list)
    for flag in all_flags:
        by_theme[flag.get('theme', 'unknown')].append(flag)

    # Sort each theme's flags: EXCLUDE first, then REVIEW
    for theme in by_theme:
        by_theme[theme].sort(key=lambda f: (0 if f.get('recommendation') == 'EXCLUDE' else 1, f.get('slug', '')))

    # Count stats
    total_exclude = sum(1 for f in all_flags if f.get('recommendation') == 'EXCLUDE')
    total_review = sum(1 for f in all_flags if f.get('recommendation') == 'REVIEW')

    # Criterion breakdown
    by_criterion = defaultdict(int)
    for f in all_flags:
        by_criterion[f.get('criterion', 0)] += 1

    # ── Generate per-theme pages ──
    for theme in sorted(by_theme.keys()):
        flags = by_theme[theme]
        theme_label = THEME_NAMES.get(theme, theme)
        n_exclude = sum(1 for f in flags if f.get('recommendation') == 'EXCLUDE')
        n_review = sum(1 for f in flags if f.get('recommendation') == 'REVIEW')

        body = []
        body.append(f'<div class="stats-bar">')
        body.append(f'  <div><span class="stat-num">{len(flags)}</span> flagged</div>')
        body.append(f'  <div><span class="stat-num">{n_exclude}</span> exclude</div>')
        body.append(f'  <div><span class="stat-num">{n_review}</span> review</div>')
        body.append(f'</div>')

        for flag in flags:
            body.append(render_flag_row(flag))

        html = render_page(
            title=f'Review: {theme_label}',
            subtitle=f'{len(flags)} documents flagged for review',
            body_html='\n'.join(body),
            breadcrumbs=[('Review Home', 'index.html'), (theme_label, '')]
        )

        out_path = REVIEW_DIR / f'{theme}.html'
        out_path.write_text(html)
        print(f"  {theme}.html: {len(flags)} flags ({n_exclude} exclude, {n_review} review)")

    # ── Generate master index ──
    body = []
    body.append(f'<div class="stats-bar">')
    body.append(f'  <div><span class="stat-num">{len(all_flags)}</span> total flagged</div>')
    body.append(f'  <div><span class="stat-num">{total_exclude}</span> exclude</div>')
    body.append(f'  <div><span class="stat-num">{total_review}</span> review</div>')
    body.append(f'  <div><span class="stat-num">{len(by_theme)}</span> themes</div>')
    body.append(f'</div>')

    # Criterion breakdown
    body.append(f'<h2>By Criterion</h2>')
    body.append(f'<div class="stats-bar">')
    for crit in sorted(by_criterion.keys()):
        label = CRITERION_LABELS.get(crit, f'#{crit}')
        body.append(f'  <div><span class="stat-num">{by_criterion[crit]}</span> {html_escape(label)}</div>')
    body.append(f'</div>')

    # Table of contents
    body.append(f'<h2>By Theme</h2>')
    body.append(f'<ul class="toc-list">')
    for theme in sorted(by_theme.keys()):
        flags = by_theme[theme]
        theme_label = THEME_NAMES.get(theme, theme)
        n_exclude = sum(1 for f in flags if f.get('recommendation') == 'EXCLUDE')
        n_review = len(flags) - n_exclude
        body.append(f'  <li><a href="{theme}.html">{html_escape(theme_label)}</a> '
                     f'<span class="toc-count">({n_exclude}E / {n_review}R)</span></li>')
    body.append(f'</ul>')

    # All flags inline
    body.append(f'<h2>All Flagged Documents</h2>')
    for theme in sorted(by_theme.keys()):
        flags = by_theme[theme]
        theme_label = THEME_NAMES.get(theme, theme)
        body.append(f'<div class="theme-section">')
        body.append(f'  <h2>{html_escape(theme_label)} ({len(flags)})</h2>')
        for flag in flags:
            body.append(render_flag_row(flag))
        body.append(f'</div>')

    html = render_page(
        title='Archive Content Review',
        subtitle=f'{len(all_flags)} documents flagged for potential exclusion',
        body_html='\n'.join(body),
    )

    out_path = REVIEW_DIR / 'index.html'
    out_path.write_text(html)
    print(f"\n  index.html: master review page")
    print(f"\nDone! Open review/index.html to review flagged documents.")


if __name__ == '__main__':
    main()
