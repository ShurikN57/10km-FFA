from pathlib import Path

p=Path('mobile.html')
s=p.read_text(encoding='utf-8')
old='''async function loadFfaRows(distance){\n  const cfg=FFA_DISTANCES[distance];\n  const r=await fetch(cfg.file,{cache:"no-store"});\n  if(!r.ok) throw new Error("HTTP "+r.status);\n  if(!("DecompressionStream" in window)) throw new Error("Décompression gzip non prise en charge par ce navigateur");\n  if(!r.body) throw new Error("Flux de la base FFA indisponible");\n  const stream=r.body.pipeThrough(new DecompressionStream("gzip"));\n  const text=await new Response(stream).text();\n  const data=JSON.parse(text);\n  return Array.isArray(data) ? data : (Array.isArray(data.rows) ? data.rows : []);\n}\n'''
new='''async function loadFfaRows(distance){\n  const cfg=FFA_DISTANCES[distance];\n  const r=await fetch(cfg.file,{cache:"no-store"});\n  if(!r.ok) throw new Error("HTTP "+r.status);\n\n  // Selon Safari / GitHub Pages, un fichier .gz peut arriver soit encore\n  // compressé, soit déjà décompressé par la couche HTTP. On inspecte donc\n  // les deux premiers octets au lieu de forcer systématiquement gunzip.\n  const buf=await r.arrayBuffer();\n  const bytes=new Uint8Array(buf);\n  let text;\n  const isGzip=bytes.length>=2 && bytes[0]===0x1f && bytes[1]===0x8b;\n\n  if(isGzip){\n    if(!("DecompressionStream" in window)) throw new Error("Décompression gzip non prise en charge par ce navigateur");\n    const stream=new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));\n    text=await new Response(stream).text();\n  }else{\n    text=new TextDecoder("utf-8").decode(bytes);\n  }\n\n  const data=JSON.parse(text);\n  const rows=Array.isArray(data) ? data : (Array.isArray(data.rows) ? data.rows : []);\n  if(!rows.length) throw new Error("Base vide ou format non reconnu");\n  return rows;\n}\n'''
if old not in s:
    raise SystemExit('Bloc loadFfaRows attendu introuvable')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Force un nouveau service worker/cache pour éliminer d'anciennes réponses.
sw=Path('sw.js')
t=sw.read_text(encoding='utf-8')
t=t.replace("const SHELL_CACHE='comparateur-ffa-shell-v6';","const SHELL_CACHE='comparateur-ffa-shell-v7';")
t=t.replace("const DATA_CACHE='comparateur-ffa-data-v2';","const DATA_CACHE='comparateur-ffa-data-v3';")
sw.write_text(t,encoding='utf-8')
