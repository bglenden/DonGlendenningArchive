#!/usr/bin/env python3
"""Validate current public collection links, reader assets, controls, and count labels."""
import re
import subprocess
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from build_search_titles import CollectionRows

ROOT=Path(__file__).resolve().parent.parent
ARCHIVE_PATHS=set(subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0'))

def require_file(path, context):
    assert path.is_file(), f'Missing archive file: {context}: {path}'
    relative=path.relative_to(ROOT).as_posix()
    assert relative in ARCHIVE_PATHS, f'Link spelling/case/Unicode differs from Git filename: {context}: {relative}'

class Elements(HTMLParser):
    def __init__(self): super().__init__(); self.tags=[]
    def handle_starttag(self,tag,attrs): self.tags.append((tag,dict(attrs)))

def local_target(base, url):
    parts=urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path: return None
    return (base/unquote(parts.path)).resolve()

def validate():
    readers=set(ROOT.glob('[0-9][0-9]-*/read/*.html'))
    linked=set(); originals=set(); variants=defaultdict(set)
    primary_rows=0; primary_highlights=0; buttons=0; images=0
    for index in sorted(ROOT.glob('[0-9][0-9]-*/index.html')):
        text=index.read_text(); rows=CollectionRows();rows.feed(text)
        elements=Elements();elements.feed(text)
        ids={a['id'] for _,a in elements.tags if 'id' in a}
        assert len(ids)==sum('id' in a for _,a in elements.tags),f'Duplicate IDs: {index}'
        assert 'onkeyup="filterTable()"' not in text
        assert any(t=='label' and a.get('for')=='searchInput' for t,a in elements.tags),index
        for tag,attrs in elements.tags:
            if 'expand-btn' in attrs.get('class',''):
                assert tag=='button' and attrs.get('aria-controls') in ids and attrs.get('aria-expanded')=='false',index
                buttons+=1
        for title,links in rows.rows:
            if not title: continue
            paths=[local_target(index.parent,link) for link in links]
            for path in paths:
                if path: require_file(path,index)
            read=next((p for p in paths if p in readers),None)
            download=next((p for p in paths if p and p.parent.name=='files'),None)
            if read: linked.add(read)
            if read and download: variants[read].add(download)
            if index.parent.name!='12-letters-to-editor':
                primary_rows+=1
                if download: originals.add(download)
        if index.parent.name!='12-letters-to-editor': primary_highlights+=len(re.findall(r'<tr\b[^>]*data-highlight=',text))
    assert linked==readers,f'Readers missing from collections: {readers-linked}'
    for reader in sorted(readers):
        text=reader.read_text();elements=Elements();elements.feed(text)
        for tag,attrs in elements.tags:
            if tag=='img' and 'src' in attrs:
                target=local_target(reader.parent,attrs['src'])
                if target: require_file(target,reader)
                images+=1
        assert 'Search archive</a>' in text,f'No archive-search navigation: {reader}'
        if len(variants[reader])>1:
            assert 'class="variant-note"' in text,f'Unexplained shared reading page: {reader}'
    home=(ROOT/'index.html').read_text()
    assert f'<span class="stat-num">{primary_rows}</span> catalog entries' in home
    assert f'<span class="stat-num">{primary_highlights}</span> family highlights' in home
    assert primary_rows==len(originals)
    print(f'Archive checks passed: {primary_rows} primary entries, {len(readers)} linked readers, {buttons} accessible summary buttons, {images} image references, {sum(len(v)>1 for v in variants.values())} explained shared readers.')

if __name__=='__main__': validate()
