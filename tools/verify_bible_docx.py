#!/usr/bin/env python3
"""Check src/advanced.json against an independent pandoc text extraction of the Bible .docx.

    python3 -I tools/verify_bible_docx.py <400-Question-IB-Bible.docx> src/advanced.json

Compares the words of the six Advanced sections in order. List markers, the book's footer URLs and
table cells (which pandoc lays out as a grid) are set aside; the table is compared separately.
"""
import difflib, html, json, re, subprocess, sys
DOCX, JSON = sys.argv[1], sys.argv[2]
D = json.load(open(JSON, encoding='utf-8'))
HEADS = ['Accounting Questions & Answers – Advanced', 'Enterprise / Equity Value Questions & Answers – Advanced',
         'Valuation Questions & Answers – Advanced', 'Discounted Cash Flow Questions & Answers – Advanced',
         'Merger Model Questions & Answers – Advanced', 'LBO Model Questions & Answers – Advanced']
ENDS = ['Enterprise / Equity Value Questions & Answers – Basic', 'Valuation Questions & Answers – Basic',
        'Discounted Cash Flow Questions & Answers – Basic', 'Merger Model Questions & Answers – Basic',
        'LBO Model Questions & Answers – Basic', 'Brain Teaser Questions & Answers']
raw = subprocess.run(['pandoc', '-t', 'plain', '--wrap=none', DOCX], capture_output=True, text=True).stdout
def section(h, e):
    s = [m.start() for m in re.finditer(re.escape(h), raw)][-1]            # last occurrence: the body, not the contents page
    t = raw.index(e, s)
    return raw[s + len(h):t]
def strip_tags(h): return html.unescape(re.sub(r'<[^>]+>', '', h))
FOOT = re.compile(r'https?://(www\.)?(breakingintowallstreet|mergersandinquisitions)\.com/?')
def norm(text):
    text = FOOT.sub(' ', text)
    out = []
    for line in text.splitlines():
        line = re.sub(r'^\s*(?:[-•*·]|\d+\.)\s+', '', line)                   # list markers
        if re.fullmatch(r'[\s+=\-|:]*', line): continue                       # table rules
        out.append(line)
    return re.sub(r'\s+', ' ', ' '.join(out)).strip().split()
bad_total, tokens_total = 0, 0
for (h, e, (sid, _)) in zip(HEADS, ENDS, [('01', ''), ('02', ''), ('03', ''), ('04', ''), ('05', ''), ('06', '')]):
    exp = [next(s['intro'] for s in D['sections'] if s['id'] == sid)]
    for q in D['questions']:
        if q['section'] != sid: continue
        exp.append(q['question'])
        for b in q['answer']:
            if b['type'] == 'table': continue
            exp.append(strip_tags(b['html']))
    # pandoc lays the table out as a grid, so drop table words from both sides
    tbl = {w for q in D['questions'] if q['section'] == sid for b in q['answer'] if b['type'] == 'table' for r in b['rows'] for c in r for w in c.split()}
    a = norm(section(h, e)); b = norm(' '.join(exp))
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        da, db = a[i1:i2], b[j1:j2]
        if not db and (all(w in tbl or w in '|' for w in da) or da[:1] == ['|']): continue      # the table grid, checked below
        diffs.append((tag, ' '.join(da)[:140], ' '.join(db)[:140]))
    tokens_total += len(b); bad_total += len(diffs)
    print(f'{h[:46]:48} docx {len(a):5} words, data {len(b):5} words, {len(diffs)} differences')
    for d in diffs[:6]: print('    ', d)
# the one real table, cell by cell against the document itself
import docx
src = docx.Document(DOCX).tables[0]
want = [[re.sub(r'\s+', ' ', ' '.join(p.text for p in c.paragraphs)).strip() for c in row.cells] for row in src.rows]
got = next(b['rows'] for q in D['questions'] for b in q['answer'] if b['type'] == 'table' and len(b['rows'][0]) == 7 and b['rows'][0][0] == 'Debt Type')
print('debt table identical cell by cell:', want == got, f'({len(want)} rows x {len(want[0])} columns)')
bad_total += 0 if want == got else 1
print('TOTAL differences:', bad_total, 'over', tokens_total, 'words')
