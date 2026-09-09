from pathlib import Path

p = Path('mobile.html')
s = p.read_text(encoding='utf-8')
old = '  "10k":{label:"10 km",file:"./ffa_base.json.gz",export:"comparaison_ffa_10km.csv",minPb:"Ex. 30:00",maxPb:"Ex. 35:00"},'
new = '  "10k":{label:"10 km",file:"./ffa_10km_2024_2026_compact.json.gz",fallbackFile:"./ffa_base.json.gz",export:"comparaison_ffa_10km.csv",minPb:"Ex. 30:00",maxPb:"Ex. 35:00"},'
if old not in s:
    raise SystemExit('FFA_DISTANCES 10k anchor not found')
s = s.replace(old, new, 1)
old_fetch = '  const r=await fetch(cfg.file+"?v=20260831d",{cache:"no-store"});\n  if(!r.ok) throw new Error("HTTP "+r.status);'
new_fetch = '''  let r=await fetch(cfg.file+"?v=20260909a",{cache:"no-store"});
  if(!r.ok && cfg.fallbackFile){
    r=await fetch(cfg.fallbackFile+"?v=20260909a",{cache:"no-store"});
  }
  if(!r.ok) throw new Error("HTTP "+r.status);'''
if old_fetch not in s:
    raise SystemExit('loadFfaRows fetch anchor not found')
s = s.replace(old_fetch, new_fetch, 1)
p.write_text(s, encoding='utf-8')

sw = Path('sw.js')
t = sw.read_text(encoding='utf-8')
if "comparateur-ffa-shell-v10" in t:
    t = t.replace("comparateur-ffa-shell-v10", "comparateur-ffa-shell-v11", 1)
old_cond = "if(url.pathname.endsWith('/ffa_base.json.gz') || url.pathname.endsWith('/ffa_5km_2024_2026.json.gz')){"
new_cond = "if(url.pathname.endsWith('/ffa_base.json.gz') || url.pathname.endsWith('/ffa_5km_2024_2026.json.gz') || url.pathname.endsWith('/ffa_10km_2024_2026_compact.json.gz')){"
if old_cond in t:
    t = t.replace(old_cond, new_cond, 1)
sw.write_text(t, encoding='utf-8')
print('patched mobile 10k V3 compact fallback + SW v11')
