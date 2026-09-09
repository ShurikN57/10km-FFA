from pathlib import Path

p=Path('mobile.html')
s=p.read_text(encoding='utf-8')
if '?v=20260909a' not in s:
    raise SystemExit('mobile cache token anchor not found')
s=s.replace('?v=20260909a','?v=20260909b')
p.write_text(s,encoding='utf-8')

p=Path('sw.js')
s=p.read_text(encoding='utf-8')
if "comparateur-ffa-shell-v11" not in s:
    raise SystemExit('sw cache version anchor not found')
s=s.replace("comparateur-ffa-shell-v11","comparateur-ffa-shell-v12",1)
p.write_text(s,encoding='utf-8')
print('mobile + sw bumped for 10k V3')
