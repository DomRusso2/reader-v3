"""Check every number in the Reader V3 README against results/ (computed results only).
  python scripts/verify_release_numbers.py   -> ALL NUMBERS VERIFIED or a list of mismatches"""
import json, os, re, sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(D, 'results')
J = lambda f: json.load(open(os.path.join(R, f)))
S = {'v3': J('suite_reader-v3.json'), 'v2': J('suite_v2.json'), 'v8': J('suite_base21.json'), 'hec': J('suite_hecate.json')}
FA = J('fairfa_reader-v3_v2.json'); FB = J('fairfa_v2_v2_256_hecate_base_base21.json'); SP = J('speed.json')
raw = open(os.path.join(D, 'README.md'), encoding='utf-8').read()
flat = re.sub(r'\s+', ' ', raw)                                   # line breaks do not matter for the text checks
f3 = lambda v: f'{v:.3f}'
F8 = lambda k: f"{S[k]['FA80_w053'] * 100:.1f}%"
bad = []

# 1. head-to-head table
expect = {'blank': [F8(k) for k in S],
          'fairfa': [f"{FA['reader-v3']['mean']}%", f"{FA['reader-v2']['mean']}%", f"{FB['base']['mean']}%", f"{FB['hecate']['mean']}%"],
          'w047': [f3(S[k]['w047']) for k in S], '0009B': [f3(S[k]['0009B_125754']) for k in S]}
rows = {'blank': 'Blank papyrus marked as ink', 'fairfa': 'Background marked as ink', 'w047': 'PHerc0139 w047', '0009B': 'PHerc0009B, AUC'}
for k, lab in rows.items():
    line = next(l for l in raw.splitlines() if l.startswith('|') and lab in l)
    got = [c.strip().strip('*') for c in line.split('|')[2:6]]
    if got != expect[k]: bad.append((k, got, expect[k]))

# 2. text claims
hx, vx = int(S['hec']['FA80_w053'] / S['v3']['FA80_w053']), int(S['v8']['FA80_w053'] / S['v3']['FA80_w053'])
claims = [f"**Over {hx}x less false ink than Hecate, over {vx}x less than v8-in.**",
          f"**{F8('v3')}** of the papyrus as ink (Hecate {F8('hec')}, v8-in {F8('v8')}, Reader v2 {F8('v2')})",
          f"(**{FA['reader-v3']['mean']}%** vs 35.3% to {FB['base']['mean']}%)", f"{FB['base21']['mean']}%"]
for c in claims:
    if c not in flat: bad.append(('text claim not found', c))
if min(FB['hecate']['mean'], FB['base']['mean'], FA['reader-v2']['mean']) != 35.3: bad.append(('35.3% lower bound', 'changed'))

# 3. 'better than Reader v2 on every held-out test' and 'the fastest'
if min(S['v3'][k] - S['v2'][k] for k in ('w047', '0009B_125754', '0841_mean', '1447_mean')) <= 0 or S['v3']['FA80_w053'] >= S['v2']['FA80_w053']:
    bad.append(('better than Reader v2 on every test', 'FAILS'))
v3 = SP['reader-v3']['seconds']
if not all(v3 < SP[k]['seconds'] for k in ('reader-v2', 'v8-in (stride 21)', 'hecate')): bad.append(('fastest', 'FAILS'))
if bad:
    [print('MISMATCH', *b) for b in bad]; sys.exit(1)
print('ALL NUMBERS VERIFIED')
