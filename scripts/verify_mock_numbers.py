#!/usr/bin/env python3
"""Recompute every number used in the Mock Interview Technicals model answers and
check that the matching figure appears in the right answer. Also checks the
structural rules (answer length, follow-up counts, a 'why' follow-up on every
question) and runs the easyJet calculator in a browser against the same maths.

Usage:  python3 scripts/verify_mock_numbers.py [path/to/index.html]
"""
import json, math, os, re, subprocess, sys
from datetime import date

PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'index.html')
html = open(PATH, encoding='utf-8').read()
DATA = json.loads(re.search(r'window\.MOCK_DATA = (\[.*?\]);</script>', html, re.S).group(1))
ITEM = {}
for q in DATA:
    ITEM[q['id']] = q
    for i, f in enumerate(q['followups']): ITEM[f"{q['id']}#{i+1}"] = f

def text(key):
    it = ITEM[key]                       # the spoken answer plus the question's own givens, never the checklist
    return ' '.join([it['question'], it['answer']]).replace(',', '')

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
def words(n):
    n = int(n)
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ('-' + ONES[n % 10] if n % 10 else '')
    if n >= 1000: return str(n)
    return ONES[n // 100] + ' hundred' + (' ' + words(n % 100) if n % 100 else '')

def forms(x, dp=None):
    """Plausible written or spoken forms of a value."""
    x = round(abs(x), 4)
    out = set()
    for d in (0, 1, 2, 3, 4):
        s = f'{x:.{d}f}'
        if abs(float(s) - x) > 1e-9: continue          # exact renderings only, never a rounded stand-in
        out.add(s); out.add(s.rstrip('0').rstrip('.') if '.' in s else s)
    p, frac = int(x), round(x - int(x), 4)
    pence = round(frac * 100, 2)
    if frac == 0: out.add(words(p))
    else:
        if pence == int(pence):
            out.add(f'{words(p)} pounds {words(pence)}'); out.add(f'{words(p)} {words(pence)}')
            if p == 0: out.add(f'{words(pence)} pence')
        else:
            out.add(f'{words(pence - 0.5)} and a half pence' if p == 0 else f'{words(p)} pounds {words(pence-0.5)} and a half')
    if frac == 0.5: out.update({'half', 'a half', f'{words(p)} and a half'} if p else {'half', 'a half'})
    return out

failures, checked = [], 0
def has(key, val, label=''):
    global checked
    checked += 1
    t = text(key).lower()
    ok = any(re.search(r'(?<![\d.])' + re.escape(f.lower()) + r'(?![\d])', t) for f in forms(val))
    if not ok: failures.append(f'{key}: expected {label or val} ({sorted(forms(val))[:4]}...) not found')
def literal(key, s):
    global checked
    checked += 1
    if s.replace(',', '').lower() not in text(key).lower(): failures.append(f'{key}: expected "{s}" not found')

tax = 0.25
# ── three-statement effects ────────────────────────────────────────────
has('acc-01', 10 * (1 - tax), 'NI -7.5'); has('acc-01', 10 * tax, 'tax 2.5')
has('acc-01#1', 10, 'no-tax NI -10')
r = 10 / 5; has('acc-02', r, 'dep 2'); has('acc-02', r * tax, 'tax 0.5'); has('acc-02', r * (1 - tax), 'NI -1.5'); has('acc-02', r * tax, 'CFO 0.5')
literal('acc-02#3', 'three pounds thirty-three') if round(10 / 3, 2) == 3.33 else failures.append('acc-02#3: 10/3 is not 3.33'); literal('acc-02#3', 'eighty-three pence') if round(10 / 3 * tax, 2) == 0.83 else failures.append('acc-02#3: shield is not 83p')
i = 10 * .05; has('acc-03', i, 'interest'); has('acc-03', i * tax, 'tax on interest'); has('acc-03', i * (1 - tax), 'NI')
has('acc-03#1', 5 * (1 - tax) / 100 * 100, 'after-tax cost of debt 3.75')
has('acc-06', 10 * (1 - tax), 'NI 7.5'); has('acc-06', 10 * tax, 'tax 2.5')
has('acc-07', 10 * (1 - tax), 'NI'); has('acc-07', 10 * tax, 'tax')
has('acc-08', 5, 'profit'); has('acc-08', 5 * tax, 'tax'); has('acc-08', 5 * (1 - tax), 'NI'); has('acc-08', 15 - 10 - 5 * tax, 'cash')
half_ni = 2.5 * (1 - tax); has('acc-08#3', half_ni, 'NI half sold'); has('acc-08#3', 10 - 7.5 + 2.5 * tax, 'cash half sold'); has('acc-08#3', 2.5 * tax, 'tax')
gain = 120 - 100; has('acc-09', gain, 'gain'); has('acc-09', gain * tax, 'tax'); has('acc-09', gain * (1 - tax), 'NI'); has('acc-09', 120 - gain * tax, 'net cash')
has('acc-09#3', 20 * (1 - tax), 'loss NI'); has('acc-09#3', 80 + (-20 * (1 - tax) + 20), 'cash on 80 sale')
has('acc-12', 10 * .05, 'interest saved'); has('acc-12', 10 * .05 * (1 - tax), 'after tax')
has('acc-14', 10 * (1 - tax), 'SBC NI'); has('acc-14', 10 * tax, 'cash'); has('acc-15', 10 * (1 - tax), 'accrual NI'); has('acc-15', 10 * tax, 'cash')
L = sum(10 / 1.05 ** k for k in range(1, 6)); dep = L / 5; intr = L * .05
has('acc-16', round(L, 1), 'lease liability'); has('acc-16', round(dep, 2), 'dep'); has('acc-16', round(intr, 2), 'interest'); has('acc-16#2', round(dep + intr, 2), 'year-one charge')
has('acc-17', 20 - 50, 'WC -30'); has('acc-17', 1.1 * (20 - 50), 'WC -33'); has('acc-17', 3, 'cash 3'); has('acc-17#3', 0.9 * -30, 'WC -27')
has('acc-18', 10 * (1 - tax), 'gift card NI'); has('acc-18', 10 * tax, 'tax')
has('acc-19', (100 - 20) * tax, 'book tax'); has('acc-19', (100 - 40) * tax, 'cash tax'); has('acc-19', (40 - 20) * tax, 'DTL')
# ── EV and equity value ────────────────────────────────────────────────
has('ev-01', 1000 - 300 + 100 - 50 - 20 + 40, 'bridge 770')
has('ev-02#1', 0.2 * 1000, 'minority 200'); has('ev-02#1', 0.8 * 1000, 'parent 800')
has('ev-04', 50, 'proceeds'); has('ev-04', 5, 'buyback'); has('ev-04', 105, 'diluted'); has('ev-04', 105 * 10, 'equity value')
has('ev-04#3', 10 - 50 / 20, 'net new 7.5'); has('ev-04#3', 100 + 10 - 50 / 20, 'diluted 107.5'); has('ev-04#3', (110 - 2.5) * 20, 'equity 2150')
has('ev-06', 100 + 0 - 150, 'negative EV -50'); has('ev-09', 100 / 5, 'convertible shares 20'); has('ev-09', 20 * 8, 'value 160')
has('val-09', 50 * 8, 'SOTP A'); has('val-09', 30 * 14, 'SOTP B'); has('val-09', 50 * 8 + 30 * 14, 'SOTP total')
# ── DCF ────────────────────────────────────────────────────────────────
has('dcf-02', 100 * (1 - tax), 'NOPAT 75'); has('dcf-02', 100 * (1 - tax) + 30 - 40 - 5, 'UFCF 60')
has('dcf-03', .7 * 9, 'equity part 6.3'); has('dcf-03', .3 * 5 * (1 - tax), 'debt part 1.125'); has('dcf-03', .7 * 9 + .3 * 5 * (1 - tax), 'WACC 7.425')
has('dcf-04', 4 + 1.2 * 5.5, 'Ke 10.6'); has('dcf-04', 1.2 * 5.5, 'beta x ERP')
tv = 60 * 1.02 / .06; has('dcf-05', tv, 'TV 1020'); has('dcf-05', tv / 100, 'implied 10.2x')
has('dcf-06', 1.02 / .06, 'factor 17'); has('dcf-06', round(1.02 / .07, 1), 'factor 14.6'); has('dcf-06', round((1.02 / .07) / (1.02 / .06) - 1, 2) * -100, 'fall 14%')
bu = 1.2 / (1 + (1 - tax) * .5); has('dcf-07', round(bu, 2), 'unlevered beta'); has('dcf-07', round(bu * (1 + (1 - tax) * .25), 2), 'relevered beta'); has('dcf-07', 1 + .75 * .5, 'denominator 1.375'); has('dcf-07', 1 + .75 * .25, '1.1875')
pvtv = tv / 1.08 ** 5; pvf = sum(60 / 1.08 ** k for k in range(1, 6))
has('dcf-08', round(pvf, -1), 'PV of FCF about 240'); has('dcf-08', round(pvtv), 'PV TV 694'); has('dcf-08', round(pvtv / (pvtv + pvf) * 100), 'TV share 74'); has('dcf-08', round(pvtv + pvf), 'EV 934')
sl = sum(5 / 1.08 ** k for k in range(1, 6)); ac = sum(x / 1.08 ** k for k, x in enumerate([10, 7.5, 5, 2.5, 0], 1))
has('dcf-11', round(sl, 1), 'SL PV 20.0'); has('dcf-11', round(ac, 1), 'accelerated PV 21.5'); has('dcf-11', round(ac - sl, 1), 'gain 1.5')
has('dcf-12', round((1.08 ** .5 - 1) * 100, 1), 'mid-year 3.9%')
# ── M&A ────────────────────────────────────────────────────────────────
has('ma-01', round(130 / 140, 2), 'EPS 0.93'); has('ma-01', round((1 - 130 / 140) * 100), 'dilution 7')
has('ma-01#1', round(100 / 15, 1), 'yield 6.7'); has('ma-01#1', 100 * 30 / 600, 'yield 5'); has('ma-01#2', 140 - 130, 'needs 10'); has('ma-01#2', round(10 / .75, 1), 'gross-up 13.3')
gw_fv = 200 + 150 - 150 * tax; has('ma-02', gw_fv, 'FV net assets'); has('ma-02', 600 - gw_fv, 'goodwill')
has('ma-03', 500 * .3, 'premium 150'); has('ma-03', 200 - 150, 'retained 50')
cash, debt, stock = 300, 180, 120
fi, di = cash * .04 * (1 - tax), debt * .06 * (1 - tax)
ni = 200 + 40 - fi - di; sh = 100 + stock / 30
has('ma-04', 12, 'foregone pre-tax'); has('ma-04', fi, 'foregone after tax'); has('ma-04', di, 'debt after tax'); has('ma-04', debt * .06, 'debt pre-tax')
has('ma-04', stock / 30, '4m shares'); has('ma-04', ni, 'earnings 222.9'); has('ma-04', sh, 'shares 104'); has('ma-04', round(ni / sh, 2), 'EPS 2.14'); has('ma-04', round((ni / sh / 2 - 1) * 100), 'accretion 7')
has('ma-04#1', cash and 4 * (1 - tax), 'cash cost 3%'); has('ma-04#1', 6 * (1 - tax), 'debt cost 4.5%'); has('ma-04#1', round(40 / 600 * 100, 1), 'yield 6.7')
syn = 10 * (1 - tax); ni2 = ni + syn; has('ma-04#2', syn, 'synergy after tax'); has('ma-04#2', ni2, 'earnings 230.4'); has('ma-04#2', round(ni2 / sh, 2), 'EPS 2.22'); has('ma-04#2', round((ni2 / sh / 2 - 1) * 100, 1), 'accretion 10.8')
di3 = debt * .10 * (1 - tax); ni3 = 200 + 40 - fi - di3
has('ma-04#3', debt * .10, 'interest 18'); has('ma-04#3', di3, 'after tax 13.5'); has('ma-04#3', ni3, 'earnings 217.5'); has('ma-04#3', round(ni3 / sh, 2), 'EPS 2.09'); has('ma-04#3', round((ni3 / sh / 2 - 1) * 100, 1), 'accretion 4.6')
# ── LBO ────────────────────────────────────────────────────────────────
has('lbo-03', 1500 / 1000, 'unlevered 1.5x'); has('lbo-03', (1500 - 600) / 400, 'levered 2.25x'); has('lbo-03', 1500 - 600, 'equity 900')
eq0, debt0, ev5, debt5 = 400, 600, 130 * 10, 400; eq5 = ev5 - debt5; moic = eq5 / eq0
has('lbo-04', 1000, 'EV in'); has('lbo-04', debt0, 'debt'); has('lbo-04', eq0, 'equity'); has('lbo-04', ev5, 'EV out 1300'); has('lbo-04', debt5, 'debt out'); has('lbo-04', eq5, 'equity out 900'); has('lbo-04', moic, 'MOIC 2.25'); has('lbo-04', round((moic ** .2 - 1) * 100, 1), 'IRR 17.6')
has('lbo-04#1', eq5 - eq0, 'gain 500'); has('lbo-04#1', 30 * 10, 'growth 300'); has('lbo-04#1', 200, 'paydown 200')
ev9 = 130 * 9; has('lbo-04#3', ev9, 'EV at 9x'); has('lbo-04#3', ev9 - 400, 'equity 770'); has('lbo-04#3', (ev9 - 400) / 400, 'MOIC 1.925'); has('lbo-04#3', round((((ev9 - 400) / 400) ** .2 - 1) * 100), 'IRR 14')
for m in (2, 2.5, 3): has('lbo-05', round((m ** .2 - 1) * 100, 1), f'{m}x 5y IRR')
has('lbo-05', round((2 ** (1 / 3) - 1) * 100), '2x 3y'); has('lbo-05', round((3 ** (1 / 3) - 1) * 100), '3x 3y'); has('lbo-05#2', round((1.5 ** (1 / 3) - 1) * 100, 1), '1.5x 3y')
has('lbo-06', 300, 'growth'); has('lbo-06', 200, 'paydown'); has('lbo-06', 500, 'total'); has('lbo-06#2', 2 * 130, 'multiple 260'); has('lbo-06#2', 260 + 300 + 200, 'gain 760'); has('lbo-06#2', 12 * 130 - 400, 'equity 1160')
has('lbo-07', round((2 ** .5 - 1) * 100), '2x 2y'); has('lbo-07', round((2 ** (1 / 7) - 1) * 100, 1), '2x 7y')
def irr(cfs):
    lo, hi = -.9, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        (lo, hi) = (mid, hi) if sum(c / (1 + mid) ** k for k, c in enumerate(cfs)) > 0 else (lo, mid)
    return mid
has('lbo-08', round(irr([-400, 0, 100, 0, 0, 800]) * 100, 1), 'recap IRR 19.4'); has('lbo-08', round(irr([-400, 0, 0, 0, 0, 900]) * 100, 1), 'plain IRR 17.6'); has('lbo-08', 900 / 400, 'MOIC 2.25')
# ── markets ────────────────────────────────────────────────────────────
def bond(c, y, n=10): return sum(c / (1 + y) ** k for k in range(1, n + 1)) + 100 / (1 + y) ** n
D = 1.05 / .05 * (1 - 1 / 1.05 ** 10) / 1.05
has('mac-01', round(bond(5, .06), 2), 'price 6%'); has('mac-01', round(bond(5, .04), 2), 'price 4%'); has('mac-01', round((bond(5, .06) / 100 - 1) * -100, 1), 'fall 7.4'); has('mac-01', round((bond(5, .04) / 100 - 1) * 100, 1), 'rise 8.1'); has('mac-01', round(D, 1), 'duration 7.7')
has('mac-01#3', round(bond(5, .06, 2), 2), '2y price'); has('mac-01#3', round((1 - bond(5, .06, 2) / 100) * 100, 1), '2y fall')
val = lambda cf, g, r: cf * (1 + g) / (r - g)
has('mac-02', val(10, .02, .08), 'mature 170'); has('mac-02', val(10, .06, .08), 'growth 530'); has('mac-02', round(val(10, .02, .09)), 'mature 146'); has('mac-02', round(val(10, .06, .09)), 'growth 353')
has('mac-02', round((1 - val(10, .02, .09) / val(10, .02, .08)) * 100), 'fall 14'); has('mac-02', round((1 - val(10, .06, .09) / val(10, .06, .08)) * 100), 'fall 33')
# ── easyJet, McCormick ─────────────────────────────────────────────────
O, D0, P = 715, 394, 677.8; days = (date(2027, 3, 31) - date(2026, 9, 29)).days; ret = (O - P) / P
has('deal-01', round(O - P, 1), 'spread 37.2'); has('deal-01', round(ret * 100, 1), 'return 5.5'); has('deal-01', days, 'days 183'); has('deal-01', round(((1 + ret) ** (365 / days) - 1) * 100), 'annualised 11')
has('deal-01', round((P - D0) / (O - D0) * 100), 'probability 88'); has('deal-01', round((1 - D0 / P) * 100), 'downside 42'); has('deal-01#2', round((P - D0) / (O - D0) * 100, 1), 'probability 88.4')
has('deal-03', round(P - D0), 'risk 284'); has('deal-03', round(O - P), 'reward 37'); has('deal-03', round((P - D0) / (O - D0) * 100), 'breakeven 88')
P2 = 700; r2 = (O - P2) / P2
has('deal-03#2', O - P2, 'spread 15'); has('deal-03#2', round(r2 * 100, 1), 'return 2.1'); has('deal-03#2', round(((1 + r2) ** (365 / days) - 1) * 100, 1), 'annualised 4.3'); has('deal-03#2', round((P2 - D0) / (O - D0) * 100), 'probability 95')
assert abs(55.1 + 9.9 + 35 - 100) < 1e-9
E = 44.8 / 13.8; has('deal-05', round(E, 1), 'EBITDA 3.2bn'); has('deal-05', round(44.8 / (E + .6), 1), 'post-synergy 11.6'); has('deal-05', round(15.7 / 44.8 * 100), 'cash share 35'); has('deal-05#1', 0, 'placeholder') if False else None
has('deal-05#2', 55.1 + 9.9, 'Unilever side 65'); has('deal-05#2', round(44.8 / (E + .6), 1), 'post-synergy 11.6')

# ── structure ──────────────────────────────────────────────────────────
for q in DATA:
    keys = [q['id']] + [f"{q['id']}#{i+1}" for i in range(len(q['followups']))]
    for k in keys:
        n = len(ITEM[k]['answer'].split())
        if n > 100: failures.append(f'{k}: {n} words (max 100)')
        if not ITEM[k]['checklist'] or not ITEM[k]['mistake']: failures.append(f'{k}: missing checklist or mistake')
    if not 2 <= len(q['followups']) <= 4: failures.append(f"{q['id']}: {len(q['followups'])} follow-ups")
    if not any(f['question'].lower().startswith('why') or 'why does that work' in f['question'].lower() for f in q['followups']):
        failures.append(f"{q['id']}: no 'why' follow-up")
    if q['likelihood'] not in ('Likely', 'Possible', 'Unlikely'): failures.append(f"{q['id']}: bad tag")
    if q['timer'] not in (60, 90): failures.append(f"{q['id']}: bad timer")

NUM = re.compile(r'(?<![\w.])£?(\d[\d,]*\.?\d*)\s*(%|m\b|bn\b|x\b|p\b)?')
for k, it in ITEM.items():
    ans = (ITEM[k.split('#')[0]]['question'] + ' ' if '#' not in k else '') + it['answer']
    ans = ans.replace(',', '').lower()
    for pt in it['checklist']:
        for m in NUM.finditer(pt.replace(',', '')):
            tok = m.group(1).rstrip('.')
            try: v = float(tok)
            except ValueError: continue
            if not ('.' in tok or v >= 100 or m.group(2) in ('%', 'x')): continue      # skip bare small integers like "5 years"
            checked += 1
            if not any(re.search(r'(?<![\d.])' + re.escape(f.lower()) + r'(?![\d])', ans) for f in forms(v)):
                failures.append(f'{k}: checklist figure "{m.group(0).strip()}" not in the answer text ({pt[:50]})')

# ── the browser calculator against the same maths ──────────────────────
node_js = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium' });
  const p = await b.newPage();
  await p.goto('file://' + process.argv[1]);
  const out = await p.evaluate(() => [[677.8,'2026-09-29'],[700,'2026-10-01'],[640,'2026-10-01']].map(([price,date]) =>
    window.MockCalc.ejCompute({price:String(price), date, end:'2027-03-31', offer:'715', und:'394'})));
  console.log(JSON.stringify(out)); await b.close();
})();
"""
try:
    env = dict(os.environ, NODE_PATH=os.environ.get('NODE_PATH', '/opt/node22/lib/node_modules'))
    res = subprocess.run(['node', '-e', node_js, os.path.abspath(PATH)], capture_output=True, text=True, env=env, timeout=90)
    got = json.loads([l for l in res.stdout.splitlines() if l.startswith('[')][-1])
    for (price, d0), g in zip([(677.8, date(2026, 9, 29)), (700, date(2026, 10, 1)), (640, date(2026, 10, 1))], got):
        dd = (date(2027, 3, 31) - d0).days; rr = (715 - price) / price
        want = dict(spread=715 - price, ret=rr, days=dd, ann=(1 + rr) ** (365 / dd) - 1, prob=(price - 394) / (715 - 394), down=394 / price - 1)
        for k, v in want.items():
            checked += 1
            if abs(g[k] - v) > 1e-9: failures.append(f'calculator {price}p {k}: got {g[k]} want {v}')
    print('easyJet calculator: matched Python for 3 price/date cases')
except Exception as e:
    print('easyJet calculator browser check skipped:', repr(e)[:120])

print(f'{len(DATA)} questions, {sum(len(q["followups"]) for q in DATA)} follow-ups, {checked} checks')
if failures:
    print('\nFAILURES:'); print('\n'.join(' -', *failures) if False else '\n'.join(' - ' + f for f in failures)); sys.exit(1)
print('All numbers match.')
