#!/usr/bin/env python3
"""Build index.html (and an artifact variant) from src/template.html plus the parsed PDF data.

    python3 -I tools/parse_pdf.py   <Moelis_First_Round_Technicals.pdf> parsed.json
    python3 -I tools/verify_text.py <same pdf> parsed.json        # word-for-word check against the PDF
    python3 -I tools/build.py       [src/questions.json] [artifact.html]

The artifact variant is the page content only (title, meta, style, body) with no embedded binaries,
which is what claude.ai needs for link sharing.
"""
import json, os, re, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, 'src', 'questions.json')
data = json.load(open(src, encoding='utf-8'))
data.pop('problems', None)
for q in data['questions']:                      # compact, app-facing keys
    if 'q_num' in q: q['n'] = q.pop('q_num')
    q.pop('page', None)
for s in data['sections']:
    s.pop('page', None)

template = open(os.path.join(root, 'src', 'template.html'), encoding='utf-8').read()
marker = '/*__DATA__*/null'
assert template.count(marker) == 1
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
page = template.replace(marker, payload)
open(os.path.join(root, 'index.html'), 'w', encoding='utf-8').write(page)
print('index.html', len(page), 'bytes;', len(data['questions']), 'questions')

if len(sys.argv) > 2:
    out_path = sys.argv[2]
    title = re.search(r'<title>.*?</title>', page, re.S).group(0)
    metas = '\n'.join(re.findall(r'<meta name="[^>]*>', page))
    style = re.search(r'<style>.*?</style>', page, re.S).group(0)
    body = re.search(r'<body>\n(.*)\n</body>', page, re.S).group(1)
    out = title + '\n' + metas + '\n' + style + '\n' + body + '\n'
    assert 'data:image' not in out and 'data:application' not in out
    open(out_path, 'w', encoding='utf-8').write(out)
    print('artifact', out_path, len(out), 'bytes')
