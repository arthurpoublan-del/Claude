"""Parse the Moelis first-round technicals PDF into structured JSON.
Usage: python3 -I parse_pdf.py in.pdf out.json
Everything is read from font, colour and position data so the wording is exact."""
import pdfplumber, json, re, sys, html, collections

SRC, OUT = sys.argv[1], sys.argv[2]
GOLD, NAVY, GREY, DARK = (0.72, 0.53, 0.17), (0.08, 0.16, 0.29), (0.36, 0.39, 0.45), (0.12, 0.14, 0.16)
LEAD = {9.3: 13.6, 9.0: 13.2, 8.9: 12.8}      # normal line spacing by font size
problems = []

def col(w):
    c = w.get('non_stroking_color') or (0,)
    return tuple(round(x, 2) for x in c)
def W(w):
    f = w['fontname']
    return dict(t=w['text'], x0=w['x0'], x1=w['x1'], top=w['top'], bottom=w['bottom'], size=round(w['size'], 1),
                bold='Bold' in f, ital='Oblique' in f, serif='Serif' in f, col=col(w))

def page_lines(page, pno):
    ws = [W(w) for w in page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False,
                                           extra_attrs=['fontname', 'size', 'non_stroking_color'])]
    body, sups = [], []
    for w in ws:
        if w['col'] == GREY and w['size'] == 7.5 and (w['top'] < 40 or w['top'] > 780): continue      # header and page number
        (sups if (w['size'] <= 7.3 and w['col'] == DARK) else body).append(w)
    body.sort(key=lambda w: (round(w['bottom'] / 1.5), w['x0']))
    lines = []
    for w in sorted(body, key=lambda w: (w['bottom'], w['x0'])):
        if lines and abs(w['bottom'] - lines[-1]['bottom']) <= 2.2:
            lines[-1]['words'].append(w)
        else:
            lines.append({'bottom': w['bottom'], 'words': [w]})
    for s in sups:
        tgt = min(lines, key=lambda l: abs(l['bottom'] - s['bottom'] - 2.5))
        s = dict(s, sup=True); tgt['words'].append(s)
    out = []
    for l in lines:
        ws_ = sorted(l['words'], key=lambda w: w['x0'])
        out.append({'page': pno, 'top': min(w['top'] for w in ws_ if not w.get('sup')), 'x0': ws_[0]['x0'], 'x1': max(w['x1'] for w in ws_), 'words': ws_})
    return sorted(out, key=lambda l: l['top'])

def text_of(words):
    s = ''
    for i, w in enumerate(words):
        if i and (w['x0'] - words[i - 1]['x1'] > 1.0): s += ' '
        s += w['t']
    return s

def rich(words):
    """HTML with <b>, <i>, <sup> kept; text escaped."""
    parts = []
    for i, w in enumerate(words):
        sp = bool(i and (w['x0'] - words[i - 1]['x1'] > 1.0))
        parts.append((sp, w))
    out, open_ = '', None
    def tag(w): return ('sup' if w.get('sup') else 'b' if (w['bold'] and not (w['col'] == NAVY)) else 'i' if (w['ital'] and w['col'] != NAVY and w['col'] != GREY) else None)
    for sp, w in parts:
        t = tag(w)
        if t != open_:
            if open_: out += f'</{open_}>'
            if sp: out += ' '; sp = False
            if t: out += f'<{t}>'
            open_ = t
        if sp: out += ' '
        out += html.escape(w['t'], quote=False)
    if open_: out += f'</{open_}>'
    return out

def first(l): return l['words'][0]
def is_label(l, name): return first(l)['col'] == GOLD and first(l)['bold'] and first(l)['size'] == 7.5 and text_of(l['words']) == name
def gapmax(l): return max([b['x0'] - a['x1'] for a, b in zip(l['words'], l['words'][1:])] + [0])

def paragraphs(lines, size_key=None):
    """lines -> list of blocks. paragraph break on extra vertical gap, tables on wide column gaps."""
    blocks, cur, prev, tbl = [], [], None, []
    def flush():
        nonlocal cur
        if cur: blocks.append({'type': 'p', 'html': ' '.join(rich(c) if isinstance(c, list) else c for c in cur)}); cur = []
    def flush_tbl():
        nonlocal tbl
        if not tbl: return
        xs = sorted({round(c[0]['x0']) for r in tbl for c in r})
        cols = []
        for x in xs:
            if not cols or x - cols[-1][-1] > 8: cols.append([x])
            else: cols[-1].append(x)
        centers = [min(c) for c in cols]
        rows = []
        for r in tbl:
            row = [''] * len(centers)
            for cell in r:
                ci = min(range(len(centers)), key=lambda i: abs(centers[i] - cell[0]['x0']))
                row[ci] = text_of(cell)
            rows.append(row)
        blocks.append({'type': 'table', 'rows': rows}); tbl = []
    for l in lines:
        if gapmax(l) > 14:        # table row: split into cells on wide gaps
            flush()
            cells, c = [], [l['words'][0]]
            for a, b in zip(l['words'], l['words'][1:]):
                if b['x0'] - a['x1'] > 14: cells.append(c); c = [b]
                else: c.append(b)
            cells.append(c); tbl.append(cells); prev = l; continue
        flush_tbl()
        sz = first(l)['size']
        lead = LEAD.get(sz, 13.6)
        newp = prev is None or prev['page'] != l['page'] or (l['top'] - prev['top']) - lead > 0.7
        if prev and prev['page'] != l['page']: problems.append(f"block continues across pages at p{l['page']}")
        if newp: flush()
        cur.append(l['words']); prev = l
    flush(); flush_tbl()
    return blocks

pdf = pdfplumber.open(SRC)
LINES = []
for i, p in enumerate(pdf.pages, 1):
    LINES += page_lines(p, i)

parts, sections, questions = {}, [], []
sec = None; group = None; q = None; state = None; i = 0
body_buf = []
def close_q():
    global q, body_buf
    if q is None: return
    q['_buf'] = None
    questions.append(q); q = None

def finish_body():
    """turn buffered lines of the current state into blocks"""
    global body_buf
    if q is None or not body_buf: body_buf = []; return
    if state == 'answer': q['answer'] = paragraphs(body_buf)
    elif state == 'why': q['why'] = paragraphs(body_buf)
    elif state == 'push':
        pushes, cur = [], None
        for l in body_buf:
            f = first(l)
            if f['ital'] and f['col'] == NAVY:
                if cur is None or cur['a_lines']: cur = {'q_lines': [], 'a_lines': []}; pushes.append(cur)
                cur['q_lines'].append(l)
            else:
                cur['a_lines'].append(l)
        q['push'] = [{'q': ' '.join(text_of(x['words']) for x in p['q_lines']), 'a': paragraphs(p['a_lines'])} for p in pushes]
    body_buf = []

for ln in LINES:
    f = first(ln); txt = text_of(ln['words']); pno = ln['page']
    if pno <= 2: continue
    if pno in (3, 58):                                  # part title pages
        key = 'part1' if pno == 3 else 'part2'
        d = parts.setdefault(key, {'title': [], 'intro': []})
        if f['size'] >= 28: d['title'].append(txt)
        elif f['size'] == 10.5: d['intro'].append(txt)
        continue
    if f['bold'] and f['serif'] and f['size'] == 20.0 and f['col'] == GOLD:       # section heading
        finish_body(); close_q(); state = None
        num = f['t']; title = text_of(ln['words'][1:])
        if num == 'A': break                                       # appendix: not part of the drill
        sec = {'id': num, 'title': title, 'intro': [], 'page': pno}; sections.append(sec); group = None; continue
    if sec is not None and q is None and not sec['intro'] and f['bold'] and f['serif'] and f['size'] == 20.0 and f['col'] == NAVY:
        sec['title'] += ' ' + txt; continue                          # wrapped section title
    if f['bold'] and f['serif'] and f['size'] == 13.5 and f['col'] == NAVY:        # sub-heading inside a section
        finish_body(); close_q(); state = None; group = txt; continue
    if sec is not None and q is None and f['ital'] and f['col'] == GREY and f['size'] == 9.5:     # section intro
        sec['intro'].append(txt); continue
    m = re.fullmatch(r'Q(\d+)\.', f['t']) if (f['bold'] and f['col'] == GOLD and f['size'] == 10.5) else None
    if m:
        finish_body(); close_q(); state = 'question'
        q = {'n': int(m.group(1)), 'section': sec['id'], 'group': group, 'q_lines': [ln], 'reported': [], 'page': pno}
        continue
    if q is None:
        problems.append(f"ignored line before a question p{pno}: {txt[:70]}"); continue
    if state == 'question' and f['bold'] and f['col'] == NAVY and f['size'] == 10.5:
        q['q_lines'].append(ln); continue
    if f['bold'] and f['col'] == GOLD and f['size'] == 8.0 and f['t'] == 'REPORTED':
        q['reported'].append(text_of(ln['words'][1:])); state = 'reported'; continue
    if state == 'reported' and f['ital'] and f['col'] == GREY and f['size'] == 8.0:
        q['reported'].append(txt); continue
    if is_label(ln, 'ANSWER'): finish_body(); state = 'answer'; continue
    if is_label(ln, "WHY IT'S RIGHT"): finish_body(); state = 'why'; continue
    if is_label(ln, 'IF THEY PUSH'): finish_body(); state = 'push'; continue
    if state in ('answer', 'why', 'push'): body_buf.append(ln); continue
    problems.append(f"unclassified line p{pno}: {txt[:70]}")
finish_body(); close_q()

for qq in questions:
    ls = qq.pop('q_lines')
    qq['q_num'] = qq.pop('n')
    qq['q_text'] = ' '.join(text_of(x['words'][1:] if i == 0 else x['words']) for i, x in enumerate(ls))
    qq['reported'] = ' '.join(qq['reported']) or None
    qq.setdefault('push', [])
    qq.pop('_buf', None)
for s in sections: s['intro'] = ' '.join(s['intro'])
for k, d in parts.items(): d['title'] = ' '.join(d['title']); d['intro'] = ' '.join(d['intro'])
json.dump({'parts': parts, 'sections': sections, 'questions': questions, 'problems': problems}, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(len(questions), 'questions;', len(sections), 'sections;', len(problems), 'problems')
for p in problems[:20]: print('  -', p)
