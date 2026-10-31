#!/usr/bin/env python3
"""Build a compact title catalogue from the active Pagefind 1.4 index and collection links.

Only published readers/originals are included. The small CBOR reader follows Pagefind
1.4's metadata schema; fail explicitly when the pinned engine version changes.
"""
import argparse
import gzip
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

def decode_cbor(data):
    cursor = 0
    def read():
        nonlocal cursor
        head = data[cursor]; cursor += 1
        kind, size = head >> 5, head & 31
        if size >= 24:
            width = {24:1, 25:2, 26:4, 27:8}.get(size)
            if width is None: raise ValueError('Unsupported Pagefind metadata encoding')
            size = int.from_bytes(data[cursor:cursor+width], 'big'); cursor += width
        if kind == 0: return size
        if kind == 3:
            value = data[cursor:cursor+size].decode(); cursor += size; return value
        if kind == 4: return [read() for _ in range(size)]
        raise ValueError('Unsupported Pagefind metadata type')
    return read()

class CollectionRows(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=-1; self.title=[]; self.badge=0; self.links=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='tr': self.row=True; self.cell=-1; self.title=[]; self.links=[]
        if self.row is not None:
            if tag=='td': self.cell+=1
            if tag=='span' and 'badge' in attrs.get('class',''): self.badge+=1
            if tag=='a' and attrs.get('href'): self.links.append(attrs['href'])
    def handle_data(self, data):
        if self.row and self.cell==1 and not self.badge: self.title.append(data)
    def handle_endtag(self, tag):
        if tag=='span' and self.badge: self.badge-=1
        if tag=='tr' and self.row:
            self.rows.append((' '.join(''.join(self.title).split()),self.links)); self.row=None

def build():
    index=json.loads((ROOT/'pagefind/pagefind-entry.json').read_text())
    if index['version'] != '1.4.0': raise ValueError('Review title catalogue builder for new Pagefind version')
    entries=[]; urls=set()
    for lang in index['languages'].values():
        meta=decode_cbor(gzip.decompress((ROOT/f"pagefind/pagefind.{lang['hash']}.pf_meta").read_bytes())[12:])
        assert len(meta[1])==lang['page_count']
        for fragment_id, _ in meta[1]:
            fragment=json.loads(gzip.decompress((ROOT/f'pagefind/fragment/{fragment_id}.pf_fragment').read_bytes())[12:])
            url=fragment['url'].lstrip('/')
            assert (ROOT/unquote(url)).is_file(), url
            entries.append({'id':fragment_id,'title':fragment['meta']['title'],'url':url,'filters':fragment['filters']})
            urls.add(url)
    downloads=0
    for index_path in sorted(ROOT.glob('[0-9][0-9]-*/index.html')):
        parser=CollectionRows(); parser.feed(index_path.read_text())
        # Collection title is already recorded in the indexed readers.
        prefix=index_path.parent.name+'/'
        theme=next((e['filters']['theme'][0] for e in entries if e['url'].startswith(prefix)), None)
        if theme is None: continue
        for title, links in parser.rows:
            if any(link.startswith('read/') for link in links): continue
            download=next((link for link in links if link.startswith('files/')), None)
            if not download: continue
            url=prefix+download
            if url in urls: continue
            assert (ROOT/unquote(url)).is_file(), url
            entries.append({'id':'download-'+hashlib.sha256(url.encode()).hexdigest()[:12],
                            'title':title,'url':url,'filters':{'theme':[theme]},'downloadOnly':True})
            urls.add(url); downloads+=1
    entries.sort(key=lambda e:(e['url'],e['id']))
    return {'version':1,'pagefindVersion':index['version'],'downloadOnlyCount':downloads,'entries':entries}

if __name__=='__main__':
    args=argparse.ArgumentParser(); args.add_argument('--check',action='store_true'); options=args.parse_args()
    content=json.dumps(build(),ensure_ascii=False,separators=(',',':'))+'\n'
    output=ROOT/'search/titles.json'
    if options.check:
        assert output.read_text()==content, 'Title catalogue is stale; run python3 scripts/build_search_titles.py'
    else:
        output.parent.mkdir(exist_ok=True); output.write_text(content)
    data=json.loads(content)
    print(f"Title catalogue: {len(data['entries'])} entries, including {data['downloadOnlyCount']} download-only documents")
