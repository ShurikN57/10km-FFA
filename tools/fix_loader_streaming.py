from pathlib import Path
import re

p=Path('mobile.html')
s=p.read_text(encoding='utf-8')

pattern=r'''async function loadFfaRows\(distance\)\{.*?\n\}\nasync function loadFfaDistance\(distance\)\{'''
replacement='''async function loadFfaRows(distance){
  const cfg=FFA_DISTANCES[distance];
  const r=await fetch(cfg.file+"?v=20260831d",{cache:"no-store"});
  if(!r.ok) throw new Error("HTTP "+r.status);
  if(!("DecompressionStream" in window)) throw new Error("Décompression gzip non prise en charge par ce navigateur");
  if(!r.body) throw new Error("Flux de la base FFA indisponible");

  // Décompression en flux : beaucoup moins de mémoire que arrayBuffer + Blob,
  // indispensable pour la grosse base 10 km sur Safari/iOS.
  const stream=r.body.pipeThrough(new DecompressionStream("gzip"));
  const text=await new Response(stream).text();
  const data=JSON.parse(text);
  let rows=Array.isArray(data) ? data : (Array.isArray(data.rows) ? data.rows : []);

  // Garde-fou 5 km : supprime les chronos impossibles (< 12 min), dont le 10'53 erroné.
  if(distance==="5k") rows=rows.filter(row=>Number(row && row[3])>=720);
  return rows;
}
async function loadFfaDistance(distance){'''

ns,n=re.subn(pattern,replacement,s,flags=re.S)
if n!=1:
    raise SystemExit(f'loadFfaRows replacement count={n}')
p.write_text(ns,encoding='utf-8')
print('patched mobile.html')
