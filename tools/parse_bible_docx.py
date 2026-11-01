#!/usr/bin/env python3
"""Pull the six 'Advanced' technical sections out of the 400-question IB Bible .docx.

    python3 -I tools/parse_bible_docx.py <400-Question-IB-Bible.docx> src/advanced.json

Walks the document body in true order (so the table lands where it sits), keeps bold, italic,
underline, bullets and numbered lists, and keeps the wording exactly. Three layout repairs, none of
which changes a word:
  * the book's repeated promotional footer lines (two website URLs) are dropped;
  * heading-styled lines with no question number are not questions: "Stock Purchase:" style labels
    become bold lines inside the answer above them, and a heading-styled line that continues a sentence
    ("... Equity Value" / "and also subtract the IPO proceeds ...") is joined back onto it;
  * the stub-period lines that use tab alignment are turned into a small table.
"""
import html, json, re, sys
import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

SRC, OUT = sys.argv[1], sys.argv[2]
# docx heading -> (id of the matching section in the Moelis PDF, short title used in the app)
ADV = {
    'Accounting Questions & Answers – Advanced': ('01', 'Accounting'),
    'Enterprise / Equity Value Questions & Answers – Advanced': ('02', 'Equity Value and Enterprise Value'),
    'Valuation Questions & Answers – Advanced': ('03', 'Valuation'),
    'Discounted Cash Flow Questions & Answers – Advanced': ('04', 'DCF and WACC'),
    'Merger Model Questions & Answers – Advanced': ('05', 'Merger Models'),
    'LBO Model Questions & Answers – Advanced': ('06', 'Leveraged Buyouts'),
}
FOOTER = re.compile(r'^\s*(https?://(www\.)?(breakingintowallstreet|mergersandinquisitions)\.com/?\s*)+$')

d = docx.Document(SRC)
numpart = d.part.numbering_part.element
ABS, NUM = {}, {}
for a in numpart.findall(qn('w:abstractNum')):
    ABS[a.get(qn('w:abstractNumId'))] = {int(l.get(qn('w:ilvl'))): l.find(qn('w:numFmt')).get(qn('w:val')) for l in a.findall(qn('w:lvl'))}
for n in numpart.findall(qn('w:num')):
    NUM[n.get(qn('w:numId'))] = n.find(qn('w:abstractNumId')).get(qn('w:val'))

def numpr(p):
    pr = p._p.pPr
    if pr is not None and pr.numPr is not None and pr.numPr.numId is not None:
        return str(pr.numPr.numId.val), (pr.numPr.ilvl.val if pr.numPr.ilvl is not None else 0)
    return None

def runs(p):
    out = []
    for r in p._p.iter(qn('w:r')):
        rpr = r.find(qn('w:rPr'))
        def on(tag):
            e = rpr.find(qn(tag)) if rpr is not None else None
            return e is not None and e.get(qn('w:val')) not in ('0', 'false', 'none')
        t = ''
        for ch in r:
            if ch.tag == qn('w:t'): t += ch.text or ''
            elif ch.tag == qn('w:tab'): t += '\t'
            elif ch.tag in (qn('w:br'), qn('w:cr')): t += ' '
            elif ch.tag == qn('w:noBreakHyphen'): t += '-'
        if t: out.append((t, on('w:b'), on('w:i'), on('w:u')))
    return out

def plain(p):
    return ''.join(t for t, *_ in runs(p))

def to_html(rs, force_bold=False):
    merged = []
    for t, b, i, u in rs:
        b = b or force_bold
        if merged and merged[-1][1:] == (b, i, u): merged[-1] = (merged[-1][0] + t, b, i, u)
        else: merged.append((t, b, i, u))
    out = ''
    for t, b, i, u in merged:
        t = re.sub(r'[ \t \n]+', ' ', t)
        lead, core, trail = re.match(r'^( *)(.*?)( *)$', t, re.S).groups()
        core = html.escape(core, quote=False)
        if core:
            for flag, tag in ((u, 'u'), (i, 'i'), (b, 'b')):
                if flag: core = f'<{tag}>{core}</{tag}>'
        out += lead + core + trail
    return re.sub(r' +', ' ', out).strip()

def strip_html(h): return html.unescape(re.sub(r'<[^>]+>', '', h)).strip()

def cell_text(c):
    return re.sub(r'\s+', ' ', ' '.join(p.text for p in c.paragraphs)).strip()

questions, cur_sec, q, counters, label_n = [], None, None, {}, 0
intros = {v[0]: [] for v in ADV.values()}
def fmt_of(nid, lvl): return ABS[NUM[nid]].get(lvl)

for el in d.element.body.iterchildren():
    if el.tag == qn('w:tbl'):
        if q is not None:
            t = Table(el, d)
            q['answer'].append({'type': 'table', 'rows': [[cell_text(c) for c in row.cells] for row in t.rows]})
        continue
    if el.tag != qn('w:p'): continue
    p = Paragraph(el, d); style = p.style.name; text = plain(p)
    if style == 'Heading 2':
        cur_sec = ADV.get(p.text.strip()); q = None
        continue
    if style in ('Heading 1', 'Title'): cur_sec = None; q = None
    if cur_sec is None: continue
    if not text.strip() or FOOTER.match(text): continue
    npr = numpr(p)
    if style == 'Heading 5' and npr:                         # a real, numbered question
        label_n += 1
        q = {'label': f'A{label_n}', 'section': cur_sec[0], 'section_title': cur_sec[1], 'question': re.sub(r'\s+', ' ', text).strip(), 'answer': []}
        questions.append(q)
        for k in [k for k in counters if k[0] == npr[0] and k[1] > npr[1]]: counters.pop(k)     # the question resets its sub-list
        continue
    if q is None:
        intros[cur_sec[0]].append(to_html(runs(p)))        # the short note under the section heading
        continue
    blocks = q['answer']
    if style == 'Heading 5':                                  # unnumbered heading-styled line
        if '\t' in text: blocks.append({'type': 'tabrow', 'text': text})
        elif text.strip().endswith(':'): blocks.append({'type': 'p', 'html': to_html(runs(p), force_bold=True)})
        elif blocks and blocks[-1]['type'] in ('p', 'li'): blocks[-1]['html'] += ' ' + to_html(runs(p))
        else: blocks.append({'type': 'p', 'html': to_html(runs(p))})
        continue
    if '\t' in text and not npr:
        blocks.append({'type': 'tabrow', 'text': text}); continue
    if npr and style == 'List Paragraph':
        nid, lvl = npr
        for k in [k for k in counters if k[0] == nid and k[1] > lvl]: counters.pop(k)
        counters[(nid, lvl)] = counters.get((nid, lvl), 0) + 1
        kind = 'bullet' if fmt_of(nid, lvl) == 'bullet' else 'num'
        blocks.append({'type': 'li', 'kind': kind, 'n': counters[(nid, lvl)], 'html': to_html(runs(p))})
        continue
    blocks.append({'type': 'p', 'html': to_html(runs(p))})

# The book was converted from a fixed-width layout, so some sentences are wrapped onto the next
# paragraph. Rejoin a plain paragraph onto the previous one only when it clearly continues it.
CONNECT = {'the', 'of', 'a', 'an', 'and', 'or', 'to', 'in', 'for', 'with', 'by', 'is', 'are', 'that', 'its', 'their', 'as', 'at', 'on'}
TERMINAL = tuple('.?!:;)\u201d"\u2019\'')
# three wrapped sentences the rules above cannot tell from a new paragraph (checked by hand)
FORCE_JOIN = {('A7', 'retained'), ('A34', 'subtract'), ('A39', 'dividing')}
joined, review = [], []
def visible(h): return re.sub(r'<[^>]+>', '', h)
for qq in questions:
    out = []
    for b in qq['answer']:
        prev = out[-1] if out else None
        if prev and prev['type'] in ('p', 'li') and b['type'] == 'p':
            pv, nv = visible(prev['html']).rstrip(), visible(b['html']).lstrip()
            lower = nv[:1].islower()
            open_paren = pv.count('(') > pv.count(')')
            tail = pv.split()[-1].lower().strip('.,;') if pv.split() else ''
            if lower or open_paren or (tail in CONNECT and not pv.endswith(TERMINAL)) or (qq['label'], tail) in FORCE_JOIN:
                prev['html'] = prev['html'].rstrip() + ' ' + b['html'].lstrip()
                joined.append((qq['label'], pv[-40:], nv[:40])); continue
            if not pv.endswith(TERMINAL): review.append((qq['label'], pv[-50:], nv[:50]))
        out.append(b)
    qq['answer'] = out
print(len(joined), 'wrapped lines rejoined')
for j in joined: print('  JOIN', j)
print(len(review), 'paragraphs that end without punctuation but were left alone:')
for r in review: print('  KEEP', r)

# tab-aligned lines -> table
for qq in questions:
    out, rows = [], []
    def flush():
        global rows
        if not rows: return
        hdr = rows[0].split('\t')
        cols = [hdr[0]] + [x for part in hdr[1:] for x in re.split(r'\s+(?=Year \d)', part.strip())]
        body = [[c.strip() for c in r.split('\t')] for r in rows[1:]]
        width = max(len(cols), *(len(r) for r in body)) if body else len(cols)
        out.append({'type': 'table', 'rows': [[''] + cols] + [[r[0]] + r[1:] for r in body]})
        rows = []
    for b in qq['answer']:
        if b['type'] == 'tabrow': rows.append(b['text'])
        else:
            flush(); out.append(b)
    flush(); qq['answer'] = out

problems = []
for qq in questions:
    if not qq['answer']: problems.append(qq['label'] + ' has no answer')
    for b in qq['answer']:
        if b['type'] == 'table' and len({len(r) for r in b['rows']}) != 1: problems.append(qq['label'] + ' ragged table ' + str([len(r) for r in b['rows']]))
json.dump({'sections': [{'id': v[0], 'title': v[1], 'intro': strip_html(' '.join(intros[v[0]]))} for v in ADV.values()], 'questions': questions}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
from collections import Counter
print(len(questions), 'advanced questions;', dict(Counter(q['section'] for q in questions)), '|', len(problems), 'problems')
for x in problems: print('  -', x)
