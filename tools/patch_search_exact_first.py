from pathlib import Path
p=Path('cloudflare-prototype/worker.js')
s=p.read_text(encoding='utf-8')
old="""        WHERE athlete_fts MATCH ? AND a.distance = ?\n        ORDER BY a.birth_year ASC, a.full_name ASC\n        LIMIT 100\n      `).bind(ftsQuery, distance);"""
new="""        WHERE athlete_fts MATCH ? AND a.distance = ?\n        ORDER BY CASE WHEN a.name_key = ? THEN 0 ELSE 1 END, a.birth_year ASC, a.full_name ASC\n        LIMIT 100\n      `).bind(ftsQuery, distance, q);"""
if old not in s:
    raise SystemExit('search query anchor not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched worker search exact-first')
