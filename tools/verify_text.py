import json, re, html, subprocess, difflib, sys
PDF, JSON = sys.argv[1], sys.argv[2]
D = json.load(open(JSON))
def strip(h): return html.unescape(re.sub(r'</?(b|i|sup)>', '', h))
def blocks_text(bs):
    out = []
    for b in bs:
        out.append(strip(b['html']) if b['type'] == 'p' else ' '.join(' '.join(r) for r in b['rows']))
    return out
exp = []
cur_sec = None; seen_group = set()
secs = {s['id']: s for s in D['sections']}
for q in D['questions']:
    s = secs[q['section']]
    if s['id'] != cur_sec:
        cur_sec = s['id']; exp += [s['id'], s['title'], s['intro']]
    if q['group'] and (q['section'], q['group']) not in seen_group:
        seen_group.add((q['section'], q['group'])); exp.append(q['group'])
    exp += [f"Q{q['q_num']}.", q['q_text']]
    if q['reported']: exp += ['REPORTED', q['reported']]
    exp += ['ANSWER'] + blocks_text(q['answer']) + ["WHY IT'S RIGHT"] + blocks_text(q['why'])
    if q['push']:
        exp += ['IF THEY PUSH']
        for p in q['push']: exp += [p['q']] + blocks_text(p['a'])
exp_tokens = ' '.join(exp).split()
raw = subprocess.run(['pdftotext', '-f', '4', '-l', '82', PDF, '-'], capture_output=True, text=True).stdout
lines = [l for l in raw.splitlines() if l.strip() and l.strip() != 'Moelis London | First-round technical prep' and not re.fullmatch(r'\d{1,2}', l.strip()) and l.strip() != '\x0c']
raw_tokens = ' '.join(lines).split()
# tables come out column by column in pdftotext, so compare them order-insensitively afterwards
sm = difflib.SequenceMatcher(None, raw_tokens, exp_tokens, autojunk=False)
bad = [(tag, raw_tokens[i1:i2], exp_tokens[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal']
print('raw tokens', len(raw_tokens), 'data tokens', len(exp_tokens), 'ratio', round(sm.ratio(), 5), 'mismatch blocks', len(bad))
for tag, a, b in bad[:30]:
    print(tag, '\n  PDF :', ' '.join(a)[:200], '\n  DATA:', ' '.join(b)[:200])
